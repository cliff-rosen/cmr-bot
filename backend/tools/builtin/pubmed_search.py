"""
PubMed Search Tool

Search PubMed/MEDLINE database for biomedical literature.
Uses NCBI E-utilities API via the pubmed_service.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Generator, List, Optional
from sqlalchemy.orm import Session

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from tools.executor import run_async

logger = logging.getLogger(__name__)

MAX_PUBMED_RESULTS = 20


def _calculate_date_range(date_range: str) -> tuple[str, str]:
    """
    Calculate start and end dates from a relative date range.
    Returns dates in YYYY/MM/DD format for PubMed API.
    """
    today = datetime.now()
    end_date = today.strftime("%Y/%m/%d")

    if date_range == "last_week":
        start = today - timedelta(days=7)
    elif date_range == "last_month":
        start = today - timedelta(days=30)
    elif date_range == "last_3_months":
        start = today - timedelta(days=90)
    elif date_range == "last_6_months":
        start = today - timedelta(days=180)
    elif date_range == "last_year":
        start = today - timedelta(days=365)
    else:
        # Default to last month if unknown
        start = today - timedelta(days=30)

    start_date = start.strftime("%Y/%m/%d")
    return start_date, end_date


def execute_pubmed_search(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Search PubMed for biomedical literature.

    This is a streaming tool that yields progress updates.
    """
    from services.pubmed_service import PubMedService

    query = params.get("query", "")
    max_results = min(params.get("max_results", 10), MAX_PUBMED_RESULTS)
    sort_by = params.get("sort_by", "relevance")
    date_range = params.get("date_range")
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    date_type = params.get("date_type", "publication")

    # If date_range is provided, calculate actual dates (overrides start_date/end_date)
    if date_range:
        start_date, end_date = _calculate_date_range(date_range)

    if not query:
        return ToolResult(text="Error: No search query provided")

    cancellation_token = context.get("cancellation_token")

    # Step 1: Initialize search
    yield ToolProgress(
        stage="searching",
        message=f"Searching PubMed for: {query}",
        data={"query": query, "max_results": max_results},
        progress=0.1
    )

    if cancellation_token and cancellation_token.is_cancelled:
        return ToolResult(text="Search cancelled")

    try:
        service = PubMedService()

        # Step 2: Execute search
        yield ToolProgress(
            stage="fetching",
            message="Fetching articles from PubMed...",
            data={},
            progress=0.3
        )

        articles, metadata = service.search_articles(
            query=query,
            max_results=max_results,
            offset=0,
            sort_by=sort_by,
            start_date=start_date,
            end_date=end_date,
            date_type=date_type
        )

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(text="Search cancelled")

        total_results = metadata.get("total_results", 0)

        yield ToolProgress(
            stage="processing",
            message=f"Found {total_results} total results, processing {len(articles)} articles",
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
                text=f"No PubMed articles found for: {query}",
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
        formatted = f"**PubMed Search Results for '{query}'**\n"
        formatted += f"Found {total_results} total results, showing {len(articles)}\n\n"

        article_data = []
        for i, article in enumerate(articles, 1):
            # Build citation line
            authors = article.authors[:3] if article.authors else []
            author_str = ", ".join(authors)
            if article.authors and len(article.authors) > 3:
                author_str += " et al."

            formatted += f"**{i}. {article.title}**\n"
            if author_str:
                formatted += f"   Authors: {author_str}\n"
            if article.journal:
                formatted += f"   Journal: {article.journal}"
                if article.publication_date:
                    formatted += f" ({article.publication_date})"
                formatted += "\n"
            if article.pmid:
                formatted += f"   PMID: {article.pmid}\n"
                formatted += f"   URL: https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/\n"
            if article.abstract:
                # Truncate long abstracts
                abstract_preview = article.abstract[:300]
                if len(article.abstract) > 300:
                    abstract_preview += "..."
                formatted += f"   Abstract: {abstract_preview}\n"
            formatted += "\n"

            # Build data for structured output
            article_data.append({
                "pmid": article.pmid,
                "title": article.title,
                "authors": article.authors,
                "journal": article.journal,
                "publication_date": article.publication_date,
                "abstract": article.abstract,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/" if article.pmid else None
            })

        yield ToolProgress(
            stage="complete",
            message=f"Found {len(articles)} articles",
            data={"article_count": len(articles)},
            progress=1.0
        )

        # Build table payload for workspace
        table_payload = {
            "type": "table",
            "title": f"PubMed: {query[:50]}{'...' if len(query) > 50 else ''}",
            "content": f"Found {total_results} total results, showing {len(articles)}",
            "table_data": {
                "columns": [
                    {"key": "pmid", "label": "PMID", "type": "text", "sortable": True, "width": "80px"},
                    {"key": "title", "label": "Title", "type": "text", "sortable": True},
                    {"key": "authors_display", "label": "Authors", "type": "text", "sortable": True},
                    {"key": "journal", "label": "Journal", "type": "text", "sortable": True, "filterable": True},
                    {"key": "publication_date", "label": "Date", "type": "text", "sortable": True, "width": "100px"},
                    {"key": "url", "label": "Link", "type": "link", "sortable": False, "width": "60px"},
                ],
                "rows": [
                    {
                        "pmid": a["pmid"],
                        "title": a["title"],
                        "authors_display": ", ".join(a["authors"][:3]) + (" et al." if len(a["authors"]) > 3 else "") if a["authors"] else "",
                        "journal": a["journal"],
                        "publication_date": a["publication_date"],
                        "url": a["url"],
                        "abstract": a["abstract"]  # Include for future use
                    }
                    for a in article_data
                ],
                "source": "pubmed_search"
            }
        }

        return ToolResult(
            text=formatted,
            data={
                "success": True,
                "query": query,
                "total_results": total_results,
                "returned": len(articles),
                "articles": article_data
            },
            workspace_payload=table_payload
        )

    except ValueError as e:
        # Handle specific errors like query too long
        logger.warning(f"PubMed search validation error: {e}")
        return ToolResult(
            text=f"Search error: {str(e)}",
            data={"success": False, "error": str(e)}
        )
    except Exception as e:
        logger.error(f"PubMed search error: {e}", exc_info=True)
        return ToolResult(
            text=f"PubMed search failed: {str(e)}",
            data={"success": False, "error": str(e)}
        )


PUBMED_SEARCH_TOOL = ToolConfig(
    name="pubmed_search",
    description="""Search PubMed/MEDLINE for biomedical and life sciences literature.

    Use this when you need to:
    - Find scientific/medical research papers
    - Look up clinical studies or trials
    - Research diseases, treatments, drugs, or medical conditions
    - Find peer-reviewed academic literature in biology, medicine, or health sciences

    Supports date filtering and sorting by relevance or date.""",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "PubMed search query. Supports standard PubMed search syntax including Boolean operators (AND, OR, NOT), field tags ([Title], [Author], [MeSH Terms]), and phrases in quotes."
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default: 10, max: 20)",
                "default": 10
            },
            "sort_by": {
                "type": "string",
                "enum": ["relevance", "date"],
                "default": "relevance",
                "description": "Sort results by relevance or publication date"
            },
            "date_range": {
                "type": "string",
                "enum": ["last_week", "last_month", "last_3_months", "last_6_months", "last_year"],
                "description": "Relative date range filter. PREFERRED over start_date/end_date as it automatically calculates correct dates."
            },
            "start_date": {
                "type": "string",
                "description": "Start date for filtering (YYYY/MM/DD format). Use date_range instead for relative dates."
            },
            "end_date": {
                "type": "string",
                "description": "End date for filtering (YYYY/MM/DD format). Use date_range instead for relative dates."
            },
            "date_type": {
                "type": "string",
                "enum": ["publication", "entry", "completion", "revised"],
                "default": "publication",
                "description": "Which date field to filter on: publication (default), entry (when added to PubMed), completion, or revised"
            }
        },
        "required": ["query"]
    },
    executor=execute_pubmed_search,
    category="research",
    streaming=True
)


def register_pubmed_search_tools():
    """Register the pubmed_search tool."""
    register_tool(PUBMED_SEARCH_TOOL)
    logger.info("Registered pubmed_search tool")
