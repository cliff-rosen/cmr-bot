"""
Tools testing endpoints.

Simple endpoints for testing backend services directly.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from database import get_db
from models import User
from routers.auth import get_current_user
from services.pubmed_service import PubMedService
from services.gmail_service import GmailService, GmailServiceError, NotConnectedError
from tools import get_all_tools, get_tools_by_category

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


# ============================================================================
# Tool Registry API
# ============================================================================

class ToolInfo(BaseModel):
    """Information about a registered tool."""
    name: str
    description: str
    category: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None
    streaming: bool


class ToolListResponse(BaseModel):
    """Response containing list of available tools."""
    tools: List[ToolInfo]
    categories: List[str]


@router.get("/list", response_model=ToolListResponse)
async def list_tools(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> ToolListResponse:
    """
    List all available tools with their documentation.

    Optionally filter by category.
    """
    if category:
        tools = get_tools_by_category(category)
    else:
        tools = get_all_tools()

    # Get unique categories
    all_tools = get_all_tools()
    categories = sorted(set(t.category for t in all_tools))

    tool_infos = [
        ToolInfo(
            name=tool.name,
            description=tool.description,
            category=tool.category,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            streaming=tool.streaming
        )
        for tool in tools
    ]

    # Sort by category then name
    tool_infos.sort(key=lambda t: (t.category, t.name))

    return ToolListResponse(
        tools=tool_infos,
        categories=categories
    )


# ============================================================================
# PubMed Search
# ============================================================================

class PubMedSearchRequest(BaseModel):
    """Request model for PubMed search."""
    query: str
    max_results: int = 10
    sort_by: str = "relevance"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class PubMedArticleResponse(BaseModel):
    """Response model for a single PubMed article."""
    pmid: Optional[str]
    title: str
    authors: List[str]
    journal: Optional[str]
    publication_date: Optional[str]
    abstract: Optional[str]
    url: Optional[str]


class PubMedSearchResponse(BaseModel):
    """Response model for PubMed search."""
    success: bool
    query: str
    total_results: int
    returned: int
    articles: List[PubMedArticleResponse]
    error: Optional[str] = None


@router.post("/pubmed/search", response_model=PubMedSearchResponse)
async def search_pubmed(
    request: PubMedSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PubMedSearchResponse:
    """
    Search PubMed for articles.

    This is a simple testing endpoint that directly calls the PubMed service.
    """
    try:
        service = PubMedService()

        articles, metadata = service.search_articles(
            query=request.query,
            max_results=min(request.max_results, 50),
            offset=0,
            sort_by=request.sort_by,
            start_date=request.start_date,
            end_date=request.end_date
        )

        total_results = metadata.get("total_results", 0)

        article_responses = [
            PubMedArticleResponse(
                pmid=article.pmid,
                title=article.title,
                authors=article.authors or [],
                journal=article.journal,
                publication_date=article.publication_date,
                abstract=article.abstract,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/" if article.pmid else None
            )
            for article in articles
        ]

        return PubMedSearchResponse(
            success=True,
            query=request.query,
            total_results=total_results,
            returned=len(articles),
            articles=article_responses
        )

    except ValueError as e:
        logger.warning(f"PubMed search validation error: {e}")
        return PubMedSearchResponse(
            success=False,
            query=request.query,
            total_results=0,
            returned=0,
            articles=[],
            error=str(e)
        )
    except Exception as e:
        logger.error(f"PubMed search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Gmail Search
# ============================================================================

class GmailSearchRequest(BaseModel):
    """Request model for Gmail search."""
    query: str
    max_results: int = 10


class GmailMessageResponse(BaseModel):
    """Response model for a single Gmail message."""
    id: str
    thread_id: str
    subject: str
    sender: str
    date: str
    snippet: str
    labels: List[str]


class GmailSearchResponse(BaseModel):
    """Response model for Gmail search."""
    success: bool
    query: str
    count: int
    messages: List[GmailMessageResponse]
    error: Optional[str] = None


@router.post("/gmail/search", response_model=GmailSearchResponse)
async def search_gmail(
    request: GmailSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> GmailSearchResponse:
    """
    Search Gmail for messages.

    This is a simple testing endpoint that directly calls the Gmail service.
    """
    try:
        service = GmailService(db, current_user.user_id)
        messages = service.search_messages(
            query=request.query,
            max_results=min(request.max_results, 50)
        )

        message_responses = [
            GmailMessageResponse(
                id=msg.id,
                thread_id=msg.thread_id,
                subject=msg.subject,
                sender=msg.sender,
                date=msg.date,
                snippet=msg.snippet,
                labels=msg.labels
            )
            for msg in messages
        ]

        return GmailSearchResponse(
            success=True,
            query=request.query,
            count=len(messages),
            messages=message_responses
        )

    except NotConnectedError as e:
        return GmailSearchResponse(
            success=False,
            query=request.query,
            count=0,
            messages=[],
            error=str(e)
        )
    except GmailServiceError as e:
        logger.error(f"Gmail search error: {e}", exc_info=True)
        return GmailSearchResponse(
            success=False,
            query=request.query,
            count=0,
            messages=[],
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Gmail search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# LLM Testing
# ============================================================================

from services.llm import (
    get_provider,
    get_available_models,
    get_configured_providers,
    get_model_provider,
    get_model,
    ModelInfo
)


class LLMModelInfo(BaseModel):
    """Information about an available LLM model."""
    id: str
    display_name: str
    provider: str
    is_configured: bool
    is_reasoning: bool
    context_window: int
    notes: Optional[str] = None


class LLMModelsResponse(BaseModel):
    """Response containing available LLM models."""
    models: List[LLMModelInfo]
    configured_providers: List[str]


@router.get("/llm-models", response_model=LLMModelsResponse)
async def list_llm_models(
    current_user: User = Depends(get_current_user)
) -> LLMModelsResponse:
    """
    List all available LLM models for testing.

    Returns models from all providers (Anthropic, OpenAI, Google) with
    information about which ones are configured (have API keys).
    """
    models = get_available_models()

    model_infos = [
        LLMModelInfo(
            id=m.id,
            display_name=m.display_name,
            provider=m.provider,
            is_configured=m.is_configured,
            is_reasoning=m.is_reasoning,
            context_window=m.context_window,
            notes=m.notes
        )
        for m in models
    ]

    # Get list of configured providers
    configured = list(set(m.provider for m in models if m.is_configured))

    return LLMModelsResponse(
        models=model_infos,
        configured_providers=configured
    )


class LLMTestRequest(BaseModel):
    """Request model for LLM testing."""
    model: str
    context: str
    questions: List[str]  # All questions sent together


class LLMTestResponse(BaseModel):
    """Response model for LLM test."""
    success: bool
    model: str
    raw_response: str  # Full response text
    parsed_answers: List[str]  # Individual answers extracted
    latency_ms: int
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    error: Optional[str] = None


def parse_answers(response_text: str, num_questions: int) -> List[str]:
    """
    Parse individual answers from a multi-question response.

    Handles formats like:
    - "1. Yes\n2. No\n3. Unclear"
    - "Yes\nNo\nUnclear"
    - "1) Yes 2) No 3) Unclear"
    """
    import re

    lines = response_text.strip().split('\n')
    answers = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Remove common prefixes: "1.", "1)", "1:", "Q1:", etc.
        cleaned = re.sub(r'^(?:Q?\d+[\.\)\:]?\s*)', '', line, flags=re.IGNORECASE).strip()

        if cleaned:
            answers.append(cleaned)

    # If we got fewer answers than questions, pad with empty strings
    while len(answers) < num_questions:
        answers.append("")

    # If we got more, truncate
    return answers[:num_questions]


@router.post("/test-llm", response_model=LLMTestResponse)
async def test_llm(
    request: LLMTestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> LLMTestResponse:
    """
    Test an LLM with a context and multiple questions sent together.

    This endpoint sends all questions in a single prompt to test how the model
    handles multiple questions at once. Used for benchmarking and comparing LLMs.

    Supports all configured providers: Anthropic, OpenAI, and Google.
    """
    try:
        # Get the provider for this model
        provider_name = get_model_provider(request.model)
        if not provider_name:
            return LLMTestResponse(
                success=False,
                model=request.model,
                raw_response="",
                parsed_answers=[],
                latency_ms=0,
                error=f"Unknown model: {request.model}"
            )

        # Get the provider instance
        provider = get_provider(provider_name)
        if not provider:
            return LLMTestResponse(
                success=False,
                model=request.model,
                raw_response="",
                parsed_answers=[],
                latency_ms=0,
                error=f"Provider '{provider_name}' is not configured. Please set the API key in your .env file."
            )

        # Check model config for temperature support
        model_config = get_model(request.model)
        temperature = 0.0 if (model_config and model_config.supports_temperature) else None

        # Call the provider
        # Use 2000 tokens to allow room for multi-question responses
        # (Reasoning models will auto-boost this further in their providers)
        response = await provider.complete_multi_question(
            model_id=request.model,
            context=request.context,
            questions=request.questions,
            max_tokens=2000,
            temperature=temperature
        )

        # Parse individual answers
        parsed_answers = parse_answers(response.text, len(request.questions))

        return LLMTestResponse(
            success=True,
            model=request.model,
            raw_response=response.text,
            parsed_answers=parsed_answers,
            latency_ms=response.latency_ms or 0,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens
        )

    except Exception as e:
        logger.error(f"LLM test error: {e}", exc_info=True)
        return LLMTestResponse(
            success=False,
            model=request.model,
            raw_response="",
            parsed_answers=[],
            latency_ms=0,
            error=str(e)
        )
