"""
Elasticsearch Search Service

This service provides a clean interface for searching Elasticsearch indices
with proper error handling and result formatting.
"""

from typing import Dict, Any, List, Optional
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError, NotFoundError, ConnectionError

from utils.logger import get_logger


class SearchService:
    """
    Service for executing Elasticsearch searches with clean error handling.
    
    This service abstracts Elasticsearch operations and provides a simple
    interface for the FastAPI application.
    """
    
    def __init__(self, elasticsearch_url: str = "http://localhost:9200"):
        """Initialize the search service."""
        self.elasticsearch_url = elasticsearch_url
        self._es_client = None
        self.logger = get_logger()
    
    @property
    def es_client(self) -> Elasticsearch:
        """Get or create Elasticsearch client."""
        if self._es_client is None:
            try:
                self._es_client = Elasticsearch(
                    self.elasticsearch_url,
                    request_timeout=30,
                    headers={'Accept': 'application/json', 'Content-Type': 'application/json'}
                )
                self._es_client.ping()
                self.logger.info(f"Connected to Elasticsearch at {self.elasticsearch_url}")
            except ConnectionError as e:
                self.logger.error(f"Failed to connect to Elasticsearch: {e}")
                raise
        return self._es_client
    
    # -----------------------
    # Core query entry points
    # -----------------------
    
    def search(self, index: str, query: Dict[str, Any], size: int = 10) -> Dict[str, Any]:
        """
        Execute a search query against Elasticsearch.
        
        Args:
            index: The index to search
            query: The Elasticsearch query DSL
            size: Maximum number of results to return
            
        Returns:
            Dict containing search results and metadata
        """
        try:
            # OLD
            # self.logger.info(f"=== ELASTICSEARCH SEARCH DEBUG ===")
            # self.logger.info(f"Index: '{index}'")
            # self.logger.info(f"Query: {query}")
            # self.logger.info(f"Size: {size}")
            
            # response = self.es_client.search(
            #     index=index,
            #     body=query,
            #     size=size
            # )

            # self.logger.info(f"Raw ES response keys: {list(response.keys())}")
            # self.logger.info(f"Total hits: {response.get('hits', {}).get('total', {}).get('value', 0)}")
            # self.logger.info(f"Max score: {response.get('hits', {}).get('max_score')}")
            # self.logger.info(f"Number of hits returned: {len(response.get('hits', {}).get('hits', []))}")

            # # Format response
            # results = {
            #     'total_hits': response['hits']['total']['value'],
            #     'max_score': response['hits']['max_score'],
            #     'results': [hit['_source'] for hit in response['hits']['hits']],
            #     'raw_hits': response['hits']['hits']  # Include for debugging
            # }
            
            # self.logger.info(f"Formatted results keys: {list(results.keys())}")
            # self.logger.info(f"Number of results: {len(results['results'])}")
            # self.logger.info(f"Search completed: {results['total_hits']} results found")
            # return results
            
            # NEW: 13/08/2025: 23:14
            self.logger.info("=== ELASTICSEARCH SEARCH DEBUG ===")
            self.logger.info(f"Index: {index!r}")
            self.logger.info(f"Incoming size arg: {size}")
            self.logger.info(f"Incoming body keys: {list(query.keys())}")

            # Ensure sensible defaults but do not stomp explicit values in the body
            body = dict(query)  # shallow copy to avoid side effects
            body.setdefault("track_total_hits", True)
            # Only set size if caller didn’t pass it inside body
            if "size" not in body:
                body_size = size
            else:
                body_size = body["size"]

            response = self.es_client.search(index=index, body=body, size=body_size)

            hits_obj = response.get("hits", {}) or {}
            hits = hits_obj.get("hits", []) or []
            total_hits = (hits_obj.get("total") or {}).get("value", 0)
            max_score = hits_obj.get("max_score")

            # Format results (preserve _source shape + attach __meta)
            formatted_results: List[Dict[str, Any]] = []
            for h in hits:
                src = dict(h.get("_source", {}) or {})
                # Safe, non-colliding metadata bag
                src["__meta"] = {
                    "id": h.get("_id"),
                    "index": h.get("_index"),
                    "score": h.get("_score"),
                    "highlight": h.get("highlight"),
                    "sort": h.get("sort"),
                }
                formatted_results.append(src)

            results: Dict[str, Any] = {
                "total_hits": total_hits,
                "max_score": max_score,
                "took": response.get("took"),
                "timed_out": response.get("timed_out"),
                "_shards": response.get("_shards"),
                "results": formatted_results,
                "raw_hits": hits,  # keep for debugging
            }

            self.logger.info(f"Total hits: {total_hits} | Returned: {len(formatted_results)} | Max score: {max_score}")
            return results
            
        except RequestError as e:
            self.logger.error(f"Elasticsearch request error: {e}")
            raise ValueError(f"Invalid search query: {e}")
        except NotFoundError as e:
            self.logger.error(f"Index not found: {e}")
            raise ValueError(f"Index '{index}' not found")
        except Exception as e:
            self.logger.error(f"Unexpected search error: {e}")
            raise RuntimeError(f"Search failed: {e}")
        
    # -----------------------
    # Utilities
    # -----------------------
    
    def get_indices_info(self) -> Dict[str, Any]:
        """
        Get information about available indices.
        
        Returns:
            Dict containing index information
        """
        try:
            # Get indices that match our blog pattern
            indices = self.es_client.indices.get(index="blog-*")
            
            info = {}
            for index_name, index_data in indices.items():
                # Get document count
                count_response = self.es_client.count(index=index_name)
                
                info[index_name] = {
                    'document_count': count_response['count'],
                    'mappings': index_data.get('mappings', {}),
                    'settings': index_data.get('settings', {})
                }
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get indices info: {e}")
            return {}
    
    def validate_query(self, index: Optional[str], body: Dict[str, Any]) -> bool:
        """Validate an Elasticsearch query without executing it.

        Args:
            index (Optional[str]): The index to validate against
            body (Dict[str, Any]): The query body to validate

        Returns:
            bool: True if the query is valid, False otherwise
        """
        try:
            # Extract just the query clause
            q = body.get("query", body)  # supports either {"query": {...}} or just {...}
            resp = self.es_client.indices.validate_query(
                index=index,
                explain=True,
                query=q
            )
            return resp.get("valid", False)
        except Exception as e:
            self.logger.error(f"Query validation failed: {e}")
            return False
    
    def search_users(self, query: Dict[str, Any], size: int = 10) -> Dict[str, Any]:
        """Search the users index."""
        return self.search("blog-users", query, size)
    
    def search_articles(self, query: Dict[str, Any], size: int = 10) -> Dict[str, Any]:
        """Search the articles index."""
        return self.search("blog-articles", query, size)
    
    def multi_search(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute multiple searches in a single request.
        
        Args:
            queries: List of query dictionaries, each containing 'index' and 'query'
            
        Returns:
            List of search results
        """
        try:
            # OLD
            # # Prepare multi-search body
            # body = []
            # for q in queries:
            #     body.append({'index': q['index']})
            #     body.append(q['query'])
            
            # response = self.es_client.msearch(body=body)
            
            # results = []
            # for resp in response['responses']:
            #     if 'error' in resp:
            #         results.append({'error': resp['error']})
            #     else:
            #         results.append({
            #             'total_hits': resp['hits']['total']['value'],
            #             'results': [hit['_source'] for hit in resp['hits']['hits']]
            #         })
            
            # return results

            # NEW: 13/08/25 - 23:17
            body = []
            for q in queries:
                idx = q["index"]
                b = dict(q.get("query", {}))
                b.setdefault("track_total_hits", True)
                size = q.get("size", 10)

                body.append({"index": idx})
                if "size" not in b:
                    b["size"] = size
                body.append(b)

            resp = self.es_client.msearch(body=body)

            out: List[Dict[str, Any]] = []
            for r in resp.get("responses", []):
                if "error" in r:
                    out.append({"error": r["error"]})
                    continue
                hits_obj = r.get("hits", {}) or {}
                hits = hits_obj.get("hits", []) or []
                total_hits = (hits_obj.get("total") or {}).get("value", 0)

                formatted: List[Dict[str, Any]] = []
                for h in hits:
                    src = dict(h.get("_source", {}) or {})
                    src["__meta"] = {
                        "id": h.get("_id"),
                        "index": h.get("_index"),
                        "score": h.get("_score"),
                        "highlight": h.get("highlight"),
                        "sort": h.get("sort"),
                    }
                    formatted.append(src)

                out.append({
                    "total_hits": total_hits,
                    "results": formatted,
                })

            return out
            
        except Exception as e:
            self.logger.error(f"Multi-search failed: {e}")
            raise RuntimeError(f"Multi-search failed: {e}")


