"""
FastAPI application for Elasticsearch blog search with LLM integration.

This application provides REST endpoints for searching blog data with
natural language queries powered by Azure OpenAI.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import os
import json

from services.search_service import SearchService
from services.llm_service import LLMService
from utils.logger import get_logger

# Initialize logger
logger = get_logger()

# Test logging to see if it's working
print("=== TESTING LOGGER ===")
print(f"Logger level: {logger.level}")
print(f"Logger handlers: {len(logger.handlers)}")
for handler in logger.handlers:
    print(f"  Handler: {type(handler).__name__}, Level: {handler.level}")

logger.info("=== API SERVER STARTING ===")
logger.info("Debug logging enabled in API")
logger.info("Info logging enabled in API")
logger.warning("Warning logging enabled in API")

# Initialize services
search_service = SearchService()
llm_service = LLMService()

# Create FastAPI app
app = FastAPI(
    title="Blog Search API",
    description="Search blog articles and users with natural language queries powered by Azure OpenAI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class NaturalSearchRequest(BaseModel):
    """Request model for natural language search."""
    query: str
    size: Optional[int] = 10
    
    def pretty_print(self) -> str:
        return json.dumps(self.model_dump(), indent=2, ensure_ascii=False)


class SearchResponse(BaseModel):
    """Response model for search results."""
    success: bool
    query: str
    total_hits: int
    results: List[Dict[str, Any]]
    analysis: Optional[str] = None
    elasticsearch_query: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def pretty_print(self) -> str:
        return json.dumps(self.model_dump(), indent=2, ensure_ascii=False)


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str
    services: Dict[str, bool]
    indices: Dict[str, Any]
    
    def pretty_print(self) -> str:
        return json.dumps(self.model_dump(), indent=2, ensure_ascii=False)


# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    logger.info("Root endpoint accessed")
    logger.info("Debug message from root endpoint")
    return {
        "message": "Blog Search API with LLM Integration",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check services
        elasticsearch_healthy = True
        llm_healthy = llm_service.health_check()
        
        try:
            search_service.es_client.ping()
        except Exception:
            elasticsearch_healthy = False
        
        # Get indices info
        indices_info = search_service.get_indices_info()
        
        status = "healthy" if elasticsearch_healthy and llm_healthy else "degraded"
        
        response = HealthResponse(
            status=status,
            services={
                "elasticsearch": elasticsearch_healthy,
                "llm": llm_healthy
            },
            indices=indices_info
        )
        logger.info(response.pretty_print())
        return response
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")


@app.post("/search/natural", response_model=SearchResponse)
async def natural_search(request: NaturalSearchRequest):
    """
    Search with natural language query using LLM refinement.
    
    This endpoint:
    1. Takes a natural language query
    2. Uses LLM to convert it to Elasticsearch DSL
    3. Executes the search
    4. Uses LLM to analyze and present results
    """
    try:
        logger.info(f"=== NATURAL SEARCH API DEBUG ===")
        logger.info(f"Natural search request: '{request.query}'")
        logger.info(f"Request size: {request.size}")
        
        # Step 1: Refine query using LLM
        logger.info("Step 1: Starting LLM query refinement")
        refined_query = llm_service.refine_query(request.query)
        logger.info(f"LLM refinement result: {refined_query}")
        
        if not refined_query:
            logger.warning("LLM refinement failed, returning error response")
        
            response = SearchResponse(
                success=False,
                query=request.query,
                total_hits=0,
                results=[],
                error="Could not understand your query. Please try rephrasing it."
            )
            logger.info(response.pretty_print())
            return response
        
        # Extract index and query from refined result
        index = refined_query.get("index", "blog-articles")
        es_query = {k: v for k, v in refined_query.items() if k != "index"}
        
        logger.info(f"Extracted index: '{index}'")
        logger.info(f"Extracted ES query: {es_query}")
        
        # Step 2: Execute search
        logger.info("Step 2: Executing Elasticsearch search")
        search_results = search_service.search(index, es_query, request.size)
        logger.info(f"Search results summary: {search_results['total_hits']} hits")
        
        # Step 3: Process results with LLM
        logger.info("Step 3: Processing results with LLM")
        logger.info(f"Search results structure: {list(search_results.keys())}")
        logger.info(f"Results count: {len(search_results.get('results', []))}")
        logger.info(f"First result sample: {search_results.get('results', [])[:1]}")
        
        try:
            analysis = llm_service.process_results(request.query, search_results)
            logger.info(f"LLM analysis length: {len(analysis) if analysis else 0}")
        except Exception as analysis_error:
            logger.error(f"LLM analysis failed: {analysis_error}")
            analysis = f"Found {search_results['total_hits']} results. LLM analysis failed: {str(analysis_error)[:100]}"
        
        logger.info(f"Natural search completed successfully: {search_results['total_hits']} results")
        
        response = SearchResponse(
            success=True,
            query=request.query,
            total_hits=search_results["total_hits"],
            results=search_results["results"],
            analysis=analysis,
            elasticsearch_query=refined_query
        )
        logger.info(response.pretty_print())
        return response
        
    except ValueError as e:
        logger.error(f"Search validation error: {e}")
        response = SearchResponse(
            success=False,
            query=request.query,
            total_hits=0,
            results=[],
            error=str(e)
        )
        logger.info(response.pretty_print())
        return response
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.post("/search/elasticsearch", response_model=SearchResponse)
async def elasticsearch_search(
    index: str,
    query: Dict[str, Any],
    size: Optional[int] = 10
):
    """
    Direct Elasticsearch query endpoint for advanced users.
    
    Allows direct execution of Elasticsearch DSL queries.
    """
    try:
        logger.info(f"Direct Elasticsearch search on index: {index}")

        logger.info(f"Elasticsearch query: {query}")

        # validate only the inner query against the given index
        if not search_service.validate_query(index, query):
            response = SearchResponse(
                success=False,
                query=str(query),
                total_hits=0,
                results=[],
                error="Invalid Elasticsearch query"
            )
            logger.info(response.pretty_print())
            return response

        # prefer URL 'size' over body size to avoid duplication
        body = dict(query)
        if "size" in body:
            body.pop("size", None)

        # Execute search
        search_results = search_service.search(index, body, size)

        response = SearchResponse(
            success=True,
            query=str(query),
            total_hits=search_results["total_hits"],
            results=search_results["results"],
            elasticsearch_query=query
        )
        logger.info(response.pretty_print())
        return response

    except Exception as e:
        logger.error(f"Direct search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/indices", response_model=Dict[str, Any])
async def get_indices():
    """Get information about available indices."""
    try:
        return search_service.get_indices_info()
    except Exception as e:
        logger.error(f"Failed to get indices: {e}")
        raise HTTPException(status_code=500, detail="Failed to get indices information")


# Example queries endpoint for documentation
@app.get("/test-logging")
async def test_logging():
    """Test endpoint to verify logging is working."""
    logger.info("DEBUG: This is a debug message")
    logger.info("INFO: This is an info message")
    logger.warning("WARNING: This is a warning message")
    logger.error("ERROR: This is an error message")
    
    return {
        "message": "Logging test completed",
        "timestamp": "Check the logs to see if all log levels are working"
    }


@app.get("/examples", response_model=Dict[str, List[str]])
async def get_example_queries():
    """Get example natural language queries."""
    return {
        "user_queries": [
            "Find active users with high social influence",
            "Show me users who have bookmarked more than 5 articles",
            "List users with the most followers"
        ],
        "article_queries": [
            "Find popular articles about python",
            "Show me recent articles with high engagement",
            "Articles by John with more than 50 likes",
            "Find technical articles with long reading time"
        ],
        "mixed_queries": [
            "What are the most popular topics in our blog?",
            "Which authors write the most engaging content?",
            "Show me trending articles this month"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    
    # Test logging before starting server
    print("=== DIRECT API TEST ===")
    logger.info("Direct API debug test")
    logger.info("Direct API info test")
    logger.warning("Direct API warning test")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
