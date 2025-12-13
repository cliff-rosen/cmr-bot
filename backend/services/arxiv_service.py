"""
arXiv Service

Search and retrieve papers from arXiv preprint server.
Uses the arXiv API (no authentication required).

API docs: https://info.arxiv.org/help/api/basics.html
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

from schemas.base import CanonicalResearchArticle

logger = logging.getLogger(__name__)

ARXIV_API_BASE = "http://export.arxiv.org/api/query"
DEFAULT_MAX_RESULTS = 10
REQUEST_TIMEOUT = 30

# arXiv category mappings for common fields
ARXIV_CATEGORIES = {
    "cs": "Computer Science",
    "math": "Mathematics",
    "physics": "Physics",
    "astro-ph": "Astrophysics",
    "cond-mat": "Condensed Matter",
    "gr-qc": "General Relativity",
    "hep-ex": "High Energy Physics - Experiment",
    "hep-lat": "High Energy Physics - Lattice",
    "hep-ph": "High Energy Physics - Phenomenology",
    "hep-th": "High Energy Physics - Theory",
    "math-ph": "Mathematical Physics",
    "nlin": "Nonlinear Sciences",
    "nucl-ex": "Nuclear Experiment",
    "nucl-th": "Nuclear Theory",
    "q-bio": "Quantitative Biology",
    "q-fin": "Quantitative Finance",
    "quant-ph": "Quantum Physics",
    "stat": "Statistics",
    "eess": "Electrical Engineering and Systems Science",
    "econ": "Economics",
}


@dataclass
class ArxivArticle:
    """Represents an arXiv article."""
    arxiv_id: str
    title: str
    abstract: str
    authors: List[str]
    published: str
    updated: str
    categories: List[str]
    primary_category: str
    pdf_url: str
    abs_url: str
    doi: Optional[str] = None
    journal_ref: Optional[str] = None
    comment: Optional[str] = None


class ArxivService:
    """Service for searching arXiv papers."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "CMR-Bot/1.0 (Research Assistant)"
        })

    def search(
        self,
        query: str,
        max_results: int = DEFAULT_MAX_RESULTS,
        start: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "descending",
        category: Optional[str] = None
    ) -> Tuple[List[CanonicalResearchArticle], Dict[str, Any]]:
        """
        Search arXiv for papers.

        Args:
            query: Search query (supports arXiv query syntax)
            max_results: Maximum number of results (default 10, max 100)
            start: Starting index for pagination
            sort_by: Sort field - 'relevance', 'lastUpdatedDate', 'submittedDate'
            sort_order: 'ascending' or 'descending'
            category: Optional category filter (e.g., 'cs.AI', 'physics.gen-ph')

        Returns:
            Tuple of (list of CanonicalResearchArticle, metadata dict)
        """
        # Build search query
        search_query = self._build_query(query, category)

        # Map sort options to arXiv API format
        sort_map = {
            "relevance": "relevance",
            "date": "submittedDate",
            "updated": "lastUpdatedDate",
            "submittedDate": "submittedDate",
            "lastUpdatedDate": "lastUpdatedDate"
        }
        api_sort_by = sort_map.get(sort_by, "relevance")

        # Build API URL
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": min(max_results, 100),  # arXiv max is ~100
            "sortBy": api_sort_by,
            "sortOrder": sort_order
        }

        url = f"{ARXIV_API_BASE}?{urlencode(params)}"
        logger.info(f"arXiv search: {url}")

        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            # Parse XML response
            articles, total_results = self._parse_response(response.text)

            # Convert to canonical format
            canonical_articles = [
                self._to_canonical(article, start + i)
                for i, article in enumerate(articles)
            ]

            metadata = {
                "total_results": total_results,
                "start": start,
                "returned": len(canonical_articles),
                "query": search_query
            }

            return canonical_articles, metadata

        except requests.exceptions.Timeout:
            logger.error("arXiv API timeout")
            raise TimeoutError("arXiv API request timed out")
        except requests.exceptions.RequestException as e:
            logger.error(f"arXiv API error: {e}")
            raise RuntimeError(f"arXiv API error: {e}")

    def _build_query(self, query: str, category: Optional[str] = None) -> str:
        """Build arXiv search query string."""
        # If query already contains field specifiers, use as-is
        if any(f"{field}:" in query.lower() for field in ["ti", "au", "abs", "co", "jr", "cat", "all"]):
            search_query = query
        else:
            # Search in title, abstract, and all fields
            search_query = f"all:{query}"

        # Add category filter if specified
        if category:
            search_query = f"({search_query}) AND cat:{category}"

        return search_query

    def _parse_response(self, xml_text: str) -> Tuple[List[ArxivArticle], int]:
        """Parse arXiv Atom XML response."""
        # Define namespaces
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
            "opensearch": "http://a9.com/-/spec/opensearch/1.1/"
        }

        root = ET.fromstring(xml_text)

        # Get total results
        total_elem = root.find("opensearch:totalResults", ns)
        total_results = int(total_elem.text) if total_elem is not None else 0

        articles = []
        for entry in root.findall("atom:entry", ns):
            try:
                article = self._parse_entry(entry, ns)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.warning(f"Error parsing arXiv entry: {e}")
                continue

        return articles, total_results

    def _parse_entry(self, entry: ET.Element, ns: dict) -> Optional[ArxivArticle]:
        """Parse a single arXiv entry."""
        # Get arxiv ID from the id URL
        id_elem = entry.find("atom:id", ns)
        if id_elem is None:
            return None

        arxiv_id = id_elem.text.split("/abs/")[-1]

        # Title (remove newlines)
        title_elem = entry.find("atom:title", ns)
        title = title_elem.text.strip().replace("\n", " ") if title_elem is not None else ""
        title = re.sub(r'\s+', ' ', title)

        # Abstract (summary)
        summary_elem = entry.find("atom:summary", ns)
        abstract = summary_elem.text.strip() if summary_elem is not None else ""
        abstract = re.sub(r'\s+', ' ', abstract)

        # Authors
        authors = []
        for author in entry.findall("atom:author", ns):
            name_elem = author.find("atom:name", ns)
            if name_elem is not None:
                authors.append(name_elem.text)

        # Dates
        published_elem = entry.find("atom:published", ns)
        published = published_elem.text[:10] if published_elem is not None else ""

        updated_elem = entry.find("atom:updated", ns)
        updated = updated_elem.text[:10] if updated_elem is not None else ""

        # Categories
        categories = []
        primary_category = ""
        for category in entry.findall("atom:category", ns):
            cat_term = category.get("term", "")
            if cat_term:
                categories.append(cat_term)

        # Primary category from arxiv namespace
        primary_elem = entry.find("arxiv:primary_category", ns)
        if primary_elem is not None:
            primary_category = primary_elem.get("term", "")
        elif categories:
            primary_category = categories[0]

        # Links
        pdf_url = ""
        abs_url = ""
        for link in entry.findall("atom:link", ns):
            link_type = link.get("type", "")
            link_href = link.get("href", "")
            if link_type == "application/pdf":
                pdf_url = link_href
            elif link.get("rel") == "alternate":
                abs_url = link_href

        # Optional fields
        doi_elem = entry.find("arxiv:doi", ns)
        doi = doi_elem.text if doi_elem is not None else None

        journal_elem = entry.find("arxiv:journal_ref", ns)
        journal_ref = journal_elem.text if journal_elem is not None else None

        comment_elem = entry.find("arxiv:comment", ns)
        comment = comment_elem.text if comment_elem is not None else None

        return ArxivArticle(
            arxiv_id=arxiv_id,
            title=title,
            abstract=abstract,
            authors=authors,
            published=published,
            updated=updated,
            categories=categories,
            primary_category=primary_category,
            pdf_url=pdf_url,
            abs_url=abs_url,
            doi=doi,
            journal_ref=journal_ref,
            comment=comment
        )

    def _to_canonical(self, article: ArxivArticle, position: int) -> CanonicalResearchArticle:
        """Convert ArxivArticle to CanonicalResearchArticle."""
        # Get readable category name
        primary_cat = article.primary_category.split(".")[0] if article.primary_category else ""
        category_name = ARXIV_CATEGORIES.get(primary_cat, article.primary_category)

        return CanonicalResearchArticle(
            pmid=None,
            doi=article.doi,
            title=article.title,
            abstract=article.abstract,
            authors=article.authors if article.authors else None,
            journal=article.journal_ref or f"arXiv:{article.arxiv_id}",
            publication_date=article.published,
            url=article.abs_url,
            source="arxiv",
            metadata={
                "arxiv_id": article.arxiv_id,
                "pdf_url": article.pdf_url,
                "categories": article.categories,
                "primary_category": article.primary_category,
                "category_name": category_name,
                "updated": article.updated,
                "comment": article.comment,
                "search_position": position + 1
            }
        )


# Module-level convenience functions
_service = None


def get_service() -> ArxivService:
    """Get or create the arXiv service singleton."""
    global _service
    if _service is None:
        _service = ArxivService()
    return _service


def search_arxiv(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    **kwargs
) -> Tuple[List[CanonicalResearchArticle], Dict[str, Any]]:
    """Convenience function to search arXiv."""
    return get_service().search(query, max_results, **kwargs)
