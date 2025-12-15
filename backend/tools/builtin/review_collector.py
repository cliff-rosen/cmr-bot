"""
Review Collector Tool (Agentic)

Collects reviews from a SINGLE source (Yelp, Google, or Reddit) with strict
entity verification before collection.

Architecture:
1. Entity Resolution - Must uniquely identify the business or fail
2. Artifact Collection - Gather actual reviews/posts with collection profile
3. Analysis - Summarize findings and collection effort
"""

import json
import logging
import queue
import re
import threading
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Generator, Literal, Union
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


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class EntityInfo:
    """Verified entity information from a platform."""
    name: str
    url: str
    platform: str
    platform_id: Optional[str] = None
    overall_rating: Optional[float] = None
    total_reviews: Optional[int] = None

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
        return asdict(self)


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
    artifact_type: str = "post"  # "post" or "comment"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionProfile:
    """
    Narrative about how the collection effort went.

    This tells the story: Was it easy? Hard? Rich with content or sparse?
    Did we hit obstacles? How confident are we in what we found?
    """
    confidence: str  # "high", "medium", "low"
    richness: str  # "abundant", "moderate", "sparse", "none"
    obstacles: List[str] = field(default_factory=list)
    narrative: str = ""  # Human-readable story of the collection effort
    searches_performed: int = 0
    pages_fetched: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CollectionResult:
    """Complete result of a review collection attempt."""
    success: bool
    source: str
    entity: Optional[EntityInfo] = None
    artifacts: List[Union[ReviewArtifact, RedditArtifact]] = field(default_factory=list)
    analysis: Dict[str, Any] = field(default_factory=dict)
    collection_profile: Optional[CollectionProfile] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # "entity_not_found", "entity_ambiguous", "collection_failed"
    candidates: List[Dict[str, Any]] = field(default_factory=list)  # If ambiguous

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "source": self.source,
            "error": self.error,
            "error_type": self.error_type,
        }
        if self.entity:
            result["entity"] = self.entity.to_dict()
        if self.artifacts:
            result["artifacts"] = [a.to_dict() for a in self.artifacts]
        if self.analysis:
            result["analysis"] = self.analysis
        if self.collection_profile:
            result["collection_profile"] = self.collection_profile.to_dict()
        if self.candidates:
            result["candidates"] = self.candidates
        return result


# =============================================================================
# Tools available to the review collector agent
# =============================================================================

def _execute_search(params: Dict[str, Any], db: Session, user_id: int, context: Dict) -> ToolResult:
    """Search tool for the review collector agent."""
    from services.search_service import SearchService

    query = params.get("query", "")
    if not query:
        return ToolResult(text="Error: No query provided")

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

        if not results:
            return ToolResult(text="No results found for this query.")

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
        return ToolResult(text=f"Search error: {str(e)}")


def _execute_fetch(params: Dict[str, Any], db: Session, user_id: int, context: Dict) -> ToolResult:
    """Fetch tool for the review collector agent."""
    from services.web_retrieval_service import WebRetrievalService

    url = params.get("url", "")
    if not url:
        return ToolResult(text="Error: No URL provided")

    try:
        web_service = WebRetrievalService()

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                web_service.retrieve_webpage(url=url, extract_text_only=True)
            )
        finally:
            loop.close()

        webpage = result["webpage"]
        content = webpage.content

        if len(content) > 12000:
            content = content[:12000] + "\n\n[Content truncated]"

        return ToolResult(text=f"Page: {webpage.title}\nURL: {url}\n\nContent:\n{content}")

    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        return ToolResult(text=f"Failed to fetch page: {str(e)}")


# Tool configurations for the agent
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
# System Prompts for Each Source
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
- AMBIGUOUS: You found multiple potential matches (list them)
- NOT_FOUND: You could not find this business on the platform

If AMBIGUOUS or NOT_FOUND, STOP and report the failure immediately with this JSON:
```json
{{
  "phase": "entity_resolution",
  "status": "failed",
  "reason": "ambiguous" or "not_found",
  "candidates": [  // if ambiguous, list what you found
    {{"name": "...", "url": "...", "why_uncertain": "..."}}
  ],
  "searches_tried": ["query1", "query2"]
}}
```

If FOUND, report success and proceed to Phase 2:
```json
{{
  "phase": "entity_resolution",
  "status": "success",
  "entity": {{
    "name": "exact name as shown on platform",
    "url": "direct URL to the business page",
    "platform_id": "if visible (e.g., yelp biz id)",
    "overall_rating": 4.5,
    "total_reviews": 127
  }}
}}
```

==============================================================================
PHASE 2: ARTIFACT COLLECTION (only if Phase 1 succeeded)
==============================================================================

Now collect actual review content from the verified entity. Your goal is to gather
REAL ARTIFACTS - the actual text of reviews, not summaries about reviews.

"""

    if source == "yelp":
        source_instructions = """
For YELP:
- The entity URL should be like: yelp.com/biz/business-name-city
- Fetch the business page to get reviews
- Note: Yelp often blocks JavaScript content. If you can't see reviews, note this as an obstacle.
- Try to extract: rating (1-5 stars), review text, author name, date
- Look for "Recommended Reviews" section

"""
    elif source == "google":
        source_instructions = """
For GOOGLE:
- Search for the business + "reviews" to find Google Maps/Business listing
- Google reviews are often embedded in search results or Maps
- Try to extract: rating (1-5 stars), review text, author name, date
- Alternative: Look for reviews on the business's Google Business Profile

"""
    elif source == "reddit":
        source_instructions = """
For REDDIT:
- Search: site:reddit.com "{business_name}" {location}
- Look for posts/comments discussing this specific business
- Collect posts from relevant subreddits (local city subs, industry subs)
- Extract: post title, text content, author, subreddit, score, URL
- Both posts and substantive comments count as artifacts

"""
    else:
        source_instructions = ""

    collection_instructions = """
As you collect, track your COLLECTION PROFILE - the story of how this went:
- How confident are you in the entity match?
- Was content abundant, moderate, sparse, or none?
- What obstacles did you hit? (JS blocking, rate limiting, no reviews visible, etc.)
- How many searches did you do? How many pages did you fetch?

==============================================================================
FINAL OUTPUT
==============================================================================

When done, provide your final report as JSON:
```json
{
  "entity": {
    "name": "...",
    "url": "...",
    "platform_id": "...",
    "overall_rating": 4.5,
    "total_reviews": 127
  },
  "artifacts": [
    {"rating": 5, "text": "actual review text here...", "author": "John D.", "date": "2024-01-15"},
    {"rating": 4, "text": "another review...", "author": "Jane S.", "date": "2024-01-10"}
    // For Reddit: {"title": "...", "text": "...", "author": "...", "subreddit": "...", "score": 42, "url": "..."}
  ],
  "analysis": {
    "sentiment_summary": "Generally positive with concerns about...",
    "key_themes": ["professional", "expensive", "long wait"],
    "notable_quotes": ["best experience ever", "would not recommend"]
  },
  "collection_profile": {
    "confidence": "high/medium/low",
    "richness": "abundant/moderate/sparse/none",
    "obstacles": ["list any issues encountered"],
    "narrative": "A 2-3 sentence story of how the collection went. Was it easy? Hard? What did you try?",
    "searches_performed": 5,
    "pages_fetched": 3
  }
}
```

IMPORTANT RULES:
1. Phase 1 MUST complete successfully before Phase 2
2. If you cannot uniquely identify the entity, FAIL IMMEDIATELY - do not guess
3. Artifacts must be ACTUAL content, not summaries
4. Be honest about obstacles and confidence level
5. The collection_profile narrative should read like a brief story of your research journey
"""

    return base_instructions + source_instructions + collection_instructions


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

    business_name = params.get("business_name", "")
    location = params.get("location", "")
    source = params.get("source", "").lower()

    # Validate inputs
    if not business_name:
        return ToolResult(
            text="Error: business_name is required",
            data=CollectionResult(success=False, source="", error="business_name is required").to_dict()
        )
    if not location:
        return ToolResult(
            text="Error: location is required",
            data=CollectionResult(success=False, source="", error="location is required").to_dict()
        )
    if source not in ("yelp", "google", "reddit"):
        return ToolResult(
            text=f"Error: source must be 'yelp', 'google', or 'reddit', got '{source}'",
            data=CollectionResult(success=False, source=source, error="invalid source").to_dict()
        )

    yield ToolProgress(
        stage="starting",
        message=f"Collecting {source.upper()} reviews for {business_name}",
        data={"business_name": business_name, "location": location, "source": source}
    )

    # Build the system prompt for this source
    system_prompt = _get_system_prompt(source, business_name, location)

    # Initial message
    messages = [
        {
            "role": "user",
            "content": f"Find and collect {source} reviews for {business_name} in {location}. "
                       f"Remember: First verify you can uniquely identify this exact business, "
                       f"then collect actual review artifacts."
        }
    ]

    # Tools available to this agent
    tools = {
        "search": SEARCH_TOOL,
        "fetch": FETCH_TOOL
    }

    # Queue for events from the agent loop
    event_queue: queue.Queue = queue.Queue()
    result_holder: List[Any] = [None, None, None]

    def run_agent():
        """Run the agent loop in a background thread."""
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

    # Start agent in background thread
    agent_thread = threading.Thread(target=run_agent, daemon=True)
    agent_thread.start()

    # Yield progress events
    tool_call_count = 0
    current_phase = "entity_resolution"

    while True:
        try:
            event = event_queue.get(timeout=0.5)
            if event is None:
                break

            if isinstance(event, AgentToolStart):
                tool_call_count += 1
                input_summary = str(event.tool_input)
                if len(input_summary) > 100:
                    input_summary = input_summary[:100] + "..."
                yield ToolProgress(
                    stage=current_phase,
                    message=f"[{tool_call_count}] {event.tool_name}: {input_summary}",
                    data={"tool": event.tool_name, "input": event.tool_input, "phase": current_phase}
                )
            elif isinstance(event, AgentToolComplete):
                yield ToolProgress(
                    stage=current_phase,
                    message=f"{event.tool_name} complete",
                    data={"tool": event.tool_name, "phase": current_phase}
                )
        except queue.Empty:
            continue

    agent_thread.join(timeout=5.0)

    yield ToolProgress(
        stage="parsing",
        message=f"Parsing results from {tool_call_count} tool calls",
        data={"tool_calls": tool_call_count}
    )

    # Parse and build result
    result = _parse_agent_output(
        source=source,
        business_name=business_name,
        location=location,
        agent_text=result_holder[0] or "",
        tool_calls=result_holder[1] or [],
        error=result_holder[2]
    )

    # Build text output
    text_output = _format_text_output(result)

    yield ToolProgress(
        stage="complete",
        message=f"Collection complete: {result.collection_profile.confidence if result.collection_profile else 'unknown'} confidence",
        data={"success": result.success}
    )

    return ToolResult(text=text_output, data=result.to_dict())


def _parse_agent_output(
    source: str,
    business_name: str,
    location: str,
    agent_text: str,
    tool_calls: List[Dict],
    error: Optional[str]
) -> CollectionResult:
    """Parse the agent's output into a structured CollectionResult."""

    if error:
        return CollectionResult(
            success=False,
            source=source,
            error=f"Agent error: {error}",
            error_type="agent_error",
            collection_profile=CollectionProfile(
                confidence="low",
                richness="none",
                narrative=f"Agent encountered an error: {error}",
                searches_performed=len([t for t in tool_calls if t.get("tool_name") == "search"]),
                pages_fetched=len([t for t in tool_calls if t.get("tool_name") == "fetch"])
            )
        )

    # Try to parse JSON from the agent's response
    parsed = None

    # Look for JSON block
    json_match = re.search(r'```json\s*(.*?)\s*```', agent_text, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try parsing whole response as JSON
    if not parsed:
        try:
            parsed = json.loads(agent_text)
        except json.JSONDecodeError:
            pass

    # Check for entity resolution failure
    if parsed and parsed.get("phase") == "entity_resolution" and parsed.get("status") == "failed":
        reason = parsed.get("reason", "unknown")
        return CollectionResult(
            success=False,
            source=source,
            error=f"Could not uniquely identify entity: {reason}",
            error_type=f"entity_{reason}",
            candidates=parsed.get("candidates", []),
            collection_profile=CollectionProfile(
                confidence="low",
                richness="none",
                narrative=f"Entity resolution failed: {reason}. Searches tried: {parsed.get('searches_tried', [])}",
                searches_performed=len(parsed.get("searches_tried", []))
            )
        )

    # Parse successful collection
    if parsed:
        # Entity
        entity = None
        entity_data = parsed.get("entity")
        if entity_data:
            entity = EntityInfo(
                name=entity_data.get("name", business_name),
                url=entity_data.get("url", ""),
                platform=source,
                platform_id=entity_data.get("platform_id"),
                overall_rating=entity_data.get("overall_rating"),
                total_reviews=entity_data.get("total_reviews")
            )

        # Artifacts
        artifacts = []
        for artifact_data in parsed.get("artifacts", []):
            if source == "reddit":
                artifacts.append(RedditArtifact(
                    text=artifact_data.get("text", ""),
                    author=artifact_data.get("author", "unknown"),
                    subreddit=artifact_data.get("subreddit", ""),
                    url=artifact_data.get("url", ""),
                    title=artifact_data.get("title"),
                    score=artifact_data.get("score"),
                    date=artifact_data.get("date"),
                    artifact_type=artifact_data.get("artifact_type", "post")
                ))
            else:
                artifacts.append(ReviewArtifact(
                    rating=artifact_data.get("rating"),
                    text=artifact_data.get("text", ""),
                    author=artifact_data.get("author"),
                    date=artifact_data.get("date"),
                    url=artifact_data.get("url")
                ))

        # Collection profile
        profile_data = parsed.get("collection_profile", {})
        collection_profile = CollectionProfile(
            confidence=profile_data.get("confidence", "medium"),
            richness=profile_data.get("richness", "moderate"),
            obstacles=profile_data.get("obstacles", []),
            narrative=profile_data.get("narrative", ""),
            searches_performed=profile_data.get("searches_performed", len([t for t in tool_calls if t.get("tool_name") == "search"])),
            pages_fetched=profile_data.get("pages_fetched", len([t for t in tool_calls if t.get("tool_name") == "fetch"]))
        )

        # Analysis
        analysis = parsed.get("analysis", {})

        return CollectionResult(
            success=True,
            source=source,
            entity=entity,
            artifacts=artifacts,
            analysis=analysis,
            collection_profile=collection_profile
        )

    # Couldn't parse - return failure with raw text
    return CollectionResult(
        success=False,
        source=source,
        error="Could not parse agent output",
        error_type="parse_error",
        collection_profile=CollectionProfile(
            confidence="low",
            richness="none",
            narrative=f"Agent completed but output could not be parsed. Raw output: {agent_text[:500]}...",
            searches_performed=len([t for t in tool_calls if t.get("tool_name") == "search"]),
            pages_fetched=len([t for t in tool_calls if t.get("tool_name") == "fetch"])
        )
    )


def _format_text_output(result: CollectionResult) -> str:
    """Format CollectionResult as human-readable text."""
    lines = []

    lines.append(f"## {result.source.upper()} Review Collection")
    lines.append("")

    if not result.success:
        lines.append(f"**Status:** FAILED")
        lines.append(f"**Error:** {result.error}")
        if result.error_type:
            lines.append(f"**Error Type:** {result.error_type}")
        if result.candidates:
            lines.append("")
            lines.append("**Candidates Found:**")
            for c in result.candidates:
                lines.append(f"  - {c.get('name', 'Unknown')}: {c.get('url', '')}")
    else:
        lines.append(f"**Status:** SUCCESS")

        if result.entity:
            lines.append("")
            lines.append("### Entity")
            lines.append(f"- **Name:** {result.entity.name}")
            lines.append(f"- **URL:** {result.entity.url}")
            if result.entity.overall_rating:
                lines.append(f"- **Rating:** {result.entity.overall_rating}/5")
            if result.entity.total_reviews:
                lines.append(f"- **Total Reviews:** {result.entity.total_reviews}")

        if result.artifacts:
            lines.append("")
            lines.append(f"### Artifacts ({len(result.artifacts)} collected)")
            for i, artifact in enumerate(result.artifacts[:5], 1):  # Show first 5
                if isinstance(artifact, ReviewArtifact):
                    rating_str = f"[{artifact.rating}/5] " if artifact.rating else ""
                    author_str = f" - {artifact.author}" if artifact.author else ""
                    text_preview = artifact.text[:200] + "..." if len(artifact.text) > 200 else artifact.text
                    lines.append(f"{i}. {rating_str}\"{text_preview}\"{author_str}")
                elif isinstance(artifact, RedditArtifact):
                    lines.append(f"{i}. r/{artifact.subreddit}: {artifact.title or artifact.text[:100]}")
            if len(result.artifacts) > 5:
                lines.append(f"   ... and {len(result.artifacts) - 5} more")

        if result.analysis:
            lines.append("")
            lines.append("### Analysis")
            if result.analysis.get("sentiment_summary"):
                lines.append(f"- **Sentiment:** {result.analysis['sentiment_summary']}")
            if result.analysis.get("key_themes"):
                lines.append(f"- **Key Themes:** {', '.join(result.analysis['key_themes'])}")

    if result.collection_profile:
        lines.append("")
        lines.append("### Collection Profile")
        lines.append(f"- **Confidence:** {result.collection_profile.confidence}")
        lines.append(f"- **Richness:** {result.collection_profile.richness}")
        lines.append(f"- **Effort:** {result.collection_profile.searches_performed} searches, {result.collection_profile.pages_fetched} pages fetched")
        if result.collection_profile.obstacles:
            lines.append(f"- **Obstacles:** {', '.join(result.collection_profile.obstacles)}")
        if result.collection_profile.narrative:
            lines.append(f"- **Narrative:** {result.collection_profile.narrative}")

    return "\n".join(lines)


# =============================================================================
# Tool Registration
# =============================================================================

REVIEW_COLLECTOR_TOOL = ToolConfig(
    name="collect_reviews",
    description="""Collect reviews for a business from a SINGLE source (yelp, google, or reddit).

    This tool:
    1. First verifies it can uniquely identify the business on the platform
    2. If verification fails, returns an error with candidates found
    3. If verified, collects actual review artifacts (not summaries)
    4. Returns structured data including collection confidence profile

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
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "source": {"type": "string"},
            "entity": {"type": "object"},
            "artifacts": {"type": "array"},
            "analysis": {"type": "object"},
            "collection_profile": {"type": "object"},
            "error": {"type": "string"},
            "error_type": {"type": "string"},
            "candidates": {"type": "array"}
        }
    },
    executor=execute_review_collector,
    category="research",
    streaming=True
)


def register_review_collector_tools():
    """Register review collector tools."""
    register_tool(REVIEW_COLLECTOR_TOOL)
    logger.info("Registered collect_reviews tool")
