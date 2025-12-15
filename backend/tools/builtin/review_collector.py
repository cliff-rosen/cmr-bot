"""
Review Collector Tool (Agentic)

Collects reviews from a SINGLE source (Yelp, Google, or Reddit) with strict
entity verification before collection.

Returns a journey-based payload that tells the story of the collection effort.
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
        import asyncio

        if needs_js:
            from services.js_web_retrieval_service import fetch_with_js

            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    fetch_with_js(url=url, timeout=45000, wait_after_load=3000)
                )
            finally:
                loop.close()

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
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    web_service.retrieve_webpage(url=url, extract_text_only=True)
                )
            finally:
                loop.close()

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
# System Prompts
# =============================================================================

def _get_system_prompt(source: SourceType, business_name: str, location: str) -> str:
    """Get the appropriate system prompt for the source."""

    base_instructions = f"""You are a precise research agent collecting reviews for a specific business.

TARGET BUSINESS: "{business_name}" in "{location}"
SOURCE PLATFORM: {source.upper()}

YOUR TASK HAS TWO PHASES:

==============================================================================
PHASE 1: ENTITY RESOLUTION (MUST COMPLETE FIRST)
==============================================================================

You MUST first verify you can uniquely identify this exact business on {source.upper()}.

Search for the business. Then determine:
- FOUND: You found exactly ONE matching business entity
- AMBIGUOUS: You found multiple potential matches
- NOT_FOUND: You could not find this business on the platform

If AMBIGUOUS or NOT_FOUND, STOP and report immediately.

==============================================================================
PHASE 2: ARTIFACT COLLECTION (only if Phase 1 succeeded)
==============================================================================

Collect actual review content. Get REAL TEXT from reviews, not summaries.

==============================================================================
FINAL OUTPUT - ALWAYS USE THIS JSON FORMAT
==============================================================================

```json
{{
  "entity_resolution": {{
    "status": "found" | "ambiguous" | "not_found",
    "entity": {{
      "name": "exact name on platform",
      "url": "direct URL",
      "platform_id": "if visible",
      "rating": 4.5,
      "review_count": 16,
      "match_confidence": "exact" | "probable" | "uncertain",
      "match_reason": "why you're confident this is the right business"
    }},
    "candidates": []  // if ambiguous, list alternatives
  }},
  "artifacts": [
    {{"rating": 5, "text": "actual review text...", "author": "Name", "date": "date"}}
  ],
  "analysis": {{
    "sentiment": "overall sentiment description",
    "themes": ["theme1", "theme2"],
    "notable_quotes": ["quote1", "quote2"]
  }},
  "collection_notes": "Brief notes on how collection went, any issues"
}}
```

RULES:
1. Entity resolution MUST succeed before collecting artifacts
2. If entity not found or ambiguous, return immediately with status
3. Artifacts must be ACTUAL review text, not summaries
4. Be specific in match_reason - address, phone, name match, etc.
"""

    if source == "yelp":
        source_instructions = """
YELP SPECIFICS:
- Business URLs look like: yelp.com/biz/business-name-city
- Rating is X.X out of 5 stars
- Look for "Recommended Reviews" section
- Note if page seems blocked or limited
"""
    elif source == "google":
        source_instructions = """
GOOGLE SPECIFICS:
- Look for Google Business Profile / Google Maps listing
- Rating is X.X out of 5 stars
- Reviews may be in search snippets or Maps
"""
    elif source == "reddit":
        source_instructions = """
REDDIT SPECIFICS:
- Search: site:reddit.com "business name" location
- Collect posts AND comments mentioning the business
- Note the subreddit and vote score
- Artifacts should include: title, text, author, subreddit, score, url
"""
    else:
        source_instructions = ""

    return base_instructions + source_instructions


# =============================================================================
# Main Executor
# =============================================================================

def execute_review_collector(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """Execute the review collector for a single source."""
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

    # Build the system prompt
    system_prompt = _get_system_prompt(source, business_name, location)

    messages = [
        {
            "role": "user",
            "content": f"Find and collect {source} reviews for {business_name} in {location}."
        }
    ]

    tools = {"search": SEARCH_TOOL, "fetch": FETCH_TOOL}

    # Queue for events
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
            logger.error(f"Agent thread error: {e}", exc_info=True)
            result_holder[2] = str(e)
        finally:
            event_queue.put(None)

    # Start agent
    agent_thread = threading.Thread(target=run_agent, daemon=True)
    agent_thread.start()

    # Yield progress events
    current_phase_name = "entity_resolution"

    while True:
        try:
            event = event_queue.get(timeout=0.5)
            if event is None:
                break

            if isinstance(event, AgentToolStart):
                tool_name = event.tool_name
                input_summary = str(event.tool_input)
                if len(input_summary) > 80:
                    input_summary = input_summary[:80] + "..."

                yield ToolProgress(
                    stage=current_phase_name,
                    message=f"{tool_name}: {input_summary}",
                    data={"tool": tool_name, "input": event.tool_input, "phase": current_phase_name}
                )
            elif isinstance(event, AgentToolComplete):
                # Check if we should transition to artifact collection phase
                result_lower = event.result_text.lower() if event.result_text else ""
                if current_phase_name == "entity_resolution" and "review" in result_lower:
                    # Might be transitioning to artifact collection
                    pass

                yield ToolProgress(
                    stage=current_phase_name,
                    message=f"{event.tool_name} complete",
                    data={"tool": event.tool_name, "phase": current_phase_name}
                )
        except queue.Empty:
            continue

    agent_thread.join(timeout=5.0)

    yield ToolProgress(
        stage="parsing",
        message="Parsing agent results",
        data={}
    )

    # Parse and build result
    result = _parse_agent_output(
        tracker=_current_tracker,
        agent_text=result_holder[0] or "",
        tool_calls=result_holder[1] or [],
        error=result_holder[2]
    )

    # Clear global tracker
    _current_tracker = None

    # Build text output for chat
    text_output = _format_text_output(result)

    yield ToolProgress(
        stage="complete",
        message=f"Collection {result.outcome.status}: {result.outcome.summary}",
        data={"success": result.outcome.success}
    )

    return ToolResult(
        text=text_output,
        data=result.to_dict(),
        workspace_payload={
            "type": "review_collection",
            "data": result.to_dict()
        }
    )


def _parse_agent_output(
    tracker: JourneyTracker,
    agent_text: str,
    tool_calls: List[Dict],
    error: Optional[str]
) -> ReviewCollectionResult:
    """Parse the agent's output and finalize the journey."""

    if error:
        tracker.set_phase_conclusion(f"Agent error: {error}", "failed")
        return tracker.finalize(Outcome(
            success=False,
            status="error",
            confidence="low",
            summary=f"Agent error: {error}"
        ))

    # Try to parse JSON
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
            pass

    if not parsed:
        tracker.set_phase_conclusion("Could not parse agent output", "failed")
        tracker.add_obstacle("parse_error", "Agent output not valid JSON", "Could not extract structured data")
        return tracker.finalize(Outcome(
            success=False,
            status="error",
            confidence="low",
            summary="Could not parse agent response"
        ))

    # Parse entity resolution
    entity_res = parsed.get("entity_resolution", {})
    entity_status = entity_res.get("status", "not_found")

    if entity_status == "not_found":
        tracker.set_phase_conclusion("Entity not found on platform", "failed")
        return tracker.finalize(Outcome(
            success=False,
            status="entity_not_found",
            confidence="low",
            summary=f"Could not find {tracker.request.business_name} on {tracker.request.source.upper()}"
        ))

    if entity_status == "ambiguous":
        candidates = entity_res.get("candidates", [])
        tracker.set_phase_conclusion(f"Found {len(candidates)} potential matches, could not resolve", "failed")
        return tracker.finalize(Outcome(
            success=False,
            status="entity_ambiguous",
            confidence="low",
            summary=f"Found multiple potential matches, could not uniquely identify"
        ))

    # Entity found - parse it
    entity_data = entity_res.get("entity", {})
    tracker.entity = Entity(
        name=entity_data.get("name", tracker.request.business_name),
        url=entity_data.get("url", ""),
        platform_id=entity_data.get("platform_id"),
        rating=entity_data.get("rating"),
        review_count=entity_data.get("review_count"),
        match_confidence=entity_data.get("match_confidence", "uncertain"),
        match_reason=entity_data.get("match_reason", "")
    )

    tracker.set_phase_conclusion(
        f"Found: {tracker.entity.name} ({tracker.entity.match_confidence} match)",
        "success"
    )

    # Start artifact collection phase
    tracker.start_phase("artifact_collection")

    # Parse artifacts
    source = tracker.request.source
    for artifact_data in parsed.get("artifacts", []):
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
    analysis_data = parsed.get("analysis", {})
    if analysis_data:
        tracker.analysis = Analysis(
            sentiment=analysis_data.get("sentiment", ""),
            themes=analysis_data.get("themes", []),
            notable_quotes=analysis_data.get("notable_quotes", [])
        )

    # Determine outcome
    artifact_count = len(tracker.artifacts)
    review_count = tracker.entity.review_count or 0

    if artifact_count == 0:
        if tracker.journey.tool_calls.fetches["blocked"] > 0:
            tracker.set_phase_conclusion("Blocked from accessing review content", "failed")
            return tracker.finalize(Outcome(
                success=False,
                status="blocked",
                confidence="medium",
                summary=f"Found entity but blocked from accessing reviews"
            ))
        else:
            tracker.set_phase_conclusion("No reviews extracted", "failed")
            return tracker.finalize(Outcome(
                success=False,
                status="partial",
                confidence="medium",
                summary=f"Found entity but could not extract review content"
            ))

    # Success case
    if review_count > 0 and artifact_count < review_count:
        tracker.set_phase_conclusion(f"Collected {artifact_count} of {review_count} reviews", "partial")
        status = "partial"
        confidence = "medium"
    else:
        tracker.set_phase_conclusion(f"Collected {artifact_count} reviews", "success")
        status = "complete"
        confidence = "high" if tracker.entity.match_confidence == "exact" else "medium"

    rating_str = f"{tracker.entity.rating}★" if tracker.entity.rating else ""
    summary = f"Found {artifact_count} reviews"
    if rating_str:
        summary += f" • {rating_str} rating"
    summary += f" • {tracker.entity.name}"

    return tracker.finalize(Outcome(
        success=True,
        status=status,
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
