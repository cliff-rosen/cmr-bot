"""
Entity Verification Workflow

Verifies a business entity exists on a platform (Yelp or Google).

Two modes:
1. SerpAPI mode (preferred): Uses SerpAPI for reliable, structured data
2. Web scraping mode (fallback): Orchestrated search/fetch/verify loop
"""

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Literal, Generator
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Configuration
LLM_MODEL = "claude-sonnet-4-20250514"
MAX_ITERATIONS = 5
USE_SERPAPI = True  # Try SerpAPI first


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str


@dataclass
class EntityCandidate:
    """A potential entity match suggested by the LLM."""
    name: str
    url: str
    reason: str
    confidence: Literal["high", "medium", "low"]


@dataclass
class VerificationStep:
    """A step in the verification process."""
    iteration: int
    action: Literal["search", "fetch", "llm_guess", "llm_verify"]
    input: str
    output: str
    duration_ms: int


@dataclass
class VerificationResult:
    """Result of entity verification."""
    status: Literal["confirmed", "not_found", "ambiguous", "gave_up", "error"]
    entity: Optional[EntityCandidate]
    page_content: Optional[str]  # The verified page content for downstream use
    steps: List[VerificationStep]
    total_duration_ms: int
    message: str


# =============================================================================
# LLM Prompts (structured, focused)
# =============================================================================

GUESS_PROMPT = """You are identifying a business from search results.

    TARGET BUSINESS: "{business_name}" in "{location}"
    PLATFORM: {source}

    Here are the search results:
    {search_results}

    TASK: Pick the BEST candidate URL for this business, or say none match.

    Respond in this exact JSON format:
    ```json
    {{
        "decision": "found" | "none_match",
        "candidate": {{
            "name": "exact name shown in results",
            "url": "the URL to verify",
            "reason": "why this is likely the right business",
            "confidence": "high" | "medium" | "low"
        }},
        "alternative_search": "if none match, suggest a better search query"
    }}
    ```

    Rules:
    - For Yelp, look for URLs like yelp.com/biz/...
    - Match location carefully - same city/state
    - If multiple good matches, pick the one with strongest signals
    - If none look right, say "none_match" and suggest a better search"""

VERIFY_PROMPT = """You are verifying this is the correct business.

    TARGET BUSINESS: "{business_name}" in "{location}"
    EXPECTED URL: {url}

    Here is the page content:
    ---
    {page_content}
    ---

    TASK: Determine if this page is for the exact target business.

    Respond in this exact JSON format:
    ```json
    {{
        "decision": "confirmed" | "not_it" | "give_up",
        "entity": {{
            "name": "exact business name from page",
            "url": "{url}",
            "reason": "why you're confident (address match, name match, etc)",
            "confidence": "high" | "medium" | "low"
        }},
        "next_search": "if not_it, suggest what to search next",
        "give_up_reason": "if give_up, explain why"
    }}
    ```

    Rules:
    - "confirmed" = definitely the right business (name AND location match)
    - "not_it" = wrong business, but we could try another search
    - "give_up" = can't find this business on this platform
    - Be strict: partial name matches or wrong locations are "not_it" """


# =============================================================================
# Core Functions
# =============================================================================

def _do_search(query: str, db, user_id: int, context: Dict) -> List[SearchResult]:
    """Execute a search and return results."""
    from services.search_service import SearchService
    import asyncio

    search_service = SearchService()
    if not search_service.initialized:
        search_service.initialize()

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            search_service.search(search_term=query, num_results=10)
        )
    finally:
        loop.close()

    results = []
    for r in result.get("search_results", []):
        results.append(SearchResult(
            title=getattr(r, 'title', ''),
            url=getattr(r, 'url', ''),
            snippet=getattr(r, 'snippet', '') or ''
        ))

    return results


def _run_async(coro):
    """Run async code safely, handling Windows subprocess requirements."""
    import asyncio
    import sys

    # On Windows, we need ProactorEventLoop for subprocess support (used by Playwright)
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Use asyncio.run() which properly manages the event loop
    return asyncio.run(coro)


def _do_fetch(url: str, needs_js: bool = False) -> tuple[str, bool]:
    """Fetch a page and return (content, was_blocked)."""
    try:
        if needs_js:
            from services.js_web_retrieval_service import fetch_with_js

            result = _run_async(
                fetch_with_js(url=url, timeout=45000, wait_after_load=3000)
            )

            webpage = result["webpage"]
            content = webpage.content
            was_blocked = webpage.metadata.get('blocked', False)

            if was_blocked:
                return f"[BLOCKED: {webpage.metadata.get('block_reason', 'Unknown')}]", True

            # Truncate for LLM
            if len(content) > 12000:
                content = content[:12000] + "\n\n[Content truncated]"

            return content, False
        else:
            from services.web_retrieval_service import WebRetrievalService

            web_service = WebRetrievalService()
            result = _run_async(
                web_service.retrieve_webpage(url=url, extract_text_only=True)
            )

            content = result["webpage"].content
            if len(content) > 12000:
                content = content[:12000] + "\n\n[Content truncated]"

            return content, False

    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        return f"[FETCH ERROR: {str(e)}]", True


def _call_llm(prompt: str) -> str:
    """Call the LLM and return its response."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


def _parse_json_response(text: str) -> Optional[Dict]:
    """Extract JSON from LLM response."""
    import re

    # Try code block first
    json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try raw JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    return None


def _needs_js_rendering(url: str) -> bool:
    """Check if URL needs JavaScript rendering."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    js_domains = [
        'yelp.com', 'www.yelp.com',
        'google.com', 'www.google.com', 'maps.google.com',
        'healthgrades.com', 'www.healthgrades.com',
    ]

    return any(domain.endswith(d) or domain == d for d in js_domains)


def _get_site_operator(source: str) -> str:
    """Get the site: operator for a source."""
    if source == "yelp":
        return "site:yelp.com/biz"
    elif source == "google":
        return "site:google.com/maps OR site:maps.google.com"
    elif source == "reddit":
        return "site:reddit.com"
    else:
        return ""


# =============================================================================
# SerpAPI-based Verification (Preferred)
# =============================================================================

def _verify_with_serpapi(
    business_name: str,
    location: str,
    source: str
) -> Generator[Dict[str, Any], None, Optional[VerificationResult]]:
    """
    Verify entity using SerpAPI.

    Much simpler than web scraping - SerpAPI returns structured data.
    Returns None if SerpAPI is not available or fails (caller should fall back).
    """
    from services.serpapi_service import get_serpapi_service, SerpApiService

    start_time = time.time()
    steps: List[VerificationStep] = []

    service = get_serpapi_service()
    if not service.api_key:
        logger.info("SerpAPI key not configured, falling back to web scraping")
        return None

    yield {"stage": "serpapi_search", "message": f"Searching {source.upper()} via SerpAPI", "iteration": 1}

    step_start = time.time()

    # Search for business
    if source == "yelp":
        result = service.search_yelp(business_name, location)
    else:
        result = service.search_google_maps(business_name, location)

    step_duration = int((time.time() - step_start) * 1000)

    steps.append(VerificationStep(
        iteration=1,
        action="search",
        input=f"{business_name} in {location}",
        output=f"SerpAPI: {result.business.name if result.business else 'not found'}",
        duration_ms=step_duration
    ))

    if not result.success or not result.business:
        yield {"stage": "not_found", "message": f"Business not found on {source.upper()}", "iteration": 1}
        total_duration = int((time.time() - start_time) * 1000)
        return VerificationResult(
            status="not_found",
            entity=None,
            page_content=None,
            steps=steps,
            total_duration_ms=total_duration,
            message=result.error or f"Could not find {business_name} on {source.upper()}"
        )

    biz = result.business

    # Simple name matching - check if the found business matches our target
    # Use fuzzy matching: lowercase, remove punctuation
    import re
    def normalize(s: str) -> str:
        return re.sub(r'[^\w\s]', '', s.lower()).strip()

    target_normalized = normalize(business_name)
    found_normalized = normalize(biz.name)

    # Check for reasonable match
    name_matches = (
        target_normalized in found_normalized or
        found_normalized in target_normalized or
        # Check if significant words overlap
        len(set(target_normalized.split()) & set(found_normalized.split())) >= min(2, len(target_normalized.split()))
    )

    if name_matches:
        confidence = "high" if target_normalized == found_normalized else "medium"
        yield {"stage": "confirmed", "message": f"Found: {biz.name}", "iteration": 1}

        total_duration = int((time.time() - start_time) * 1000)
        return VerificationResult(
            status="confirmed",
            entity=EntityCandidate(
                name=biz.name,
                url=biz.url or f"https://www.yelp.com/biz/{biz.place_id}" if source == "yelp" else "",
                reason=f"SerpAPI match: {biz.rating}★ ({biz.review_count} reviews) at {biz.address or 'address N/A'}",
                confidence=confidence
            ),
            page_content=None,  # SerpAPI doesn't give us page content, but we don't need it
            steps=steps,
            total_duration_ms=total_duration,
            message=f"Verified {biz.name} on {source.upper()} via SerpAPI"
        )
    else:
        # Name doesn't match well - could be wrong business
        yield {"stage": "ambiguous", "message": f"Found '{biz.name}' but expected '{business_name}'", "iteration": 1}

        total_duration = int((time.time() - start_time) * 1000)
        return VerificationResult(
            status="ambiguous",
            entity=EntityCandidate(
                name=biz.name,
                url=biz.url or "",
                reason=f"Name mismatch: searched for '{business_name}', found '{biz.name}'",
                confidence="low"
            ),
            page_content=None,
            steps=steps,
            total_duration_ms=total_duration,
            message=f"Found '{biz.name}' but may not match '{business_name}'"
        )


# =============================================================================
# Web Scraping Verification (Fallback)
# =============================================================================

def verify_entity(
    business_name: str,
    location: str,
    source: str,
    db,
    user_id: int,
    context: Dict[str, Any],
    on_progress: Optional[callable] = None
) -> Generator[Dict[str, Any], None, VerificationResult]:
    """
    Entity verification workflow.

    Tries SerpAPI first (fast, reliable), falls back to web scraping if needed.
    """
    # Try SerpAPI first
    if USE_SERPAPI and source in ("yelp", "google"):
        serpapi_gen = _verify_with_serpapi(business_name, location, source)
        try:
            while True:
                progress = next(serpapi_gen)
                yield progress
        except StopIteration as e:
            result = e.value
            if result is not None:
                return result
            # result is None means SerpAPI not available, fall back to web scraping
            logger.info("SerpAPI unavailable, falling back to web scraping")

    # Fall back to web scraping workflow
    yield {"stage": "fallback", "message": "Using web scraping fallback", "iteration": 0}

    start_time = time.time()
    steps: List[VerificationStep] = []
    iteration = 0

    site_op = _get_site_operator(source)
    search_query = f'{site_op} "{business_name}" {location}'

    verified_content = None  # Store verified page content

    while iteration < MAX_ITERATIONS:
        iteration += 1
        logger.info(f"Entity verification iteration {iteration}/{MAX_ITERATIONS}")

        # === STEP 1: Search ===
        yield {"stage": "searching", "message": f"Searching {source.upper()} [{iteration}]", "iteration": iteration}

        step_start = time.time()
        search_results = _do_search(search_query, db, user_id, context)
        step_duration = int((time.time() - step_start) * 1000)

        steps.append(VerificationStep(
            iteration=iteration,
            action="search",
            input=search_query,
            output=f"{len(search_results)} results",
            duration_ms=step_duration
        ))

        if not search_results:
            yield {"stage": "no_results", "message": f"No {source.upper()} results found, refining search", "iteration": iteration}
            # LLM might suggest different search
            search_query = f'{site_op} {business_name} {location.split(",")[0]}'
            continue

        # Format results for LLM
        results_text = "\n".join([
            f"{i+1}. {r.title}\n   URL: {r.url}\n   {r.snippet[:200]}"
            for i, r in enumerate(search_results[:8])
        ])

        # === STEP 2: Ask LLM for best guess ===
        yield {"stage": "analyzing", "message": f"Found {len(search_results)} results, selecting best match", "iteration": iteration}

        guess_prompt = GUESS_PROMPT.format(
            business_name=business_name,
            location=location,
            source=source.upper(),
            search_results=results_text
        )

        step_start = time.time()
        guess_response = _call_llm(guess_prompt)
        step_duration = int((time.time() - step_start) * 1000)

        steps.append(VerificationStep(
            iteration=iteration,
            action="llm_guess",
            input=f"{len(search_results)} results",
            output=guess_response[:200],
            duration_ms=step_duration
        ))

        guess_data = _parse_json_response(guess_response)
        if not guess_data:
            logger.warning(f"Could not parse guess response: {guess_response[:200]}")
            yield {"stage": "parse_error", "message": "Could not parse LLM response", "iteration": iteration}
            # Try a different search
            search_query = f'"{business_name}" {location} {source}'
            continue

        if guess_data.get("decision") == "none_match":
            alt_search = guess_data.get("alternative_search", "")
            if alt_search:
                yield {"stage": "no_match", "message": f"No exact match, trying different search", "iteration": iteration}
                search_query = f'{site_op} {alt_search}'
                continue
            else:
                # Give up
                total_duration = int((time.time() - start_time) * 1000)
                return VerificationResult(
                    status="not_found",
                    entity=None,
                    page_content=None,
                    steps=steps,
                    total_duration_ms=total_duration,
                    message=f"Could not find {business_name} on {source.upper()}"
                )

        # We have a candidate
        candidate_data = guess_data.get("candidate", {})
        candidate = EntityCandidate(
            name=candidate_data.get("name", business_name),
            url=candidate_data.get("url", ""),
            reason=candidate_data.get("reason", ""),
            confidence=candidate_data.get("confidence", "low")
        )

        if not candidate.url:
            yield {"stage": "no_url", "message": "No valid URL found, refining search", "iteration": iteration}
            search_query = f'{site_op} "{business_name}" "{location}"'
            continue

        # === STEP 3: Fetch the page (with retry on block) ===
        # Build list of URLs to try: primary candidate + alternatives from search results
        urls_to_try = [candidate.url]
        for r in search_results[1:5]:
            if source in r.url.lower() and r.url not in urls_to_try:
                urls_to_try.append(r.url)

        page_content = None
        fetch_succeeded = False

        for try_idx, try_url in enumerate(urls_to_try):
            yield {"stage": "fetching", "message": f"Loading {source.upper()} page" + (f" (attempt {try_idx + 1})" if try_idx > 0 else ""), "iteration": iteration}

            step_start = time.time()
            needs_js = _needs_js_rendering(try_url)
            content, was_blocked = _do_fetch(try_url, needs_js)
            step_duration = int((time.time() - step_start) * 1000)

            steps.append(VerificationStep(
                iteration=iteration,
                action="fetch",
                input=try_url,
                output=f"{len(content)} chars" + (" [BLOCKED]" if was_blocked else ""),
                duration_ms=step_duration
            ))

            if was_blocked:
                yield {"stage": "blocked", "message": f"{source.upper()} blocked access" + (", trying alternative" if try_idx < len(urls_to_try) - 1 else ""), "iteration": iteration}
                continue  # Try next URL in urls_to_try

            # Success - we got content
            page_content = content
            candidate.url = try_url  # Update candidate to the URL that worked
            fetch_succeeded = True
            break

        if not fetch_succeeded:
            yield {"stage": "all_blocked", "message": f"All {source.upper()} URLs blocked, trying new search", "iteration": iteration}
            search_query = f'{site_op} {business_name} {location.split(",")[0]} reviews'
            continue  # Go to next iteration with modified search

        # === STEP 4: Ask LLM to verify ===
        yield {"stage": "verifying", "message": "Checking if this is the right business", "iteration": iteration}

        verify_prompt = VERIFY_PROMPT.format(
            business_name=business_name,
            location=location,
            url=candidate.url,
            page_content=page_content
        )

        step_start = time.time()
        verify_response = _call_llm(verify_prompt)
        step_duration = int((time.time() - step_start) * 1000)

        steps.append(VerificationStep(
            iteration=iteration,
            action="llm_verify",
            input=candidate.url,
            output=verify_response[:200],
            duration_ms=step_duration
        ))

        verify_data = _parse_json_response(verify_response)
        if not verify_data:
            logger.warning(f"Could not parse verify response: {verify_response[:200]}")
            continue

        decision = verify_data.get("decision", "not_it")

        if decision == "confirmed":
            # SUCCESS!
            entity_data = verify_data.get("entity", {})
            confirmed_entity = EntityCandidate(
                name=entity_data.get("name", candidate.name),
                url=entity_data.get("url", candidate.url),
                reason=entity_data.get("reason", ""),
                confidence=entity_data.get("confidence", "medium")
            )

            total_duration = int((time.time() - start_time) * 1000)
            yield {"stage": "confirmed", "message": f"Found: {confirmed_entity.name}", "iteration": iteration}

            return VerificationResult(
                status="confirmed",
                entity=confirmed_entity,
                page_content=page_content,  # Return for artifact collection
                steps=steps,
                total_duration_ms=total_duration,
                message=f"Verified {confirmed_entity.name} on {source.upper()}"
            )

        elif decision == "give_up":
            reason = verify_data.get("give_up_reason", "Could not verify")
            total_duration = int((time.time() - start_time) * 1000)
            yield {"stage": "gave_up", "message": f"Could not find business on {source.upper()}", "iteration": iteration}

            return VerificationResult(
                status="gave_up",
                entity=None,
                page_content=None,
                steps=steps,
                total_duration_ms=total_duration,
                message=reason
            )

        else:  # not_it
            next_search = verify_data.get("next_search", "")
            if next_search:
                yield {"stage": "not_it", "message": "Wrong business, searching again", "iteration": iteration}
                search_query = f'{site_op} {next_search}'
            else:
                # Modify current search
                search_query = f'{site_op} "{business_name}" exact {location}'

    # Max iterations reached
    total_duration = int((time.time() - start_time) * 1000)
    return VerificationResult(
        status="gave_up",
        entity=None,
        page_content=None,
        steps=steps,
        total_duration_ms=total_duration,
        message=f"Could not verify entity after {MAX_ITERATIONS} attempts"
    )


# =============================================================================
# Synchronous wrapper
# =============================================================================

def verify_entity_sync(
    business_name: str,
    location: str,
    source: str,
    db,
    user_id: int,
    context: Dict[str, Any]
) -> tuple[VerificationResult, List[Dict[str, Any]]]:
    """
    Synchronous wrapper that collects all progress and returns final result.
    Returns (result, progress_events).
    """
    progress_events = []
    result = None

    gen = verify_entity(business_name, location, source, db, user_id, context)

    try:
        while True:
            progress = next(gen)
            progress_events.append(progress)
    except StopIteration as e:
        result = e.value

    return result, progress_events


# =============================================================================
# Tool Registration
# =============================================================================

def _result_to_dict(result: VerificationResult) -> Dict[str, Any]:
    """Convert VerificationResult to serializable dict."""
    return {
        "status": result.status,
        "entity": {
            "name": result.entity.name,
            "url": result.entity.url,
            "reason": result.entity.reason,
            "confidence": result.entity.confidence
        } if result.entity else None,
        "steps": [
            {
                "iteration": s.iteration,
                "action": s.action,
                "input": s.input,
                "output": s.output,
                "duration_ms": s.duration_ms
            }
            for s in result.steps
        ],
        "total_duration_ms": result.total_duration_ms,
        "message": result.message
    }


def execute_entity_verification(
    params: Dict[str, Any],
    db,
    user_id: int,
    context: Dict[str, Any]
) -> Generator:
    """
    Streaming executor for entity verification tool.
    """
    from tools.registry import ToolResult, ToolProgress

    business_name = params.get("business_name", "")
    location = params.get("location", "")
    source = params.get("source", "").lower()

    # Validate inputs
    if not business_name:
        return ToolResult(text="Error: business_name is required")
    if not location:
        return ToolResult(text="Error: location is required")
    if source not in ("yelp", "google"):
        return ToolResult(text="Error: source must be 'yelp' or 'google'")

    yield ToolProgress(
        stage="starting",
        message=f"Verifying {business_name} on {source.upper()}",
        data={"business_name": business_name, "location": location, "source": source}
    )

    # Run verification workflow
    verification_gen = verify_entity(
        business_name=business_name,
        location=location,
        source=source,
        db=db,
        user_id=user_id,
        context=context
    )

    # Forward progress
    result = None
    try:
        while True:
            progress = next(verification_gen)
            yield ToolProgress(
                stage=progress.get("stage", "verifying"),
                message=progress.get("message", "Verifying..."),
                data={"iteration": progress.get("iteration", 1)}
            )
    except StopIteration as e:
        result = e.value

    # Build result
    result_dict = _result_to_dict(result)

    if result.status == "confirmed":
        text_output = f"**Entity Verified**\n\n"
        text_output += f"- **Name:** {result.entity.name}\n"
        text_output += f"- **URL:** {result.entity.url}\n"
        text_output += f"- **Confidence:** {result.entity.confidence}\n"
        text_output += f"- **Reason:** {result.entity.reason}\n"
        success_msg = f"Verified: {result.entity.name}"
    else:
        text_output = f"**Entity Not Found**\n\n"
        text_output += f"- **Status:** {result.status}\n"
        text_output += f"- **Message:** {result.message}\n"
        text_output += f"- **Attempts:** {len(result.steps)} steps across {result.steps[-1].iteration if result.steps else 0} iterations\n"
        success_msg = result.message

    yield ToolProgress(
        stage="complete",
        message=success_msg,
        data={"status": result.status}
    )

    return ToolResult(
        text=text_output,
        data=result_dict,
        workspace_payload={
            "type": "entity_verification",
            "data": result_dict
        }
    )


def register_entity_verification_tool():
    """Register the entity verification tool."""
    from tools.registry import ToolConfig, register_tool

    tool = ToolConfig(
        name="verify_entity",
        description="""Verify a business entity exists on a platform (Yelp or Google).

This tool uses an orchestrated workflow to:
1. Search for the business
2. Analyze results to find best match
3. Fetch the candidate page
4. Verify it's the correct business
5. Loop until confirmed or give up

Use this when you need to confirm a specific business exists on a platform
before collecting reviews or other data.""",
        input_schema={
            "type": "object",
            "properties": {
                "business_name": {
                    "type": "string",
                    "description": "Name of the business to verify"
                },
                "location": {
                    "type": "string",
                    "description": "City and state (e.g., 'Cambridge, MA')"
                },
                "source": {
                    "type": "string",
                    "enum": ["yelp", "google"],
                    "description": "Platform to verify on"
                }
            },
            "required": ["business_name", "location", "source"]
        },
        executor=execute_entity_verification,
        category="research",
        streaming=True
    )

    register_tool(tool)
    logger.info("Registered verify_entity tool")
