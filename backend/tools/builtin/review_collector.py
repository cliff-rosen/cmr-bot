"""
Review Collector Tool

Collects reviews from a SINGLE source (Yelp, Google, or Reddit).

Architecture:
1. Entity verification is a SEPARATE orchestrated workflow (not autonomous agent)
2. Once entity is verified, artifact collection extracts reviews from the verified page
3. Returns journey-based payload with full telemetry
"""

import json
import logging
import queue
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Generator, Literal, Union
from urllib.parse import urlparse
from sqlalchemy.orm import Session

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from tools.builtin.entity_verification import verify_entity, VerificationResult
from services.agent_loop import (
    run_agent_loop_sync,
    AgentEvent,
    AgentToolStart,
    AgentToolProgress,
    AgentToolComplete,
)

logger = logging.getLogger(__name__)

# Configuration
AGENT_MODEL = "claude-sonnet-4-20250514"
MAX_AGENT_TURNS = 20

SourceType = Literal["yelp", "google", "reddit"]
OutcomeStatus = Literal["complete", "entity_not_found", "entity_ambiguous", "blocked", "partial", "error"]
ConfidenceLevel = Literal["high", "medium", "low"]
MatchConfidence = Literal["exact", "probable", "uncertain"]
StepStatus = Literal["success", "failed", "blocked", "timeout"]
PhaseStatus = Literal["success", "failed", "partial", "skipped"]
ObstacleType = Literal["rate_limit", "js_blocked", "captcha", "not_found", "timeout", "parse_error"]


# =============================================================================
# Data Structures - Journey-Based Payload
# =============================================================================

@dataclass
class Step:
    """A single action taken during collection (search or fetch)."""
    action: Literal["search", "fetch"]
    input: str  # Query or URL
    status: StepStatus
    duration_ms: int
    findings: List[str] = field(default_factory=list)

    # For fetches
    content_size: Optional[int] = None
    was_js_rendered: Optional[bool] = None
    was_blocked: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class Phase:
    """A phase of the collection process."""
    name: Literal["entity_resolution", "artifact_collection"]
    status: PhaseStatus
    duration_ms: int = 0
    steps: List[Step] = field(default_factory=list)
    conclusion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "steps": [s.to_dict() for s in self.steps],
            "conclusion": self.conclusion
        }


@dataclass
class Obstacle:
    """An obstacle encountered during collection."""
    type: ObstacleType
    description: str
    impact: str
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class ToolCallStats:
    """Statistics about tool calls made."""
    searches: Dict[str, int] = field(default_factory=lambda: {"attempted": 0, "successful": 0})
    fetches: Dict[str, int] = field(default_factory=lambda: {"attempted": 0, "successful": 0, "blocked": 0})

    def to_dict(self) -> Dict[str, Any]:
        return {"searches": self.searches, "fetches": self.fetches}


@dataclass
class Journey:
    """The complete journey of a collection attempt."""
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0
    phases: List[Phase] = field(default_factory=list)
    tool_calls: ToolCallStats = field(default_factory=ToolCallStats)
    obstacles: List[Obstacle] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "phases": [p.to_dict() for p in self.phases],
            "tool_calls": self.tool_calls.to_dict(),
            "obstacles": [o.to_dict() for o in self.obstacles]
        }


@dataclass
class Entity:
    """A verified business entity."""
    name: str
    url: str
    platform_id: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    match_confidence: MatchConfidence = "uncertain"
    match_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewArtifact:
    """An actual review from Yelp or Google."""
    rating: Optional[float]
    text: str
    author: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class RedditArtifact:
    """A Reddit post or comment."""
    text: str
    author: str
    subreddit: str
    url: str
    title: Optional[str] = None
    score: Optional[int] = None
    date: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Analysis:
    """Analysis of collected artifacts."""
    sentiment: str = ""
    themes: List[str] = field(default_factory=list)
    notable_quotes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Outcome:
    """The outcome of the collection attempt."""
    success: bool
    status: OutcomeStatus
    confidence: ConfidenceLevel
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Request:
    """The original request parameters."""
    business_name: str
    location: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewCollectionResult:
    """Complete result of a review collection attempt with journey details."""
    outcome: Outcome
    request: Request
    entity: Optional[Entity] = None
    artifacts: List[Union[ReviewArtifact, RedditArtifact]] = field(default_factory=list)
    journey: Journey = field(default_factory=Journey)
    analysis: Optional[Analysis] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "outcome": self.outcome.to_dict(),
            "request": self.request.to_dict(),
            "entity": self.entity.to_dict() if self.entity else None,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "journey": self.journey.to_dict(),
            "analysis": self.analysis.to_dict() if self.analysis else None
        }
        return result


# =============================================================================
# Journey Tracker - Collects telemetry during execution
# =============================================================================

class JourneyTracker:
    """Tracks the journey of a collection attempt in real-time."""

    def __init__(self, business_name: str, location: str, source: str):
        self.request = Request(business_name=business_name, location=location, source=source)
        self.journey = Journey()
        self.journey.started_at = datetime.now(timezone.utc).isoformat()
        self._start_time = time.time()

        self.current_phase: Optional[Phase] = None
        self._phase_start_time: Optional[float] = None
        self._step_start_time: Optional[float] = None
        self._current_step_input: Optional[str] = None
        self._current_step_action: Optional[str] = None

        self.entity: Optional[Entity] = None
        self.artifacts: List[Union[ReviewArtifact, RedditArtifact]] = []
        self.analysis: Optional[Analysis] = None

    def start_phase(self, name: Literal["entity_resolution", "artifact_collection"]):
        """Start a new phase."""
        if self.current_phase:
            self._end_current_phase()

        self.current_phase = Phase(name=name, status="success")
        self._phase_start_time = time.time()

    def _end_current_phase(self):
        """End the current phase."""
        if self.current_phase and self._phase_start_time:
            self.current_phase.duration_ms = int((time.time() - self._phase_start_time) * 1000)
            self.journey.phases.append(self.current_phase)

    def start_step(self, action: Literal["search", "fetch"], input_str: str):
        """Start tracking a step."""
        self._step_start_time = time.time()
        self._current_step_input = input_str
        self._current_step_action = action

        # Update stats
        if action == "search":
            self.journey.tool_calls.searches["attempted"] += 1
        else:
            self.journey.tool_calls.fetches["attempted"] += 1

    def complete_step(self, status: StepStatus, findings: List[str],
                      content_size: Optional[int] = None,
                      was_js_rendered: Optional[bool] = None,
                      was_blocked: Optional[bool] = None):
        """Complete the current step."""
        if not self._step_start_time or not self._current_step_action:
            return

        duration_ms = int((time.time() - self._step_start_time) * 1000)

        step = Step(
            action=self._current_step_action,
            input=self._current_step_input or "",
            status=status,
            duration_ms=duration_ms,
            findings=findings,
            content_size=content_size,
            was_js_rendered=was_js_rendered,
            was_blocked=was_blocked
        )

        if self.current_phase:
            self.current_phase.steps.append(step)

        # Update stats
        if self._current_step_action == "search":
            if status == "success":
                self.journey.tool_calls.searches["successful"] += 1
        else:
            if status == "success":
                self.journey.tool_calls.fetches["successful"] += 1
            elif status == "blocked":
                self.journey.tool_calls.fetches["blocked"] += 1

        # Reset
        self._step_start_time = None
        self._current_step_input = None
        self._current_step_action = None

    def add_obstacle(self, type: ObstacleType, description: str, impact: str, url: Optional[str] = None):
        """Record an obstacle encountered."""
        self.journey.obstacles.append(Obstacle(
            type=type, description=description, impact=impact, url=url
        ))

    def set_phase_conclusion(self, conclusion: str, status: PhaseStatus = "success"):
        """Set the conclusion for the current phase."""
        if self.current_phase:
            self.current_phase.conclusion = conclusion
            self.current_phase.status = status

    def finalize(self, outcome: Outcome) -> ReviewCollectionResult:
        """Finalize the journey and build the result."""
        # End current phase if any
        if self.current_phase:
            self._end_current_phase()

        # Set completion time
        self.journey.completed_at = datetime.now(timezone.utc).isoformat()
        self.journey.duration_ms = int((time.time() - self._start_time) * 1000)

        return ReviewCollectionResult(
            outcome=outcome,
            request=self.request,
            entity=self.entity,
            artifacts=self.artifacts,
            journey=self.journey,
            analysis=self.analysis
        )


# =============================================================================
# Tools available to the review collector agent
# =============================================================================

# Global tracker for current execution (set per-execution)
_current_tracker: Optional[JourneyTracker] = None


def _execute_search(params: Dict[str, Any], db: Session, user_id: int, context: Dict) -> ToolResult:
    """Search tool for the review collector agent."""
    global _current_tracker
    from services.search_service import SearchService

    query = params.get("query", "")
    if not query:
        return ToolResult(text="Error: No query provided")

    # Track step start
    if _current_tracker:
        _current_tracker.start_step("search", query)

    try:
        search_service = SearchService()
        if not search_service.initialized:
            search_service.initialize()

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                search_service.search(search_term=query, num_results=10)
            )
        finally:
            loop.close()

        results = result.get("search_results", [])

        findings = []
        if not results:
            findings.append("No results found")
            if _current_tracker:
                _current_tracker.complete_step("success", findings)
            return ToolResult(text="No results found for this query.")

        findings.append(f"Found {len(results)} results")

        # Extract key findings from results
        for r in results[:3]:
            title = getattr(r, 'title', '')
            url = getattr(r, 'url', '')
            if 'yelp.com/biz' in url:
                findings.append(f"Yelp business page: {url}")
            elif 'healthgrades.com' in url:
                findings.append(f"Healthgrades page: {url}")
            elif 'reddit.com' in url:
                findings.append(f"Reddit post: {title[:50]}")

        if _current_tracker:
            _current_tracker.complete_step("success", findings)

        output = f"Search results for: {query}\n\n"
        for i, r in enumerate(results, 1):
            title = getattr(r, 'title', 'No title')
            url = getattr(r, 'url', '')
            snippet = getattr(r, 'snippet', '') or ''
            output += f"{i}. {title}\n"
            output += f"   URL: {url}\n"
            if snippet:
                output += f"   {snippet[:300]}\n"
            output += "\n"

        return ToolResult(text=output)

    except Exception as e:
        logger.error(f"Search error: {e}")
        if _current_tracker:
            _current_tracker.complete_step("failed", [f"Error: {str(e)}"])
        return ToolResult(text=f"Search error: {str(e)}")


def _run_async(coro):
    """Run async code safely, handling Windows subprocess requirements."""
    import asyncio
    import sys

    # On Windows, we need ProactorEventLoop for subprocess support (used by Playwright)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    return asyncio.run(coro)


def _execute_fetch(params: Dict[str, Any], db: Session, user_id: int, context: Dict) -> ToolResult:
    """Fetch tool for the review collector agent."""
    global _current_tracker

    url = params.get("url", "")
    if not url:
        return ToolResult(text="Error: No URL provided")

    # Track step start
    if _current_tracker:
        _current_tracker.start_step("fetch", url)

    # Determine if this URL needs JavaScript rendering
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    js_required_domains = [
        'yelp.com', 'www.yelp.com',
        'google.com', 'www.google.com', 'maps.google.com',
        'healthgrades.com', 'www.healthgrades.com',
    ]

    needs_js = any(domain.endswith(d) or domain == d for d in js_required_domains)

    try:
        if needs_js:
            from services.js_web_retrieval_service import fetch_with_js

            result = _run_async(
                fetch_with_js(url=url, timeout=45000, wait_after_load=3000)
            )

            webpage = result["webpage"]
            content = webpage.content
            title = webpage.title
            content_size = len(content)
            was_blocked = webpage.metadata.get('blocked', False)

            findings = []
            if was_blocked:
                block_reason = webpage.metadata.get('block_reason', 'Unknown')
                findings.append(f"BLOCKED: {block_reason}")
                if _current_tracker:
                    _current_tracker.complete_step("blocked", findings, content_size, True, True)
                    _current_tracker.add_obstacle(
                        "rate_limit", block_reason,
                        "Could not access page content", url
                    )
            else:
                findings.append(f"Loaded {content_size} chars")
                findings.append(f"Title: {title[:60]}")
                # Look for key indicators
                content_lower = content.lower()
                if 'review' in content_lower:
                    review_count = content_lower.count('review')
                    findings.append(f"Contains 'review' {review_count}x")
                if _current_tracker:
                    _current_tracker.complete_step("success", findings, content_size, True, False)

            load_info = f"[JS-rendered in {webpage.load_time_ms}ms]"
        else:
            from services.web_retrieval_service import WebRetrievalService

            web_service = WebRetrievalService()
            result = _run_async(
                web_service.retrieve_webpage(url=url, extract_text_only=True)
            )

            webpage = result["webpage"]
            content = webpage.content
            title = webpage.title
            content_size = len(content)
            load_info = ""

            findings = [f"Loaded {content_size} chars", f"Title: {title[:60]}"]
            if _current_tracker:
                _current_tracker.complete_step("success", findings, content_size, False, False)

        if len(content) > 15000:
            content = content[:15000] + "\n\n[Content truncated]"

        return ToolResult(text=f"Page: {title} {load_info}\nURL: {url}\n\nContent:\n{content}")

    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        if _current_tracker:
            _current_tracker.complete_step("failed", [f"Error: {str(e)}"])
        return ToolResult(text=f"Failed to fetch page: {str(e)}")


# Tool configurations
SEARCH_TOOL = ToolConfig(
    name="search",
    description="Search the web. Use site: operators to target specific platforms (e.g., 'site:yelp.com/biz', 'site:reddit.com').",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query"}
        },
        "required": ["query"]
    },
    executor=_execute_search,
    category="internal"
)

FETCH_TOOL = ToolConfig(
    name="fetch",
    description="Fetch and read a webpage. Returns the text content.",
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to fetch"}
        },
        "required": ["url"]
    },
    executor=_execute_fetch,
    category="internal"
)


# =============================================================================
# System Prompts - Artifact Extraction Only
# =============================================================================

def _get_artifact_extraction_prompt(source: SourceType, business_name: str, entity_url: str) -> str:
    """
    Get prompt for artifact extraction from a VERIFIED page.
    Entity verification is done separately - this agent just extracts reviews.
    """

    if source == "reddit":
        return f"""You are extracting Reddit posts/comments about a business.

TARGET: "{business_name}"
PLATFORM: Reddit

You have search and fetch tools. Find Reddit discussions about this business.

OUTPUT FORMAT (JSON):
```json
{{
    "artifacts": [
        {{
            "text": "the comment or post text",
            "author": "username",
            "subreddit": "subreddit name",
            "url": "permalink",
            "title": "post title if it's a post",
            "score": 42,
            "date": "date if visible"
        }}
    ],
    "analysis": {{
        "sentiment": "overall sentiment",
        "themes": ["theme1", "theme2"],
        "notable_quotes": ["quote1"]
    }}
}}
```

Collect ACTUAL post/comment text, not summaries."""

    # For Yelp/Google - we already have the page content from verification
    return f"""You are extracting reviews from a business page.

TARGET: "{business_name}"
URL: {entity_url}
PLATFORM: {source.upper()}

You have the page content. Extract the actual reviews.

OUTPUT FORMAT (JSON):
```json
{{
    "artifacts": [
        {{
            "rating": 5,
            "text": "actual review text verbatim",
            "author": "reviewer name",
            "date": "date if shown"
        }}
    ],
    "rating_summary": {{
        "overall": 4.5,
        "total_reviews": 123
    }},
    "analysis": {{
        "sentiment": "overall sentiment",
        "themes": ["theme1", "theme2"],
        "notable_quotes": ["quote1"]
    }}
}}
```

RULES:
- Extract ACTUAL review text, not summaries
- Include as many reviews as visible on the page
- Preserve exact wording from reviews"""


def _get_page_extraction_prompt(source: SourceType, business_name: str, page_content: str) -> str:
    """
    Direct extraction prompt when we already have page content (no agent needed).
    """
    return f"""Extract reviews from this {source.upper()} page for "{business_name}".

PAGE CONTENT:
---
{page_content}
---

Extract all visible reviews into this JSON format:
```json
{{
    "artifacts": [
        {{"rating": 5, "text": "review text", "author": "name", "date": "date"}}
    ],
    "rating_summary": {{"overall": 4.5, "total_reviews": 123}},
    "analysis": {{"sentiment": "...", "themes": ["..."], "notable_quotes": ["..."]}}
}}
```

Return ACTUAL review text, not summaries. Include all visible reviews."""


# =============================================================================
# SerpAPI Fast Path
# =============================================================================

def _try_serpapi_collection(
    business_name: str,
    location: str,
    source: str,
    tracker: JourneyTracker
) -> Generator[ToolProgress, None, Optional[ToolResult]]:
    """
    Try to collect reviews via SerpAPI.

    Returns ToolResult if successful, None if SerpAPI unavailable (caller should fall back).
    """
    from services.serpapi_service import get_serpapi_service

    service = get_serpapi_service()
    if not service.api_key:
        logger.info("SerpAPI key not configured, falling back to web scraping")
        yield ToolProgress(
            stage="serpapi_unavailable",
            message="SerpAPI not configured, using fallback",
            data={}
        )
        return None

    yield ToolProgress(
        stage="serpapi",
        message=f"Fetching {source.upper()} reviews via SerpAPI",
        data={"method": "serpapi"}
    )

    tracker.start_step("search", f"SerpAPI {source} search")

    # Use SerpAPI to find business and get reviews (with pagination)
    result = service.find_and_get_reviews(
        business_name=business_name,
        location=location,
        source=source,
        num_reviews=30  # Get more reviews with pagination support
    )

    tracker.complete_step(
        "success" if result.success else "failed",
        [f"Found {len(result.reviews)} reviews" if result.success else result.error or "Failed"]
    )

    if not result.success:
        yield ToolProgress(
            stage="serpapi_failed",
            message=result.error or f"Could not find {business_name} on {source.upper()}",
            data={}
        )
        # Return failure result
        tracker.set_phase_conclusion(result.error or "SerpAPI search failed", "failed")
        outcome = Outcome(
            success=False,
            status="entity_not_found",
            confidence="low",
            summary=result.error or f"Could not find {business_name} on {source.upper()}"
        )
        final_result = tracker.finalize(outcome)
        return ToolResult(
            text=_format_text_output(final_result),
            data=final_result.to_dict(),
            workspace_payload={"type": "review_collection", "data": final_result.to_dict()}
        )

    # Success! Convert SerpAPI result to our format
    biz = result.business
    tracker.entity = Entity(
        name=biz.name,
        url=biz.url or "",
        platform_id=biz.place_id,  # Store the platform ID for future lookups
        rating=biz.rating,
        review_count=biz.review_count,
        match_confidence="exact",  # SerpAPI gives us exact matches
        match_reason=f"SerpAPI match at {biz.address or 'N/A'}"
    )
    tracker.set_phase_conclusion(f"Found via SerpAPI: {biz.name}", "success")

    # Phase 2: Reviews (already fetched)
    tracker.start_phase("artifact_collection")

    yield ToolProgress(
        stage="serpapi_reviews",
        message=f"Got {len(result.reviews)} reviews from SerpAPI",
        data={"review_count": len(result.reviews)}
    )

    # Convert reviews to our format
    for review in result.reviews:
        tracker.artifacts.append(ReviewArtifact(
            rating=review.rating,
            text=review.text,
            author=review.author,
            date=review.date
        ))

    # Build analysis (simple version - could use LLM for better analysis)
    if tracker.artifacts:
        ratings = [a.rating for a in tracker.artifacts if a.rating]
        avg_rating = sum(ratings) / len(ratings) if ratings else None

        tracker.analysis = Analysis(
            sentiment=f"Average rating: {avg_rating:.1f}/5" if avg_rating else "Mixed reviews",
            themes=[],
            notable_quotes=[a.text[:100] + "..." for a in tracker.artifacts[:2] if len(a.text) > 50]
        )

    tracker.set_phase_conclusion(f"Collected {len(tracker.artifacts)} reviews via SerpAPI", "success")

    # Build final result
    artifact_count = len(tracker.artifacts)
    rating_str = f"{biz.rating}★" if biz.rating else ""

    summary = f"Found {artifact_count} reviews"
    if rating_str:
        summary += f" • {rating_str}"
    summary += f" • {biz.name}"

    outcome = Outcome(
        success=True,
        status="complete",
        confidence="high",
        summary=summary
    )

    final_result = tracker.finalize(outcome)

    yield ToolProgress(
        stage="complete",
        message=summary,
        data={"success": True, "method": "serpapi"}
    )

    return ToolResult(
        text=_format_text_output(final_result),
        data=final_result.to_dict(),
        workspace_payload={"type": "review_collection", "data": final_result.to_dict()}
    )


# =============================================================================
# Main Executor
# =============================================================================

def execute_review_collector(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Execute the review collector for a single source.

    Two-phase architecture:
    1. Entity Verification (orchestrated workflow, not autonomous agent)
    2. Artifact Extraction (simple LLM call or agent for Reddit)
    """
    global _current_tracker

    business_name = params.get("business_name", "")
    location = params.get("location", "")
    source = params.get("source", "").lower()

    # Validate inputs
    if not business_name:
        return ToolResult(text="Error: business_name is required")
    if not location:
        return ToolResult(text="Error: location is required")
    if source not in ("yelp", "google", "reddit"):
        return ToolResult(text=f"Error: source must be 'yelp', 'google', or 'reddit'")

    # Initialize journey tracker
    _current_tracker = JourneyTracker(business_name, location, source)
    _current_tracker.start_phase("entity_resolution")

    yield ToolProgress(
        stage="starting",
        message=f"Collecting {source.upper()} reviews for {business_name}",
        data={"business_name": business_name, "location": location, "source": source}
    )

    # ==========================================================================
    # TRY SERPAPI FIRST (Fast path for Yelp/Google)
    # ==========================================================================

    if source in ("yelp", "google"):
        serpapi_result = yield from _try_serpapi_collection(
            business_name, location, source, _current_tracker
        )
        if serpapi_result is not None:
            _current_tracker = None
            return serpapi_result

    # ==========================================================================
    # FALLBACK: Entity Verification + Extraction
    # ==========================================================================

    verification_result = None

    # For Reddit, we don't need strict entity verification - we search for mentions
    if source == "reddit":
        yield ToolProgress(
            stage="reddit_mode",
            message="Reddit mode: searching for mentions",
            data={}
        )
        # Skip entity verification for Reddit - go straight to agent collection
        verification_result = None
    else:
        # Run entity verification workflow
        verification_gen = verify_entity(
            business_name=business_name,
            location=location,
            source=source,
            db=db,
            user_id=user_id,
            context=context
        )

        # Forward progress from verification
        try:
            while True:
                progress = next(verification_gen)
                # Convert verification progress to ToolProgress
                stage = progress.get("stage", "verifying")
                message = progress.get("message", "Verifying entity")
                iteration = progress.get("iteration", 1)

                # Track steps in journey
                if stage == "searching":
                    _current_tracker.start_step("search", message)
                elif stage == "fetching":
                    _current_tracker.start_step("fetch", message)
                elif stage in ("confirmed", "no_results", "blocked", "no_match", "gave_up"):
                    if _current_tracker._step_start_time:
                        status = "success" if stage == "confirmed" else "failed"
                        _current_tracker.complete_step(status, [message])

                yield ToolProgress(
                    stage=f"verify_{stage}",
                    message=message,
                    data={"iteration": iteration, "phase": "entity_verification"}
                )

        except StopIteration as e:
            verification_result = e.value

        # Handle verification failure
        if verification_result and verification_result.status != "confirmed":
            _current_tracker.set_phase_conclusion(
                verification_result.message,
                "failed"
            )

            outcome = Outcome(
                success=False,
                status=_map_verification_status(verification_result.status),
                confidence="low",
                summary=verification_result.message
            )

            result = _current_tracker.finalize(outcome)
            _current_tracker = None

            yield ToolProgress(
                stage="verification_failed",
                message=verification_result.message,
                data={"status": verification_result.status}
            )

            return ToolResult(
                text=_format_text_output(result),
                data=result.to_dict(),
                workspace_payload={"type": "review_collection", "data": result.to_dict()}
            )

        # Entity verified!
        if verification_result:
            _current_tracker.entity = Entity(
                name=verification_result.entity.name,
                url=verification_result.entity.url,
                match_confidence=verification_result.entity.confidence,
                match_reason=verification_result.entity.reason
            )
            _current_tracker.set_phase_conclusion(
                f"Verified: {verification_result.entity.name}",
                "success"
            )

    # ==========================================================================
    # PHASE 2: Artifact Extraction
    # ==========================================================================

    _current_tracker.start_phase("artifact_collection")

    yield ToolProgress(
        stage="extracting",
        message="Extracting reviews",
        data={"phase": "artifact_collection"}
    )

    if source == "reddit":
        # Reddit needs agent-based collection (search + fetch Reddit posts)
        artifacts_data = yield from _run_reddit_agent(
            business_name, location, db, user_id, context
        )
    else:
        # Yelp/Google: We have page content from verification - direct extraction
        if verification_result and verification_result.page_content:
            artifacts_data = _extract_from_page_content(
                source, business_name, verification_result.page_content
            )
        else:
            # Fallback: run agent to fetch and extract
            artifacts_data = yield from _run_extraction_agent(
                source, business_name, _current_tracker.entity.url,
                db, user_id, context
            )

    # ==========================================================================
    # Build Final Result
    # ==========================================================================

    yield ToolProgress(
        stage="finalizing",
        message="Building result",
        data={}
    )

    result = _build_final_result(
        tracker=_current_tracker,
        artifacts_data=artifacts_data,
        source=source
    )

    _current_tracker = None

    yield ToolProgress(
        stage="complete",
        message=f"Collection {result.outcome.status}: {result.outcome.summary}",
        data={"success": result.outcome.success}
    )

    return ToolResult(
        text=_format_text_output(result),
        data=result.to_dict(),
        workspace_payload={"type": "review_collection", "data": result.to_dict()}
    )


def _map_verification_status(status: str) -> OutcomeStatus:
    """Map verification status to outcome status."""
    mapping = {
        "confirmed": "complete",
        "not_found": "entity_not_found",
        "ambiguous": "entity_ambiguous",
        "gave_up": "entity_not_found",
        "error": "error"
    }
    return mapping.get(status, "error")


def _extract_from_page_content(source: str, business_name: str, page_content: str) -> Dict:
    """
    Direct LLM extraction from already-fetched page content.
    No agent loop needed - single LLM call.
    """
    import anthropic

    prompt = _get_page_extraction_prompt(source, business_name, page_content)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=4096,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = response.content[0].text

    # Parse JSON response
    parsed = None
    json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    if not parsed:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            parsed = {"artifacts": [], "analysis": {}}

    return parsed


def _run_reddit_agent(
    business_name: str,
    location: str,
    db: Session,
    user_id: int,
    context: Dict
) -> Generator[ToolProgress, None, Dict]:
    """Run agent to collect Reddit mentions."""
    global _current_tracker

    system_prompt = _get_artifact_extraction_prompt("reddit", business_name, "")

    messages = [
        {
            "role": "user",
            "content": f"Find Reddit discussions about {business_name} in {location}."
        }
    ]

    tools = {"search": SEARCH_TOOL, "fetch": FETCH_TOOL}

    event_queue: queue.Queue = queue.Queue()
    result_holder: List[Any] = [None, None, None]

    def run_agent():
        def on_event(event: AgentEvent):
            event_queue.put(event)

        try:
            final_text, tool_calls, error = run_agent_loop_sync(
                model=AGENT_MODEL,
                max_tokens=8096,
                max_iterations=MAX_AGENT_TURNS,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                db=db,
                user_id=user_id,
                context=context,
                temperature=0.2,
                on_event=on_event
            )
            result_holder[0] = final_text
            result_holder[1] = tool_calls
            result_holder[2] = error
        except Exception as e:
            logger.error(f"Reddit agent error: {e}", exc_info=True)
            result_holder[2] = str(e)
        finally:
            event_queue.put(None)

    agent_thread = threading.Thread(target=run_agent, daemon=True)
    agent_thread.start()

    # Forward progress
    search_count = 0
    fetch_count = 0

    while True:
        try:
            event = event_queue.get(timeout=0.5)
            if event is None:
                break

            if isinstance(event, AgentToolStart):
                if event.tool_name == "search":
                    search_count += 1
                    _current_tracker.start_step("search", str(event.tool_input))
                    yield ToolProgress(
                        stage="reddit_search",
                        message=f"Searching Reddit [{search_count}]",
                        data={"search_count": search_count}
                    )
                else:
                    fetch_count += 1
                    _current_tracker.start_step("fetch", str(event.tool_input))
                    yield ToolProgress(
                        stage="reddit_fetch",
                        message=f"Fetching Reddit [{fetch_count}]",
                        data={"fetch_count": fetch_count}
                    )

            elif isinstance(event, AgentToolComplete):
                _current_tracker.complete_step("success", [])

        except queue.Empty:
            continue

    agent_thread.join(timeout=5.0)

    # Parse result
    agent_text = result_holder[0] or ""
    parsed = None

    json_match = re.search(r'```json\s*(.*?)\s*```', agent_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    if not parsed:
        try:
            parsed = json.loads(agent_text)
        except json.JSONDecodeError:
            parsed = {"artifacts": [], "analysis": {}}

    return parsed


def _run_extraction_agent(
    source: str,
    business_name: str,
    entity_url: str,
    db: Session,
    user_id: int,
    context: Dict
) -> Generator[ToolProgress, None, Dict]:
    """Fallback: run agent to fetch and extract reviews."""
    global _current_tracker

    system_prompt = _get_artifact_extraction_prompt(source, business_name, entity_url)

    messages = [
        {
            "role": "user",
            "content": f"Fetch {entity_url} and extract the reviews."
        }
    ]

    tools = {"search": SEARCH_TOOL, "fetch": FETCH_TOOL}

    event_queue: queue.Queue = queue.Queue()
    result_holder: List[Any] = [None, None, None]

    def run_agent():
        def on_event(event: AgentEvent):
            event_queue.put(event)

        try:
            final_text, tool_calls, error = run_agent_loop_sync(
                model=AGENT_MODEL,
                max_tokens=8096,
                max_iterations=10,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                db=db,
                user_id=user_id,
                context=context,
                temperature=0.2,
                on_event=on_event
            )
            result_holder[0] = final_text
            result_holder[1] = tool_calls
            result_holder[2] = error
        except Exception as e:
            logger.error(f"Extraction agent error: {e}", exc_info=True)
            result_holder[2] = str(e)
        finally:
            event_queue.put(None)

    agent_thread = threading.Thread(target=run_agent, daemon=True)
    agent_thread.start()

    while True:
        try:
            event = event_queue.get(timeout=0.5)
            if event is None:
                break

            if isinstance(event, AgentToolStart):
                if event.tool_name == "fetch":
                    _current_tracker.start_step("fetch", str(event.tool_input))
                    yield ToolProgress(
                        stage="extracting_fetch",
                        message=f"Fetching {source.upper()} page",
                        data={}
                    )

            elif isinstance(event, AgentToolComplete):
                _current_tracker.complete_step("success", [])

        except queue.Empty:
            continue

    agent_thread.join(timeout=5.0)

    # Parse result
    agent_text = result_holder[0] or ""
    parsed = None

    json_match = re.search(r'```json\s*(.*?)\s*```', agent_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    if not parsed:
        try:
            parsed = json.loads(agent_text)
        except json.JSONDecodeError:
            parsed = {"artifacts": [], "analysis": {}}

    return parsed


def _build_final_result(
    tracker: JourneyTracker,
    artifacts_data: Dict,
    source: str
) -> ReviewCollectionResult:
    """Build the final result from artifacts data."""

    # Parse artifacts
    for artifact_data in artifacts_data.get("artifacts", []):
        if source == "reddit":
            tracker.artifacts.append(RedditArtifact(
                text=artifact_data.get("text", ""),
                author=artifact_data.get("author", "unknown"),
                subreddit=artifact_data.get("subreddit", ""),
                url=artifact_data.get("url", ""),
                title=artifact_data.get("title"),
                score=artifact_data.get("score"),
                date=artifact_data.get("date")
            ))
        else:
            tracker.artifacts.append(ReviewArtifact(
                rating=artifact_data.get("rating"),
                text=artifact_data.get("text", ""),
                author=artifact_data.get("author"),
                date=artifact_data.get("date"),
                url=artifact_data.get("url")
            ))

    # Parse analysis
    analysis_data = artifacts_data.get("analysis", {})
    if analysis_data:
        tracker.analysis = Analysis(
            sentiment=analysis_data.get("sentiment", ""),
            themes=analysis_data.get("themes", []),
            notable_quotes=analysis_data.get("notable_quotes", [])
        )

    # Update rating info from rating_summary if present
    rating_summary = artifacts_data.get("rating_summary", {})
    if rating_summary and tracker.entity:
        tracker.entity.rating = rating_summary.get("overall")
        tracker.entity.review_count = rating_summary.get("total_reviews")

    # Determine outcome
    artifact_count = len(tracker.artifacts)

    if artifact_count == 0:
        tracker.set_phase_conclusion("No reviews extracted", "failed")
        return tracker.finalize(Outcome(
            success=False,
            status="partial",
            confidence="medium",
            summary="Entity found but no reviews extracted"
        ))

    # Success
    tracker.set_phase_conclusion(f"Collected {artifact_count} reviews", "success")

    entity_name = tracker.entity.name if tracker.entity else tracker.request.business_name
    rating_str = f"{tracker.entity.rating}★" if tracker.entity and tracker.entity.rating else ""

    summary = f"Found {artifact_count} reviews"
    if rating_str:
        summary += f" • {rating_str}"
    summary += f" • {entity_name}"

    confidence = "high" if tracker.entity and tracker.entity.match_confidence == "high" else "medium"

    return tracker.finalize(Outcome(
        success=True,
        status="complete",
        confidence=confidence,
        summary=summary
    ))


def _format_text_output(result: ReviewCollectionResult) -> str:
    """Format result as human-readable text for chat."""
    lines = []

    # Header
    lines.append(f"## {result.request.source.upper()} Review Collection")
    lines.append("")

    # Outcome
    status_emoji = "✅" if result.outcome.success else "❌"
    lines.append(f"{status_emoji} **{result.outcome.status.upper()}** - {result.outcome.confidence} confidence")
    lines.append(f"{result.outcome.summary}")
    lines.append("")

    # Entity
    if result.entity:
        lines.append("### Entity Found")
        lines.append(f"- **Name:** {result.entity.name}")
        lines.append(f"- **URL:** {result.entity.url}")
        if result.entity.rating:
            lines.append(f"- **Rating:** {result.entity.rating}/5")
        if result.entity.review_count:
            lines.append(f"- **Reviews:** {result.entity.review_count}")
        lines.append(f"- **Match:** {result.entity.match_confidence} - {result.entity.match_reason}")
        lines.append("")

    # Artifacts preview
    if result.artifacts:
        lines.append(f"### Reviews ({len(result.artifacts)} collected)")
        for i, artifact in enumerate(result.artifacts[:3], 1):
            if isinstance(artifact, ReviewArtifact):
                rating_str = f"{'★' * int(artifact.rating or 0)} " if artifact.rating else ""
                text_preview = artifact.text[:150] + "..." if len(artifact.text) > 150 else artifact.text
                lines.append(f"{i}. {rating_str}\"{text_preview}\"")
                if artifact.author:
                    lines.append(f"   — {artifact.author}")
            else:
                lines.append(f"{i}. r/{artifact.subreddit}: {artifact.title or artifact.text[:100]}")
        if len(result.artifacts) > 3:
            lines.append(f"   ... and {len(result.artifacts) - 3} more")
        lines.append("")

    # Journey summary
    journey = result.journey
    lines.append(f"### Journey ({journey.duration_ms}ms)")
    stats = journey.tool_calls
    lines.append(f"- Searches: {stats.searches['successful']}/{stats.searches['attempted']}")
    lines.append(f"- Fetches: {stats.fetches['successful']}/{stats.fetches['attempted']}" +
                 (f" ({stats.fetches['blocked']} blocked)" if stats.fetches['blocked'] > 0 else ""))

    if journey.obstacles:
        lines.append(f"- Obstacles: {len(journey.obstacles)}")
        for obs in journey.obstacles:
            lines.append(f"  - {obs.type}: {obs.description}")

    return "\n".join(lines)


# =============================================================================
# Tool Registration
# =============================================================================

REVIEW_COLLECTOR_TOOL = ToolConfig(
    name="collect_reviews",
    description="""Collect reviews for a business from a SINGLE source (yelp, google, or reddit).

    This tool:
    1. First verifies it can uniquely identify the business on the platform
    2. If verification fails, returns an error with details
    3. If verified, collects actual review artifacts (not summaries)
    4. Returns detailed journey telemetry for debugging

    Use this when you need reliable review data from a specific platform.""",
    input_schema={
        "type": "object",
        "properties": {
            "business_name": {
                "type": "string",
                "description": "Name of the business"
            },
            "location": {
                "type": "string",
                "description": "City and state (e.g., 'Cambridge, MA')"
            },
            "source": {
                "type": "string",
                "enum": ["yelp", "google", "reddit"],
                "description": "The platform to collect reviews from"
            }
        },
        "required": ["business_name", "location", "source"]
    },
    executor=execute_review_collector,
    category="research",
    streaming=True
)


def register_review_collector_tools():
    """Register review collector tools."""
    register_tool(REVIEW_COLLECTOR_TOOL)
    logger.info("Registered collect_reviews tool")
