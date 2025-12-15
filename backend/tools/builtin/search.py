"""
Search tools for CMR Bot primary agent.

Includes web search and webpage fetching capabilities.
"""

import logging
from typing import Dict, Any
from sqlalchemy.orm import Session

from tools.registry import ToolConfig, ToolResult, register_tool
from tools.executor import run_async

logger = logging.getLogger(__name__)


# =============================================================================
# Web Search Tool
# =============================================================================

def execute_web_search(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Execute a web search using the search service."""
    from services.search_service import SearchService, SearchQuotaExceededError, SearchAPIError

    query = params.get("query", "")
    num_results = params.get("num_results", 5)

    if not query:
        return ToolResult(text="Error: No search query provided")

    try:
        search_service = SearchService()
        if not search_service.initialized:
            search_service.initialize()

        result = run_async(
            search_service.search(search_term=query, num_results=num_results)
        )

        # Format results for LLM
        search_results = result.get("search_results", [])
        if not search_results:
            return ToolResult(text=f"No results found for: {query}")

        # Check if we fell back to a different engine
        fallback_note = ""
        metadata = result.get("metadata")
        if metadata and metadata.get("fallback_reason"):
            fallback_note = f"\n(Note: Used fallback search due to {metadata['fallback_reason']})\n\n"

        formatted = f"Search results for '{query}':{fallback_note}\n"
        for i, item in enumerate(search_results, 1):
            formatted += f"{i}. **{item.title}**\n"
            formatted += f"   URL: {item.url}\n"
            if item.snippet:
                formatted += f"   {item.snippet}\n"
            formatted += "\n"

        return ToolResult(
            text=formatted,
            data={
                "type": "search_results",
                "query": query,
                "results": [
                    {"title": r.title, "url": r.url, "snippet": r.snippet}
                    for r in search_results
                ],
                "fallback_used": metadata.get("fallback_reason") if metadata else None
            }
        )

    except SearchQuotaExceededError as e:
        logger.warning(f"Search quota exceeded: {e}")
        return ToolResult(text="Search quota exceeded. The search API limit has been reached. Please try again later or use fewer searches.")
    except SearchAPIError as e:
        logger.error(f"Search API error: {e}")
        return ToolResult(text=f"Search failed: {str(e)}")
    except Exception as e:
        logger.error(f"Web search error: {e}", exc_info=True)
        return ToolResult(text=f"Search failed: {str(e)}")


WEB_SEARCH_TOOL = ToolConfig(
    name="web_search",
    description="Search the web for information. Use this to find current information, research topics, or answer questions that require up-to-date knowledge.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return (default: 5, max: 10)",
                "default": 5
            }
        },
        "required": ["query"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "search_results"},
            "query": {"type": "string", "description": "The search query that was executed"},
            "results": {
                "type": "array",
                "description": "List of search results",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Page title"},
                        "url": {"type": "string", "description": "Page URL"},
                        "snippet": {"type": ["string", "null"], "description": "Text snippet from the page"}
                    },
                    "required": ["title", "url"]
                }
            },
            "fallback_used": {"type": ["string", "null"], "description": "Reason if fallback search engine was used"}
        },
        "required": ["type", "query", "results"]
    },
    executor=execute_web_search,
    category="search"
)


# =============================================================================
# Web Page Fetch Tool
# =============================================================================

def execute_fetch_webpage(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> ToolResult:
    """Fetch and extract content from a webpage."""
    from services.web_retrieval_service import WebRetrievalService

    url = params.get("url", "")

    if not url:
        return ToolResult(text="Error: No URL provided")

    try:
        service = WebRetrievalService()

        result = run_async(
            service.retrieve_webpage(url=url, extract_text_only=True)
        )

        webpage = result["webpage"]
        content = webpage.content[:8000]  # Limit content length
        if len(webpage.content) > 8000:
            content += "\n\n[Content truncated...]"

        formatted = f"**{webpage.title}**\n"
        formatted += f"URL: {url}\n\n"
        formatted += content

        return ToolResult(
            text=formatted,
            data={
                "type": "webpage_content",
                "url": url,
                "title": webpage.title,
                "content_length": len(webpage.content)
            }
        )

    except Exception as e:
        logger.error(f"Webpage fetch error: {e}", exc_info=True)
        return ToolResult(text=f"Failed to fetch webpage: {str(e)}")


FETCH_WEBPAGE_TOOL = ToolConfig(
    name="fetch_webpage",
    description="Fetch and read the content of a webpage. Use this to get detailed information from a specific URL.",
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to fetch"
            }
        },
        "required": ["url"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "type": {"type": "string", "const": "webpage_content"},
            "url": {"type": "string", "description": "The URL that was fetched"},
            "title": {"type": "string", "description": "Page title"},
            "content_length": {"type": "integer", "description": "Total length of page content in characters"}
        },
        "required": ["type", "url", "title", "content_length"]
    },
    executor=execute_fetch_webpage,
    category="search"
)


# =============================================================================
# Tool Registration
# =============================================================================

def register_search_tools():
    """Register all search tools."""
    register_tool(WEB_SEARCH_TOOL)
    register_tool(FETCH_WEBPAGE_TOOL)
    logger.info("Registered 2 search tools")
