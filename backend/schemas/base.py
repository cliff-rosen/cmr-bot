"""
Base Schema Definitions for CMR-Bot
"""

from pydantic import BaseModel, Field
from typing import Dict, Optional, Any, List
from dataclasses import dataclass


class CanonicalSearchResult(BaseModel):
    """Represents a search result from any search engine"""
    title: str
    url: str
    snippet: Optional[str] = None
    source: Optional[str] = None
    date: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class CanonicalResearchArticle(BaseModel):
    """Represents a research article from PubMed or other sources"""
    pmid: Optional[str] = None
    doi: Optional[str] = None
    title: str
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    journal: Optional[str] = None
    publication_date: Optional[str] = None
    url: Optional[str] = None
    source: str = "pubmed"
    metadata: Optional[Dict[str, Any]] = None
