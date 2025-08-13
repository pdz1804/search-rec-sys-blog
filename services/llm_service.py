# services/llm_service.py
"""
LLM Service for Query Refinement and Result Processing.

This module provides a small, focused service class to:
  1) Convert natural-language queries to Elasticsearch DSL (mapping-aware).
  2) Summarize/interpret search results for end users.

Design goals:
  - Clean, readable, and easy to re-check later.
  - Minimal moving parts; clear separation of concerns.
  - Mapping-aware prompting (inject real fields into the prompt).
  - Light, safe normalization (defaults + common alias fix) without complex rewriting.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional

from dataclasses import dataclass
from dotenv import load_dotenv
from openai import AzureOpenAI

from config.prompts import (
    QUERY_REFINEMENT_PROMPT_TMPL,   # << use the new template with {index_cheatsheet}
    RESULT_PROCESSING_PROMPT,
    LLM_CONFIG,
    ERROR_MESSAGES,
)
from utils.logger import get_logger

load_dotenv()

# Indices we allow the model to target
ALLOWED_INDICES = {"blog-articles", "blog-users"}

# ----------------------------
# Mapping helpers (lightweight)
# ----------------------------

@dataclass
class MappingView:
    """
    Shallow view over an ES mapping.

    Attributes:
        fields: Flattened {field_name: type}
        preferred_date_field: date field for human date ranges (e.g., "created_at")
        preferred_sort_field: freshest chronological field (e.g., "createdTs" or fallback to date)
    """
    fields: Dict[str, str]
    preferred_date_field: Optional[str]
    preferred_sort_field: Optional[str]

    @classmethod
    def from_file(cls, path: str) -> "MappingView":
        """Load mapping JSON, flatten top-level properties, and pick date/sort fields."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        except Exception:
            mapping = {}

        props = (mapping.get("mappings") or {}).get("properties") or {}
        flat: Dict[str, str] = {}

        def walk(prefix: str, node: Dict[str, Any]) -> None:
            for k, v in node.items():
                if "properties" in v:
                    walk(f"{prefix}{k}.", v["properties"])
                else:
                    t = v.get("type")
                    if t:
                        flat[(prefix + k)] = t

        walk("", props)

        # Prefer created_at for date ranges if exists; else updated_at
        date_field = None
        for cand in ["created_at", "updated_at"]:
            if flat.get(cand) == "date":
                date_field = cand
                break

        # Prefer createdTs (long) for sort freshness; else created_at; else updated_at
        sort_field = None
        if flat.get("createdTs") == "long":
            sort_field = "createdTs"
        elif flat.get("created_at") == "date":
            sort_field = "created_at"
        elif flat.get("updated_at") == "date":
            sort_field = "updated_at"

        return cls(fields=flat, preferred_date_field=date_field, preferred_sort_field=sort_field)

    def cheatsheet(self, index_name: str) -> str:
        """Compact row for prompt; orders common fields first, then alphabetical."""
        preferred_order = [
            "title", "summary", "content", "searchable_content", "author_name", "author_name.keyword",
            "tags", "status", "is_published",
            "createdTs", "created_at", "updated_at",
            "likes", "dislikes", "views",
            "content_length", "summary_length", "engagement_ratio", "tag_count",
            "full_name", "full_name.keyword", "email", "role",
            "engagement_score", "followers", "total_followers", "total_likes", "total_dislikes",
            "total_bookmarks", "total_following",
            "id"
        ]
        # Add .keyword subs if exist
        if "title" in self.fields:
            self.fields.setdefault("title.keyword", "keyword")
        if "author_name" in self.fields:
            self.fields.setdefault("author_name.keyword", "keyword")
        if "full_name" in self.fields:
            self.fields.setdefault("full_name.keyword", "keyword")

        ordered = sorted(
            self.fields.items(),
            key=lambda kv: (preferred_order.index(kv[0]) if kv[0] in preferred_order else 9999, kv[0])
        )
        preview = ", ".join([f"{k} [{t}]" for k, t in ordered])
        return f"{index_name} (fields: {preview})"

class LLMService:
    """
    Service for interacting with Azure OpenAI for:
      1) Query refinement (NL → Elasticsearch DSL).
      2) Result processing (LLM-written user-friendly analysis).

    Key ideas:
      - We build a mapping-aware prompt by injecting a concise field cheatsheet.
      - We ask the model to return JSON only (prefer response_format=json_object).
      - We apply minimal post-processing to add safe defaults and fix common aliases.
    """

    # ---- Lifecycle ---------------------------------------------------------
    
    def __init__(self):
        """Initialize the LLM service with Azure OpenAI configuration."""
        self.logger = get_logger()
        
        # Load configuration from environment
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.deployment = os.getenv("AZURE_OPENAI_COMPLETION_DEPLOYMENT")
        
        # Validate configuration
        if not all([self.api_key, self.endpoint, self.deployment]):
            raise ValueError("Missing Azure OpenAI configuration. Please check your .env file.")
        
        # Initialize client
        try:
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_endpoint=self.endpoint
            )
            self.logger.info("LLM service initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM service: {e}")
            raise
        
        mappings_dir = os.getenv("ES_MAPPINGS_DIR", "es")
        self.articles = MappingView.from_file(os.path.join(mappings_dir, "articles_mapping.json"))
        self.users    = MappingView.from_file(os.path.join(mappings_dir, "users_mapping.json"))

    # ---------------- Public API --------------------------------------------
    
    def refine_query(self, natural_query: str) -> Optional[Dict[str, Any]]:
        """
        NL → Elasticsearch Search API request.

        Steps:
          1) Build mapping-aware prompt (cheatsheet from live mappings).
          2) Ask for strict JSON; fallback to text parsing if needed.
          3) Minimal normalization: defaults, index guess, alias fix, default sort choice.
        
        Args:
            natural_query: User's natural language query
            
        Returns:
            Elasticsearch query dictionary or None if refinement fails
        """
        try:
            self.logger.info(f"Refining query: '{natural_query}'")
            
            cheatsheet = "\n".join([
                self.articles.cheatsheet("blog-articles"),
                self.users.cheatsheet("blog-users"),
            ])
            prompt = QUERY_REFINEMENT_PROMPT_TMPL.format(
                index_cheatsheet=cheatsheet,
                query=natural_query,
            )

            refined = self._call_llm_json_only(prompt)

            if refined:
                self.logger.info(f"Query refined successfully: {refined.get('index', 'unknown')}")
                return refined
            
        except Exception as e:
            self.logger.error(f"Query refinement failed: {e}")
            return None
    
    def process_results(self, original_query: str, search_results: Dict[str, Any]) -> str:
        """
        Process search results into human-readable insights.
        
        Args:
            original_query: The original user query
            search_results: Results from Elasticsearch
            
        Returns:
            Human-readable analysis of the results
        """
        try:
            self.logger.info(f"Processing results for query: '{original_query}'")
            
            # Prepare results data
            result_count = search_results.get('total_hits', 0)
            results = search_results.get('results', [])
            
            # Handle empty results
            if result_count == 0:
                return ERROR_MESSAGES["no_results"]
            
            # Clean and prepare results for the prompt
            cleaned_results = []
            for result in results[:5]:  # Limit to top 5 for context
                # Create a clean copy with only essential fields
                cleaned_result = {}
                for key, value in result.items():
                    if isinstance(value, str):
                        # Truncate long strings to avoid prompt issues
                        cleaned_result[key] = value[:200] if len(value) > 200 else value
                    elif isinstance(value, (int, float, bool)):
                        cleaned_result[key] = value
                    elif isinstance(value, list):
                        # Handle lists (like tags) safely
                        if all(isinstance(item, str) for item in value):
                            cleaned_result[key] = [item[:100] for item in value[:10]]  # Limit list items
                        else:
                            cleaned_result[key] = str(value)[:100]  # Convert to string and truncate
                    else:
                        # Convert other types to string and truncate
                        cleaned_result[key] = str(value)[:100]
                cleaned_results.append(cleaned_result)
            
            # Log the cleaned results for debugging
            self.logger.info(f"Cleaned results for LLM: {cleaned_results}")
            
            # Prepare prompt with safe JSON
            try:
                results_json = json.dumps(cleaned_results, indent=2, ensure_ascii=False)
                self.logger.info(f"JSON prepared for prompt: {results_json[:500]}...")
            except Exception as json_error:
                self.logger.error(f"Failed to serialize results to JSON: {json_error}")
                # Fallback: use string representation
                results_json = str(cleaned_results)[:1000]
            
            prompt = RESULT_PROCESSING_PROMPT.format(
                original_query=original_query,
                results=results_json,
                result_count=result_count
            )
            
            # Call Azure OpenAI
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are an expert data analyst specializing in blog analytics."},
                    {"role": "user", "content": prompt}
                ],
                temperature=LLM_CONFIG["temperature"],
                max_tokens=LLM_CONFIG["max_tokens"]
            )
            
            # Extract and clean the response
            analysis = response.choices[0].message.content.strip()
            
            # Log the raw response for debugging
            self.logger.info(f"=== LLM ANALYSIS RESPONSE DEBUG ===")
            self.logger.info(f"Raw LLM analysis response length: {len(analysis)}")
            self.logger.info(f"Raw LLM analysis response: '{analysis}'")
            self.logger.info(f"Response starts with quote: {analysis.startswith('"')}")
            self.logger.info(f"Response ends with quote: {analysis.endswith('"')}")
            self.logger.info(f"Contains 'title': {'title' in analysis}")
            self.logger.info(f"Contains '\"title\"': {'\"title\"' in analysis}")
            
            # Clean up any malformed quotes or JSON artifacts
            if analysis.startswith('"') and analysis.endswith('"'):
                # Remove surrounding quotes
                analysis = analysis[1:-1]
                self.logger.info("Removed surrounding double quotes")
            elif analysis.startswith("'") and analysis.endswith("'"):
                # Remove surrounding single quotes
                analysis = analysis[1:-1]
                self.logger.info("Removed surrounding single quotes")
            
            # Clean up any remaining quote artifacts
            analysis = analysis.replace('""', '"').replace("''", "'")
            
            # Additional cleanup for common LLM artifacts
            analysis = analysis.replace('\\"', '"')  # Remove escaped quotes
            analysis = analysis.replace('\\n', '\n')  # Convert escaped newlines
            analysis = analysis.replace('\\t', '\t')  # Convert escaped tabs
            
            self.logger.info(f"Final cleaned analysis: '{analysis}'")
            self.logger.info("Results processed successfully")
            return analysis
            
        except Exception as e:
            self.logger.error(f"Result processing failed: {e}")
            self.logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            self.logger.error(f"Search results structure: {list(search_results.keys()) if isinstance(search_results, dict) else 'Not a dict'}")
            
            # Return a simple fallback analysis instead of error message
            try:
                result_count = search_results.get('total_hits', 0)
                results = search_results.get('results', [])
                if result_count > 0:
                    return f"Found {result_count} results for your query. LLM analysis unavailable due to processing error: {str(e)[:100]}"
                else:
                    return ERROR_MESSAGES["no_results"]
            except Exception as fallback_error:
                self.logger.error(f"Fallback analysis also failed: {fallback_error}")
                return ERROR_MESSAGES["llm_error"]
    
    def health_check(self) -> bool:
        """
        Check if the LLM service is healthy and can make API calls.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Simple test call
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            return bool(response.choices[0].message.content)
        except Exception as e:
            self.logger.error(f"LLM health check failed: {e}")
            return False

    # ---------------- Internals -----------------

    def _call_llm_json_only(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Prefer strict JSON via response_format; fallback to plain call + extraction.
        """
        # Preferred: JSON mode (if supported by your Azure model)
        try:
            resp = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are a careful, mapping-aware Elasticsearch query engineer."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=LLM_CONFIG.get("temperature", 0),
                max_tokens=LLM_CONFIG.get("max_tokens", 512),
            )
            raw = resp.choices[0].message.content or ""
            return json.loads(raw)
        except Exception as e:
            self.logger.info(f"JSON response_format failed or unsupported: {e}. Falling back to text parsing.")

        # Fallback: plain response + parse JSON block
        try:
            resp = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": "You are a careful, mapping-aware Elasticsearch query engineer."},
                    {"role": "user", "content": prompt},
                ],
                temperature=LLM_CONFIG.get("temperature", 0),
                max_tokens=LLM_CONFIG.get("max_tokens", 512),
            )
            text = (resp.choices[0].message.content or "").strip()
            return self._extract_json(text)
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Extract a JSON object from a text blob:
          - ```json fenced blocks
          - {{ ... }} double-curly
          - widest { ... } block
        """
        if not text:
            return None

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            candidate = text[start:end].strip()
            try:
                if candidate.startswith("{{") and candidate.endswith("}}"):
                    candidate = candidate.replace("{{", "{").replace("}}", "}")
                return json.loads(candidate)
            except Exception:
                pass

        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            candidate = text[start:end]
            if candidate.startswith("{{") and candidate.endswith("}}"):
                candidate = candidate.replace("{{", "{").replace("}}", "}")
            return json.loads(candidate)
        except Exception:
            return None

