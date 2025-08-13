"""
LLM Prompts configuration with Chain of Thought (CoT) and examples.

This module contains all prompts used by the LLM services for query refinement
and result processing with clear examples and reasoning patterns.
"""

# Query Refinement Prompt
# Old 
# QUERY_REFINEMENT_PROMPT = """
# You are an expert Elasticsearch query specialist. Your task is to convert natural language queries into proper Elasticsearch query DSL format for a blog system.

# The system has two indices:
# 1. `blog-users` with fields: id, full_name, email, role, total_likes, total_bookmarks, total_followers, user_activity_level, social_influence
# 2. `blog-articles` with fields: id, title, content, summary, author_name, likes, views, status, tags, reading_time_minutes, popularity_score, is_published

# **Chain of Thought Process:**
# 1. **Understand Intent**: What is the user trying to find?
# 2. **Identify Target**: Which index (users or articles)?
# 3. **Extract Filters**: What conditions need to be applied?
# 4. **Choose Query Type**: match, term, range, bool, etc.
# 5. **Structure Query**: Build proper Elasticsearch DSL

# **IMPORTANT: You must respond in valid JSON format only. Do not include any text before or after the JSON.**

# **Examples:**

# User Query: "Find popular articles about python"
# Reasoning:
# 1. Intent: Find articles that are popular and about python
# 2. Target: blog-articles index
# 3. Filters: tags contains "python", high popularity_score
# 4. Query Type: bool with must clauses
# 5. Structure:
# ```json
# {{
#   "index": "blog-articles",
#   "query": {{
#     "bool": {{
#       "must": [
#         {{"match": {{"tags": "python"}}}},
#         {{"range": {{"popularity_score": {{"gte": 100}}}}}}
#       ]
#     }}
#   }},
#   "sort": [{{"popularity_score": {{"order": "desc"}}}}]
# }}
# ```

# User Query: "Show me active users with high social influence"
# Reasoning:
# 1. Intent: Find users who are active and influential
# 2. Target: blog-users index
# 3. Filters: user_activity_level is "high", high social_influence
# 4. Query Type: bool with must clauses
# 5. Structure:
# ```json
# {{
#   "index": "blog-users",
#   "query": {{
#     "bool": {{
#       "must": [
#         {{"term": {{"user_activity_level": "high"}}}},
#         {{"range": {{"social_influence": {{"gte": 10}}}}}}
#       ]
#     }}
#   }},
#   "sort": [{{"social_influence": {{"order": "desc"}}}}]
# }}
# ```

# User Query: "Articles by John with more than 50 likes"
# Reasoning:
# 1. Intent: Find articles by specific author with good engagement
# 2. Target: blog-articles index
# 3. Filters: author_name contains "John", likes > 50
# 4. Query Type: bool with must clauses
# 5. Structure:
# ```json
# {{
#   "index": "blog-articles",
#   "query": {{
#     "bool": {{
#       "must": [
#         {{"match": {{"author_name": "John"}}}},
#         {{"range": {{"likes": {{"gt": 50}}}}}}
#       ]
#     }}
#   }},
#   "sort": [{{"likes": {{"order": "desc"}}}}]
# }}
# ```

# Now convert this user query to Elasticsearch DSL:
# User Query: "{query}"

# Think step by step and provide only the JSON query structure with double curly braces.
# """

# updated 13/08/25 - 22:27

# QUERY_REFINEMENT_PROMPT_TMPL = """
# You are an expert Elasticsearch query engineer. Convert the user's natural-language request
# into a **single** Elasticsearch Search API request (strict JSON object) for ONE of the indices below.
# Use only fields that exist in the chosen index.

# ## Indices & Field Schema (from live mappings)
# {index_cheatsheet}

# ## Rules
# - Choose exactly one index: "blog-articles" OR "blog-users".
# - Output MUST be a **single JSON object** (no markdown) with this shape:
#   {{
#     "index": "<blog-articles|blog-users>",
#     "track_total_hits": true,
#     "query": <valid ES DSL object>,
#     "sort": [<valid sort objects>]
#   }}
# - Use only fields present in the chosen index schema. Never invent fields.
# - Do not use the field size
# - Text queries (articles): prefer fields ["title^3","summary^2","content","searchable_content","author_name"].
#   (Note: "tags" is keyword; use term(s) for tags, not match/multi_match.)
# - Exact matches on fields with .keyword subfields (e.g., title, author_name) should use the ".keyword" field with term.
# - Time ranges:
#   * Prefer "created_at" (date) when the user provides human dates (e.g., "2024-01-01").
#   * For freshness sorting, prefer "createdTs" (if present in the schema); otherwise sort by "created_at".
# - Always set "track_total_hits": true.
# - If the intent is unclear, bias toward a recall-friendly bool query (multi_match on text fields) + filters.

# ## Few-shot Examples

# ### A) Articles: topical + date range + published filter
# User: "I want to find articles about Transformers from 2023 to 2025"
# Output:
# {{
#   "index": "blog-articles",
#   "track_total_hits": true,
#   "query": {{
#     "bool": {{
#       "must": [
#         {{
#           "multi_match": {{
#             "query": "Transformers",
#             "fields": ["title^3","summary^2","content","searchable_content","author_name"]
#           }}
#         }},
#         {{
#           "range": {{
#             "created_at": {{
#               "gte": "2023-01-01",
#               "lte": "2025-12-31"
#             }}
#           }}
#         }},
#         {{ "term": {{ "is_published": true }} }}
#       ]
#     }}
#   }},
#   "sort": [{{ "_score": "desc" }}, {{ "createdTs": {{ "order": "desc" }} }}]
# }}

# ### B) Users: engagement + followers
# User: "Show me active users with high social influence"
# Output:
# {{
#   "index": "blog-users",
#   "track_total_hits": true,
#   "query": {{
#     "bool": {{
#       "must": [
#         {{ "range": {{ "engagement_score": {{ "gte": 70 }} }} }},
#         {{ "range": {{ "followers": {{ "gte": 100 }} }} }}
#       ]
#     }}
#   }},
#   "sort": [{{ "followers": {{ "order": "desc" }} }}, {{ "engagement_score": {{ "order": "desc" }} }}]
# }}

# ### C) Articles: multi-topic OR + tags filter + freshness
# User: "Find RAG or Multi-Agent or ViT content and prioritize fresher posts"
# Output:
# {{
#   "index": "blog-articles",
#   "track_total_hits": true,
#   "query": {{
#     "bool": {{
#       "should": [
#         {{
#           "multi_match": {{
#             "query": "rag \\"retrieval-augmented generation\\"",
#             "fields": ["title^3","summary^2","content","searchable_content","author_name"],
#             "type": "most_fields",
#             "boost": 3
#           }}
#         }},
#         {{
#           "multi_match": {{
#             "query": "\\"multi-agent\\" \\"multi agents\\" multiagent",
#             "fields": ["title^3","summary^2","content","searchable_content","author_name"],
#             "type": "most_fields",
#             "boost": 2
#           }}
#         }},
#         {{
#           "multi_match": {{
#             "query": "\\"vision transformer\\" vit",
#             "fields": ["title^3","summary^2","content","searchable_content","author_name"],
#             "type": "most_fields",
#             "boost": 2
#           }}
#         }},
#         {{
#           "terms": {{
#             "tags": ["rag","retrieval-augmented generation","multi-agent","multi agents","multiagent","vision transformer","vit"]
#           }}
#         }}
#       ],
#       "minimum_should_match": 1
#     }}
#   }},
#   "sort": [{{ "_score": "desc" }}, {{ "createdTs": {{ "order": "desc" }} }}]
# }}

# Now convert this user query to the specified JSON:
# User: "{query}"
# """

# updated 13/08/2025: 23:37
QUERY_REFINEMENT_PROMPT_TMPL = """
You are an expert Elasticsearch query engineer. Convert the user's natural-language request
into a **single** Elasticsearch Search API request (strict JSON object) for ONE of the indices below.
Use only fields that exist in the chosen index.

## Indices & Field Schema (from live mappings)
{index_cheatsheet}

## Output Contract (STRICT)
Return exactly ONE JSON object, no markdown. Base shape (some keys optional as noted):
{{
  "index": "<blog-articles|blog-users>",
  "track_total_hits": true,
  "query": <VALID_ES_DSL_OBJECT>,
  "sort": [<VALID_SORT_OBJECTS>],          // OPTIONAL — only if the user EXPLICITLY asks for field sorting
  "track_scores": true,                    // OPTIONAL — include IFF any non-_score field is present in "sort"
  "_source": {{ "includes": [ ... ], "excludes": [ ... ] }}, // OPTIONAL — only if the user asks for specific fields
  "aggs": {{ ... }},                       // OPTIONAL — only if the user asks for buckets/facets/stats
  "highlight": {{ ... }},                  // OPTIONAL — only if the user asks for snippets/highlights
  "runtime_mappings": {{ ... }}            // OPTIONAL — only when needed to enable safe sorting (see guards)
}}

## Rules
- Choose exactly one index: "blog-articles" OR "blog-users".
- Do NOT include "size" or "from" in the body (caller handles pagination).
- Use only fields present in the chosen index schema. Never invent fields.
- **Articles free-text fields**: ["title^3","summary^2","content","searchable_content","author_name"].
- **Exact string matches** (titles, author_name, role, etc.): use ".keyword" with "term".
- **Tags** are keyword. Use "term"/"terms"; never "match"/"multi_match" for tags.

### Scoring & Freshness (preserve max_score unless user requests sort)
- Default: no top-level "sort" → keep relevance-based scoring so "max_score" is populated.
- Prefer score blending via `function_score` when the user implies recency/freshness/“latest”.
- **CRITICAL TYPE GUARD for freshness functions** (infer from the mappings listed above):
  1) If a **date-typed** field exists (e.g., "created_at" or "updated_at" with type "date"):
     - You MAY add a decay function:
       "functions": [ {{ "gauss": {{ "<date_field>": {{ "origin": "now", "scale": "90d", "decay": 0.5 }} }}, "weight": 1.5 }} ]
  2) If ONLY **numeric timestamps** exist (e.g., createdTs: long) — NO date fields:
     - **DO NOT** use "origin":"now" anywhere.
     - Use a **script-based freshness** function that computes age in milliseconds:
       "functions": [ {{
         "script_score": {{
           "script": {{
             "source": "long now = new Date().getTime(); long t = doc[params.f].value; double ageMs = Math.max(0, now - t); double halfLifeMs = params.h * 86400000.0; return Math.exp(-0.69314718056 * ageMs / halfLifeMs);",
             "params": {{ "f": "<numeric_time_field>", "h": 90 }}
           }}
         }},
         "weight": 1.5
       }} ]
     - Optionally add a mild field_value_factor on the same numeric time field:
       {{ "field_value_factor": {{ "field": "<numeric_time_field>", "modifier": "log1p", "missing": 0 }} }}
- You MAY combine multiple functions in `function_score` with "score_mode":"sum" and "boost_mode":"multiply".
- If the user explicitly asks for deterministic ordering ("most viewed", "alphabetical", "break ties by newest"), provide "sort" and set "track_scores": true.
  - Note: any non-"_score" sort can make "max_score": null — acceptable only when explicitly requested.

### Sortable Field Guard (for ANY "sort" you output)
- **NEVER sort on a `text` field.** Sort only on fields with doc values: `keyword`, `date`, `numeric`, or `boolean`.
- For **date/recency tie-breakers**, choose the first available in this order:
  1) `created_at` if mapping type is `date`
  2) `updated_at` if mapping type is `date`
  3) `createdTs` if mapping type is `long`/numeric
  4) As a last resort, add `runtime_mappings` to derive a sortable date (e.g., `created_at_rt`) parsed from a string field in `_source`,
     then sort on that runtime field.
- Example runtime date for a string `"yyyy-MM-dd HH:mm:ss"`:
  "runtime_mappings": {{
    "created_at_rt": {{
      "type": "date",
      "script": {{
        "source": "def v = params._source['created_at']; if (v != null) {{ def fmt = new java.text.SimpleDateFormat('yyyy-MM-dd HH:mm:ss'); fmt.setTimeZone(java.util.TimeZone.getTimeZone('UTC')); emit(fmt.parse(v).getTime()); }}"
      }}
    }}
  }}
  and then sort on `"created_at_rt": {{"order":"desc"}}`.

### Filters & Ranges
- **Exclude drafts** via exact keyword: {{ "term": {{ "status.keyword": "draft" }} }} (only if the field exists).
- **Published**: {{ "term": {{ "is_published": true }} }} (only if the field exists).
- **Date ranges**:
  - Use date math (e.g., "now-30d/d") **only on date-typed fields**.
  - If only numeric time fields exist, **do not** use "now-…". Prefer the script-based freshness above and topical filters.
- Numeric ranges: use "range" on numeric fields (likes, views, engagement_score, followers, etc.).
- For topical multi-intent, use bool.should with minimum_should_match: 1.

### Collapse (one per group)
- If the user asks for “one per author/…”, use:
  "collapse": {{ "field": "<group_field>.keyword" }}
- Do **NOT** add top-level "sort" for collapse unless explicitly requested; let "_score" pick the top doc per group.

### Ambiguity
- If clearly about people/metrics (followers, engagement), prefer "blog-users".
- Otherwise default to "blog-articles" for topical/content searches.

### Strictness
- Return minimal but sufficient JSON. No comments, no trailing commas, no markdown.

## Few-shot Examples (mapping-safe)

### 1) Deterministic ordering with safe tie-breaker (DATE exists)
User: "Surface the most viewed vision transformer posts; break ties by newest first."
Output:
{{
  "index": "blog-articles",
  "track_total_hits": true,
  "query": {{
    "bool": {{
      "must": [
        {{
          "multi_match": {{
            "query": "vision transformer",
            "fields": ["title^3","summary^2","content","searchable_content","author_name"],
            "type": "most_fields"
          }}
        }}
      ]
    }}
  }},
  "sort": [{{ "views": {{ "order": "desc" }} }}, {{ "created_at": {{ "order": "desc" }} }}],
  "track_scores": true
}}

### 2) Deterministic ordering when only numeric timestamp exists (no date fields)
User: "Surface the most viewed vision transformer posts; break ties by newest first."
Output:
{{
  "index": "blog-articles",
  "track_total_hits": true,
  "query": {{
    "bool": {{
      "must": [
        {{
          "multi_match": {{
            "query": "vision transformer",
            "fields": ["title^3","summary^2","content","searchable_content","author_name"],
            "type": "most_fields"
          }}
        }}
      ]
    }}
  }},
  "sort": [{{ "views": {{ "order": "desc" }} }}, {{ "createdTs": {{ "order": "desc" }} }}],
  "track_scores": true
}}

### 3) Deterministic ordering when date is stored as string (derive runtime date)
User: "Surface the most viewed vision transformer posts; break ties by newest first."
Output:
{{
  "index": "blog-articles",
  "track_total_hits": true,
  "runtime_mappings": {{
    "created_at_rt": {{
      "type": "date",
      "script": {{
        "source": "def v = params._source['created_at']; if (v != null) {{ def fmt = new java.text.SimpleDateFormat('yyyy-MM-dd HH:mm:ss'); fmt.setTimeZone(java.util.TimeZone.getTimeZone('UTC')); emit(fmt.parse(v).getTime()); }}"
      }}
    }}
  }},
  "query": {{
    "bool": {{
      "must": [
        {{
          "multi_match": {{
            "query": "vision transformer",
            "fields": ["title^3","summary^2","content","searchable_content","author_name"],
            "type": "most_fields"
          }}
        }}
      ]
    }}
  }},
  "sort": [{{ "views": {{ "order": "desc" }} }}, {{ "created_at_rt": {{ "order": "desc" }} }}],
  "track_scores": true
}}

### 4) Articles: topical + date range (DATE field exists) + freshness blended; no explicit sort
User: "I want to find articles about Transformers from 2023 to 2025"
Output:
{{
  "index": "blog-articles",
  "track_total_hits": true,
  "query": {{
    "function_score": {{
      "query": {{
        "bool": {{
          "must": [
            {{
              "multi_match": {{
                "query": "Transformers",
                "fields": ["title^3","summary^2","content","searchable_content","author_name"]
              }}
            }},
            {{
              "range": {{
                "created_at": {{
                  "gte": "2023-01-01",
                  "lte": "2025-12-31"
                }}
              }}
            }},
            {{ "term": {{ "is_published": true }} }}
          ]
        }}
      }},
      "score_mode": "sum",
      "boost_mode": "multiply",
      "functions": [
        {{
          "gauss": {{
            "created_at": {{
              "origin": "now",
              "scale": "365d",
              "decay": 0.5
            }}
          }},
          "weight": 1.5
        }}
      ]
    }}
  }}
}}

### 5) Articles: typo-tolerant last 30 days + exclude drafts (DATE exists); no sort
User: "recent mlti agnt posts (last 30 days) but not drafts"
Output:
{{
  "index": "blog-articles",
  "track_total_hits": true,
  "query": {{
    "function_score": {{
      "query": {{
        "bool": {{
          "must": [
            {{
              "multi_match": {{
                "query": "mlti agnt",
                "fields": ["title^3","summary^2","content","searchable_content","author_name"],
                "type": "most_fields",
                "fuzziness": "AUTO"
              }}
            }},
            {{ "range": {{ "created_at": {{ "gte": "now-30d/d" }} }} }}
          ],
          "must_not": [
            {{ "term": {{ "status.keyword": "draft" }} }}
          ]
        }}
      }},
      "score_mode": "sum",
      "boost_mode": "multiply",
      "functions": [
        {{
          "gauss": {{
            "created_at": {{
              "origin": "now",
              "scale": "30d",
              "decay": 0.5
            }}
          }},
          "weight": 2.0
        }}
      ]
    }}
  }}
}}

### 6) Articles: one freshest per author about dense retrieval OR sentence embeddings; exclude drafts (numeric-safe freshness)
User: "Return one freshest article per author about dense retrieval or sentence embeddings; exclude drafts."
Output:
{{
  "index": "blog-articles",
  "track_total_hits": true,
  "query": {{
    "function_score": {{
      "query": {{
        "bool": {{
          "should": [
            {{
              "multi_match": {{
                "query": "dense retrieval",
                "fields": ["title^3","summary^2","content","searchable_content","author_name"],
                "type": "most_fields"
              }}
            }},
            {{
              "multi_match": {{
                "query": "sentence embeddings",
                "fields": ["title^3","summary^2","content","searchable_content","author_name"],
                "type": "most_fields"
              }}
            }}
          ],
          "minimum_should_match": 1,
          "must_not": [
            {{ "term": {{ "status.keyword": "draft" }} }}
          ]
        }}
      }},
      "score_mode": "sum",
      "boost_mode": "multiply",
      "functions": [
        {{
          "script_score": {{
            "script": {{
              "source": "long now = new Date().getTime(); long t = doc[params.f].value; double ageMs = Math.max(0, now - t); double halfLifeMs = params.h * 86400000.0; return Math.exp(-0.69314718056 * ageMs / halfLifeMs);",
              "params": {{ "f": "createdTs", "h": 180 }}
            }}
          }},
          "weight": 1.5
        }}
      ]
    }}
  }},
  "collapse": {{ "field": "author_name.keyword" }}
}}

### 7) Users: top followers, active this year (deterministic ordering)
User: "Top users by followers active this year"
Output:
{{
  "index": "blog-users",
  "track_total_hits": true,
  "query": {{
    "bool": {{
      "must": [
        {{ "range": {{ "created_at": {{ "gte": "now-365d/d" }} }} }}
      ]
    }}
  }},
  "sort": [{{ "followers": {{ "order": "desc" }} }}, {{ "engagement_score": {{ "order": "desc" }} }}],
  "track_scores": true
}}

Now convert this user query to the specified JSON:
User: "{query}"
"""


# Result Processing Prompt
RESULT_PROCESSING_PROMPT = """
You are an expert data analyst specializing in blog analytics. Your task is to analyze Elasticsearch search results and provide comprehensive, insightful answers to user queries.

**Chain of Thought Process:**
1. **Understand Query**: What did the user want to know?
2. **Analyze Results**: What patterns and insights can be extracted?
3. **Synthesize Information**: How do results answer the query?
4. **Provide Context**: What additional insights are valuable?
5. **Structure Response**: Present findings clearly and actionably

**Analysis Guidelines:**
- Always mention the number of results found
- Highlight key patterns and trends
- Provide specific examples from the data
- Suggest related insights or follow-up queries
- Use clear, non-technical language for business users

**Example Analysis:**

Original Query: "Find popular articles about python"
Results: 2 articles found
Raw Data: [
  {{"title": "Python Best Practices", "author_name": "Alice", "likes": 150, "views": 1200, "popularity_score": 420}},
  {{"title": "FastAPI Tutorial", "author_name": "Bob", "likes": 89, "views": 800, "popularity_score": 258}}
]

Analysis:
I found 2 popular Python articles in your blog system. Here are the key insights:

**Top Performers:**
- 'Python Best Practices' by Alice is your most popular Python content with 150 likes and 420 popularity score
- 'FastAPI Tutorial' by Bob also performs well with 89 likes and strong engagement

**Patterns:**
- Python content shows strong engagement with an average of 119 likes per article
- These articles have high view-to-like conversion rates, indicating quality content
- Alice and Bob are your top Python content creators

**Recommendations:**
- Consider having Alice and Bob collaborate on more Python content
- The 'Best Practices' format seems to resonate well with your audience
- You might want to explore more FastAPI content given its strong performance

Now analyze these results:

Original Query: "{original_query}"
Search Results: {results}
Number of Results: {result_count}

**IMPORTANT: Provide your analysis in plain text format only. Do not use quotes around your response, do not return JSON, and do not use markdown code blocks. Write a natural, conversational analysis that directly answers the user's query.**

Provide a comprehensive analysis following the Chain of Thought process above.
"""

# System Configuration
LLM_CONFIG = {
    "temperature": 0.1,       # Low temperature for consistent, focused responses
    "max_tokens": 1024,
    "model": "gpt-4o-mini",   # Will be overridden by deployment name
}

# Error Messages
ERROR_MESSAGES = {
    "query_refinement_failed": "I couldn't understand your query. Please try rephrasing it or provide more specific details about what you're looking for.",
    "no_results": "No results were found for your query. Try broadening your search terms or checking for typos.",
    "elasticsearch_error": "There was an issue searching the database. Please try again or contact support.",
    "llm_error": "I encountered an issue processing your request. Please try again with a simpler query."
}
