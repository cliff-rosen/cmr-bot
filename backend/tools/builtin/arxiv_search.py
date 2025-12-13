"""
arXiv Search Tool

Search arXiv preprint server for scientific papers.
Covers physics, mathematics, computer science, and more.
"""

import logging
from typing import Any, Dict, Generator
from sqlalchemy.orm import Session

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool

logger = logging.getLogger(__name__)

MAX_ARXIV_RESULTS = 25


def execute_arxiv_search(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Search arXiv for scientific papers.

    This is a streaming tool that yields progress updates.
    """
    from services.arxiv_service import ArxivService

    query = params.get("query", "")
    max_results = min(params.get("max_results", 10), MAX_ARXIV_RESULTS)
    sort_by = params.get("sort_by", "relevance")
    category = params.get("category")

    if not query:
        return ToolResult(text="Error: No search query provided")

    cancellation_token = context.get("cancellation_token")

    # Step 1: Initialize search
    yield ToolProgress(
        stage="searching",
        message=f"Searching arXiv for: {query}",
        data={"query": query, "max_results": max_results, "category": category},
        progress=0.1
    )

    if cancellation_token and cancellation_token.is_cancelled:
        return ToolResult(text="Search cancelled")

    try:
        service = ArxivService()

        # Step 2: Execute search
        yield ToolProgress(
            stage="fetching",
            message="Fetching papers from arXiv...",
            data={},
            progress=0.3
        )

        articles, metadata = service.search(
            query=query,
            max_results=max_results,
            sort_by=sort_by,
            category=category
        )

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(text="Search cancelled")

        total_results = metadata.get("total_results", 0)

        yield ToolProgress(
            stage="processing",
            message=f"Found {total_results} total results, processing {len(articles)} papers",
            data={
                "total_results": total_results,
                "returned": len(articles)
            },
            progress=0.7
        )

        if not articles:
            yield ToolProgress(
                stage="complete",
                message="No results found",
                data={},
                progress=1.0
            )
            return ToolResult(
                text=f"No arXiv papers found for: {query}",
                data={"success": False, "reason": "no_results", "query": query}
            )

        # Step 3: Format results
        yield ToolProgress(
            stage="formatting",
            message="Formatting results...",
            data={},
            progress=0.9
        )

        # Build formatted output
        formatted = f"**arXiv Search Results for '{query}'**\n"
        formatted += f"Found {total_results} total results, showing {len(articles)}\n\n"

        article_data = []
        for i, article in enumerate(articles, 1):
            # Build author string
            authors = article.authors[:3] if article.authors else []
            author_str = ", ".join(authors)
            if article.authors and len(article.authors) > 3:
                author_str += " et al."

            # Get arxiv ID and category from metadata
            arxiv_id = article.metadata.get("arxiv_id", "") if article.metadata else ""
            category_name = article.metadata.get("category_name", "") if article.metadata else ""
            pdf_url = article.metadata.get("pdf_url", "") if article.metadata else ""

            formatted += f"**{i}. {article.title}**\n"
            if author_str:
                formatted += f"   Authors: {author_str}\n"
            if arxiv_id:
                formatted += f"   arXiv: {arxiv_id}"
                if category_name:
                    formatted += f" [{category_name}]"
                formatted += "\n"
            if article.publication_date:
                formatted += f"   Published: {article.publication_date}\n"
            if article.url:
                formatted += f"   URL: {article.url}\n"
            if pdf_url:
                formatted += f"   PDF: {pdf_url}\n"
            if article.abstract:
                # Truncate long abstracts
                abstract_preview = article.abstract[:300]
                if len(article.abstract) > 300:
                    abstract_preview += "..."
                formatted += f"   Abstract: {abstract_preview}\n"
            formatted += "\n"

            # Build data for structured output
            article_data.append({
                "arxiv_id": arxiv_id,
                "title": article.title,
                "authors": article.authors,
                "publication_date": article.publication_date,
                "abstract": article.abstract,
                "url": article.url,
                "pdf_url": pdf_url,
                "categories": article.metadata.get("categories", []) if article.metadata else [],
                "doi": article.doi
            })

        yield ToolProgress(
            stage="complete",
            message=f"Found {len(articles)} papers",
            data={"article_count": len(articles)},
            progress=1.0
        )

        return ToolResult(
            text=formatted,
            data={
                "success": True,
                "query": query,
                "total_results": total_results,
                "returned": len(articles),
                "articles": article_data
            }
        )

    except TimeoutError as e:
        logger.warning(f"arXiv search timeout: {e}")
        return ToolResult(
            text=f"arXiv search timed out. Please try again.",
            data={"success": False, "error": "timeout"}
        )
    except Exception as e:
        logger.error(f"arXiv search error: {e}", exc_info=True)
        return ToolResult(
            text=f"arXiv search failed: {str(e)}",
            data={"success": False, "error": str(e)}
        )


ARXIV_SEARCH_TOOL = ToolConfig(
    name="arxiv_search",
    description="""Search arXiv for scientific preprints and papers.

Use this when you need to find:
- Computer science papers (machine learning, AI, algorithms, etc.)
- Physics papers (quantum, astrophysics, condensed matter, etc.)
- Mathematics papers (pure math, applied math, statistics)
- Quantitative biology, finance, or economics papers

arXiv contains preprints (not yet peer-reviewed) and is updated daily with cutting-edge research.

Supports category filtering for focused searches.""",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query. Supports arXiv syntax: 'ti:' (title), 'au:' (author), 'abs:' (abstract), 'cat:' (category). Example: 'ti:transformer au:vaswani'"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10, max: 25)",
                "default": 10
            },
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "date", "updated"],
                "default": "relevance",
                "description": "Sort by relevance, submission date, or last updated date"
            },
            "category": {
                "type": "string",
                "description": "Filter by arXiv category. Examples: 'cs.AI' (AI), 'cs.LG' (machine learning), 'physics.gen-ph' (general physics), 'math.CO' (combinatorics), 'stat.ML' (ML statistics)"
            }
        },
        "required": ["query"]
    },
    executor=execute_arxiv_search,
    category="research",
    streaming=True
)


def register_arxiv_search_tools():
    """Register the arxiv_search tool."""
    register_tool(ARXIV_SEARCH_TOOL)
    logger.info("Registered arxiv_search tool")
