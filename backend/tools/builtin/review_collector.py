"""
Review Collector Tool (Agentic)

Uses the existing agent_loop infrastructure to run an agent that
collects business reviews using search and fetch tools.
"""

import logging
import queue
import threading
from typing import Dict, Any, List, Optional, Generator
from dataclasses import dataclass, field, asdict
from sqlalchemy.orm import Session

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from services.agent_loop import (
    run_agent_loop_sync,
    AgentEvent,
    AgentToolStart,
    AgentToolProgress,
    AgentToolComplete,
    AgentComplete,
    AgentError
)

logger = logging.getLogger(__name__)

# Configuration
AGENT_MODEL = "claude-sonnet-4-20250514"
MAX_AGENT_TURNS = 15


@dataclass
class ReviewData:
    """Structured review data collected by the agent."""
    source: str
    url: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    sample_reviews: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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
                search_service.search(search_term=query, num_results=8)
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
                output += f"   {snippet[:200]}\n"
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

        if len(content) > 8000:
            content = content[:8000] + "\n\n[Content truncated]"

        return ToolResult(text=f"Page: {webpage.title}\nURL: {url}\n\nContent:\n{content}")

    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        return ToolResult(text=f"Failed to fetch page: {str(e)}")


# Tool configurations for the agent
SEARCH_TOOL = ToolConfig(
    name="search",
    description="Search the web. Use site: operators like 'site:yelp.com/biz' to target specific sites.",
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
# Review Collector Execution
# =============================================================================

def execute_review_collector(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """Execute the review collector using the agent loop."""

    business_name = params.get("business_name", "")
    location = params.get("location", "")

    if not business_name:
        return ToolResult(text="Error: business_name is required")
    if not location:
        return ToolResult(text="Error: location is required")

    yield ToolProgress(
        stage="starting",
        message=f"Starting review collection for {business_name}",
        data={"business_name": business_name, "location": location}
    )

    # System prompt for the agent
    system_prompt = f"""You are a research agent collecting business reviews.

        GOAL: Find review information for "{business_name}" in "{location}"

        You need to find:
        1. YELP reviews - rating, review count, and sample review text
        2. GOOGLE reviews or alternatives (Healthgrades, TripAdvisor, etc.)

        STRATEGY:
        - Search for the business on Yelp (use site:yelp.com/biz)
        - Look at search results - titles often show review counts like "- 16 Reviews"
        - Fetch promising pages to get more details
        - If a page doesn't load well (JavaScript), try different approaches
        - Search for other review sources

        When you have enough information, respond with a JSON summary:
        ```json
        {{
        "yelp": {{
            "url": "...",
            "rating": 4.5,
            "review_count": 16,
            "sample_reviews": [{{"rating": 5, "text": "...", "author": "..."}}],
            "notes": "..."
        }},
        "google": {{
            "url": "...",
            "rating": 4.2,
            "review_count": 25,
            "sample_reviews": [...],
            "notes": "Found on Healthgrades instead of Google"
        }},
        "summary": "Brief summary of findings and confidence level"
        }}
        ```

        Be efficient - you have limited tool calls. Report what you find even if partial."""

    # Initial message
    messages = [
        {
            "role": "user",
            "content": f"Find review information for {business_name} in {location}."
        }
    ]

    # Tools available to this agent
    tools = {
        "search": SEARCH_TOOL,
        "fetch": FETCH_TOOL
    }

    # Queue for events from the agent loop running in background thread
    event_queue: queue.Queue = queue.Queue()
    result_holder: List[Any] = [None, None, None]  # [final_text, tool_calls, error]

    def run_agent():
        """Run the agent loop in a background thread."""
        def on_event(event: AgentEvent):
            event_queue.put(event)

        try:
            final_text, tool_calls, error = run_agent_loop_sync(
                model=AGENT_MODEL,
                max_tokens=4096,
                max_iterations=MAX_AGENT_TURNS,
                system_prompt=system_prompt,
                messages=messages,
                tools=tools,
                db=db,
                user_id=user_id,
                context=context,
                temperature=0.3,
                on_event=on_event
            )
            result_holder[0] = final_text
            result_holder[1] = tool_calls
            result_holder[2] = error
        except Exception as e:
            logger.error(f"Agent thread error: {e}", exc_info=True)
            result_holder[2] = str(e)
        finally:
            event_queue.put(None)  # Signal completion

    # Start agent in background thread
    agent_thread = threading.Thread(target=run_agent, daemon=True)
    agent_thread.start()

    # Yield progress events as they come from the agent
    tool_call_count = 0
    while True:
        try:
            event = event_queue.get(timeout=0.5)
            if event is None:
                break

            if isinstance(event, AgentToolStart):
                tool_call_count += 1
                # Format the tool input for display
                input_summary = str(event.tool_input)
                if len(input_summary) > 80:
                    input_summary = input_summary[:80] + "..."
                yield ToolProgress(
                    stage="tool_call",
                    message=f"[{tool_call_count}] {event.tool_name}: {input_summary}",
                    data={
                        "tool": event.tool_name,
                        "input": event.tool_input,
                        "tool_use_id": event.tool_use_id
                    }
                )
            elif isinstance(event, AgentToolProgress):
                # Forward inner tool progress
                yield ToolProgress(
                    stage="tool_progress",
                    message=f"{event.tool_name}: {event.progress.message}",
                    data={"tool": event.tool_name, "progress": event.progress.stage}
                )
            elif isinstance(event, AgentToolComplete):
                # Brief completion notice
                result_preview = event.result_text[:100] if event.result_text else "(no output)"
                if len(event.result_text or "") > 100:
                    result_preview += "..."
                yield ToolProgress(
                    stage="tool_complete",
                    message=f"{event.tool_name} done",
                    data={"tool": event.tool_name, "preview": result_preview}
                )
        except queue.Empty:
            continue

    agent_thread.join(timeout=5.0)

    yield ToolProgress(
        stage="complete",
        message=f"Agent completed with {tool_call_count} tool calls",
        data={"tool_calls": tool_call_count}
    )

    # Parse the agent's final response
    return _build_result(
        business_name,
        location,
        result_holder[0] or "",
        result_holder[1] or [],
        result_holder[2]
    )


def _build_result(
    business_name: str,
    location: str,
    agent_text: str,
    tool_calls: List[Dict],
    error: Optional[str]
) -> ToolResult:
    """Parse agent output and build structured result."""

    if error:
        return ToolResult(
            text=f"Agent error: {error}\n\nPartial output:\n{agent_text}",
            data={
                "business_name": business_name,
                "location": location,
                "sources": [],
                "error": error
            }
        )

    # Try to parse JSON from the agent's response
    import json
    import re

    findings = None

    # Look for JSON block in the response
    json_match = re.search(r'```json\s*(.*?)\s*```', agent_text, re.DOTALL)
    if json_match:
        try:
            findings = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Also try parsing the whole response as JSON
    if not findings:
        try:
            findings = json.loads(agent_text)
        except json.JSONDecodeError:
            pass

    sources = []
    if findings:
        if findings.get("yelp"):
            yelp = findings["yelp"]
            sources.append(ReviewData(
                source="yelp",
                url=yelp.get("url"),
                rating=yelp.get("rating"),
                review_count=yelp.get("review_count"),
                sample_reviews=yelp.get("sample_reviews", []),
                notes=yelp.get("notes", "")
            ))

        if findings.get("google"):
            google = findings["google"]
            sources.append(ReviewData(
                source="google",
                url=google.get("url"),
                rating=google.get("rating"),
                review_count=google.get("review_count"),
                sample_reviews=google.get("sample_reviews", []),
                notes=google.get("notes", "")
            ))

    # Build text output
    text_parts = [f"## Review Collection: {business_name} ({location})\n"]

    if findings and findings.get("summary"):
        text_parts.append(f"**Summary:** {findings['summary']}\n")

    for source in sources:
        text_parts.append(f"\n### {source.source.title()}")
        if source.url:
            text_parts.append(f"- URL: {source.url}")
        if source.rating:
            text_parts.append(f"- Rating: {source.rating}/5")
        if source.review_count:
            text_parts.append(f"- Review Count: {source.review_count}")
        if source.sample_reviews:
            text_parts.append(f"- Sample Reviews: {len(source.sample_reviews)}")
        if source.notes:
            text_parts.append(f"- Notes: {source.notes}")

    if not sources:
        text_parts.append("\nNo structured findings extracted.")
        text_parts.append(f"\nAgent response:\n{agent_text[:500]}")

    text_parts.append(f"\n\n*Agent made {len(tool_calls)} tool calls*")

    return ToolResult(
        text="\n".join(text_parts),
        data={
            "business_name": business_name,
            "location": location,
            "sources": [s.to_dict() for s in sources],
            "summary": findings.get("summary", "") if findings else "",
            "agent_tool_calls": len(tool_calls)
        }
    )


# =============================================================================
# Tool Registration
# =============================================================================

REVIEW_COLLECTOR_TOOL = ToolConfig(
    name="collect_reviews",
    description="""Collect business reviews from Yelp and Google using an autonomous agent.

    The agent searches for business pages, fetches review pages, and compiles
    ratings, review counts, and sample reviews.

    Use when you need to understand a business's online reputation.""",
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
            }
        },
        "required": ["business_name", "location"]
    },
    output_schema={
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "location": {"type": "string"},
            "sources": {"type": "array"},
            "summary": {"type": "string"}
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
