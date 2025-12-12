"""
Deep Research Tool

A high-level research tool that orchestrates search-fetch-analyze loops
with built-in strategy. Instead of the LLM manually calling web_search
and fetch_webpage repeatedly, it calls this once with a research goal.

This is a STREAMING tool - it yields ToolProgress updates as it works,
allowing the frontend to show real-time progress.

The workflow is hardcoded but uses LLMs at decision points:
1. Break goal into checklist of information needs
2. Loop until satisfied:
   - Generate targeted search queries for unfilled items
   - Execute searches
   - Evaluate which URLs to fetch
   - Fetch and extract relevant information
   - Update checklist with findings
3. Synthesize into final output
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional, Generator
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
import anthropic

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from tools.executor import run_async

logger = logging.getLogger(__name__)

# Use a fast model for the inner LLM calls
RESEARCH_MODEL = "claude-sonnet-4-20250514"
MAX_RESEARCH_ITERATIONS = 5
MAX_URLS_PER_ITERATION = 3
MAX_SEARCH_RESULTS = 8


@dataclass
class ChecklistItem:
    """An item of information we need to find."""
    question: str
    status: str = "unfilled"  # unfilled, partial, complete
    findings: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "status": self.status,
            "findings": self.findings,
            "sources": self.sources
        }


@dataclass
class ResearchState:
    """Current state of the research process."""
    goal: str
    checklist: List[ChecklistItem] = field(default_factory=list)
    all_sources: List[str] = field(default_factory=list)
    search_queries_used: List[str] = field(default_factory=list)
    iteration: int = 0

    def checklist_summary(self) -> Dict[str, int]:
        """Get counts by status."""
        counts = {"unfilled": 0, "partial": 0, "complete": 0}
        for item in self.checklist:
            counts[item.status] = counts.get(item.status, 0) + 1
        return counts


class DeepResearchEngine:
    """Orchestrates the research workflow with streaming progress."""

    def __init__(self, cancellation_token=None):
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.cancellation_token = cancellation_token

    def _is_cancelled(self) -> bool:
        """Check if the operation has been cancelled."""
        return self.cancellation_token is not None and self.cancellation_token.is_cancelled

    def _parse_llm_json(self, text: str) -> Optional[Any]:
        """
        Parse JSON from LLM response, handling markdown code blocks.

        Args:
            text: Raw LLM response text

        Returns:
            Parsed JSON object or None if parsing fails
        """
        # Strip whitespace
        text = text.strip()

        # Handle markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            # Find the content between ``` markers
            start_idx = 1  # Skip the opening ```
            end_idx = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "```":
                    end_idx = i
                    break
            text = "\n".join(lines[start_idx:end_idx]).strip()
            # Remove json language marker if present
            if text.startswith("json"):
                text = text[4:].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return None

    def run_streaming(
        self, topic: str, goal: str, db: Session, user_id: int
    ) -> Generator[ToolProgress, None, ToolResult]:
        """Execute the full research workflow, yielding progress updates."""
        state = ResearchState(goal=goal)

        try:
            # Check for cancellation at start
            if self._is_cancelled():
                return ToolResult(text="Research cancelled before starting")

            # Step 1: Break goal into checklist
            yield ToolProgress(
                stage="creating_checklist",
                message="Analyzing research goal and creating checklist...",
                data={"topic": topic, "goal": goal}
            )

            self._create_checklist(state, topic)

            if not state.checklist:
                return ToolResult(text="Failed to create research checklist")

            # Check for cancellation after checklist creation
            if self._is_cancelled():
                return ToolResult(text="Research cancelled after checklist creation")

            yield ToolProgress(
                stage="checklist_created",
                message=f"Created checklist with {len(state.checklist)} questions",
                data={
                    "checklist": [item.to_dict() for item in state.checklist]
                }
            )

            # Step 2: Research loop
            while state.iteration < MAX_RESEARCH_ITERATIONS:
                # Check for cancellation at start of each iteration
                if self._is_cancelled():
                    logger.info("Research cancelled during iteration loop")
                    yield ToolProgress(
                        stage="cancelled",
                        message="Research cancelled by user",
                        data={"iterations_completed": state.iteration}
                    )
                    return ToolResult(
                        text=f"Research cancelled after {state.iteration} iterations",
                        data={
                            "partial": True,
                            "checklist": [item.to_dict() for item in state.checklist],
                            "sources": state.all_sources
                        }
                    )
                state.iteration += 1

                # Check if we're done
                unfilled = [c for c in state.checklist if c.status != "complete"]
                if not unfilled:
                    yield ToolProgress(
                        stage="research_complete",
                        message="All checklist items answered",
                        data={"iterations": state.iteration}
                    )
                    break

                summary = state.checklist_summary()
                yield ToolProgress(
                    stage="iteration_start",
                    message=f"Research iteration {state.iteration}/{MAX_RESEARCH_ITERATIONS}",
                    data={
                        "iteration": state.iteration,
                        "max_iterations": MAX_RESEARCH_ITERATIONS,
                        "remaining": len(unfilled),
                        "complete": summary["complete"],
                        "partial": summary["partial"]
                    },
                    progress=state.iteration / MAX_RESEARCH_ITERATIONS
                )

                # Generate queries
                yield ToolProgress(
                    stage="generating_queries",
                    message="Generating search queries...",
                    data={"targeting": [c.question for c in unfilled[:3]]}
                )

                queries = self._generate_queries(state, unfilled)
                if not queries:
                    yield ToolProgress(
                        stage="no_queries",
                        message="No new queries to try, ending research",
                        data={}
                    )
                    break

                yield ToolProgress(
                    stage="queries_generated",
                    message=f"Generated {len(queries)} search queries",
                    data={"queries": queries}
                )

                # Execute searches
                yield ToolProgress(
                    stage="searching",
                    message=f"Executing {len(queries)} searches...",
                    data={"queries": queries}
                )

                search_results = self._execute_searches(queries)

                yield ToolProgress(
                    stage="search_complete",
                    message=f"Found {len(search_results)} results",
                    data={"result_count": len(search_results)}
                )

                if not search_results:
                    continue

                # Evaluate URLs
                yield ToolProgress(
                    stage="evaluating_urls",
                    message="Evaluating which sources to read...",
                    data={"candidates": len(search_results)}
                )

                urls_to_fetch = self._evaluate_urls(state, search_results, unfilled)

                if not urls_to_fetch:
                    yield ToolProgress(
                        stage="no_urls",
                        message="No promising URLs found in this iteration",
                        data={}
                    )
                    continue

                yield ToolProgress(
                    stage="urls_selected",
                    message=f"Selected {len(urls_to_fetch)} pages to read",
                    data={"urls": urls_to_fetch}
                )

                # Fetch pages
                yield ToolProgress(
                    stage="fetching_pages",
                    message=f"Fetching {len(urls_to_fetch)} pages...",
                    data={"urls": urls_to_fetch}
                )

                page_contents = self._fetch_pages(urls_to_fetch)

                yield ToolProgress(
                    stage="pages_fetched",
                    message=f"Retrieved {len(page_contents)} pages",
                    data={
                        "fetched": len(page_contents),
                        "titles": [p["title"] for p in page_contents]
                    }
                )

                if page_contents:
                    # Extract info
                    yield ToolProgress(
                        stage="extracting_info",
                        message="Extracting relevant information...",
                        data={"pages": len(page_contents)}
                    )

                    self._extract_and_update(state, page_contents, unfilled)

                    # Report updated checklist status
                    summary = state.checklist_summary()
                    yield ToolProgress(
                        stage="extraction_complete",
                        message=f"Updated checklist: {summary['complete']} complete, {summary['partial']} partial",
                        data={
                            "checklist": [item.to_dict() for item in state.checklist],
                            "summary": summary
                        }
                    )

            # Step 3: Synthesize findings
            yield ToolProgress(
                stage="synthesizing",
                message="Synthesizing research findings...",
                data={
                    "total_sources": len(state.all_sources),
                    "iterations_used": state.iteration
                }
            )

            result = self._synthesize(state, topic)

            yield ToolProgress(
                stage="complete",
                message="Research complete",
                data={
                    "checklist": [item.to_dict() for item in state.checklist],
                    "sources": state.all_sources,
                    "iterations": state.iteration
                }
            )

            return result

        except Exception as e:
            logger.error(f"Research error: {e}", exc_info=True)
            yield ToolProgress(
                stage="error",
                message=f"Research error: {str(e)}",
                data={"error": str(e)}
            )
            return ToolResult(text=f"Research failed: {str(e)}")

    def _create_checklist(self, state: ResearchState, topic: str):
        """Use LLM to break the goal into specific information needs."""
        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=1024,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": f"""Break this research goal into 3-6 specific questions/information needs.

                Topic: {topic}
                Goal: {state.goal}

                Return ONLY a JSON array of strings, each a specific question to answer.
                Example: ["What is X?", "When did Y happen?", "Who are the key people in Z?"]

                JSON array:"""
            }]
        )

        text = response.content[0].text.strip()
        parsed = self._parse_llm_json(text)

        if parsed is not None and isinstance(parsed, list):
            state.checklist = [ChecklistItem(question=q) for q in parsed]
            logger.info(f"Created checklist with {len(state.checklist)} items")
        else:
            logger.error(f"Failed to parse checklist: {text}")
            # Fallback: single item
            state.checklist = [ChecklistItem(question=state.goal)]

    def _generate_queries(self, state: ResearchState, unfilled: List[ChecklistItem]) -> List[str]:
        """Generate search queries for unfilled checklist items."""
        unfilled_text = "\n".join(f"- {c.question}" for c in unfilled[:3])
        used_queries = "\n".join(f"- {q}" for q in state.search_queries_used[-10:]) or "None yet"

        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=512,
            temperature=0.5,
            messages=[{
                "role": "user",
                "content": f"""Generate 2-3 search queries to find information for these questions:

                {unfilled_text}

                Previously used queries (avoid repeating):
                {used_queries}

                Return ONLY a JSON array of search query strings. Be specific and varied.
                JSON array:"""
            }]
        )

        text = response.content[0].text.strip()
        parsed = self._parse_llm_json(text)

        if parsed is not None and isinstance(parsed, list):
            # Filter out already-used queries
            new_queries = [q for q in parsed if q not in state.search_queries_used]
            state.search_queries_used.extend(new_queries)
            return new_queries[:3]
        else:
            logger.error(f"Failed to parse queries: {text}")
            return []

    def _execute_searches(self, queries: List[str]) -> List[Dict[str, Any]]:
        """Execute search queries and collect results."""
        from services.search_service import SearchService, SearchQuotaExceededError, SearchAPIError

        all_results = []
        search_service = SearchService()
        if not search_service.initialized:
            search_service.initialize()

        quota_exceeded = False
        for query in queries:
            if quota_exceeded:
                # Skip remaining queries if quota exceeded
                break
            try:
                result = run_async(
                    search_service.search(search_term=query, num_results=MAX_SEARCH_RESULTS)
                )

                # Check if fallback was used (indicates quota issues)
                metadata = result.get("metadata")
                if metadata and metadata.get("fallback_reason") == "google_quota_exceeded":
                    logger.info(f"Search fell back to DuckDuckGo for query: {query}")

                for item in result.get("search_results", []):
                    all_results.append({
                        "title": item.title,
                        "url": item.url,
                        "snippet": item.snippet,
                        "query": query
                    })
            except SearchQuotaExceededError as e:
                logger.warning(f"Search quota exceeded for '{query}': {e}")
                quota_exceeded = True
            except SearchAPIError as e:
                logger.error(f"Search API error for '{query}': {e}")
            except Exception as e:
                logger.error(f"Search error for '{query}': {e}")

        # Dedupe by URL
        seen_urls = set()
        deduped = []
        for r in all_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                deduped.append(r)

        return deduped

    def _evaluate_urls(
        self,
        state: ResearchState,
        search_results: List[Dict[str, Any]],
        unfilled: List[ChecklistItem]
    ) -> List[str]:
        """Use LLM to pick which URLs are worth fetching."""
        if not search_results:
            return []

        # Format search results
        results_text = ""
        for i, r in enumerate(search_results[:15]):
            results_text += f"{i+1}. {r['title']}\n   URL: {r['url']}\n   {r['snippet']}\n\n"

        unfilled_text = "\n".join(f"- {c.question}" for c in unfilled[:3])
        already_fetched = "\n".join(f"- {u}" for u in state.all_sources[-10:]) or "None"

        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=256,
            temperature=0.2,
            messages=[{
                "role": "user",
                "content": f"""Which search results are most likely to contain useful information?

            Information needed:
            {unfilled_text}

            Already fetched (skip these):
            {already_fetched}

            Search results:
            {results_text}

            Return ONLY a JSON array of result numbers (1-indexed) to fetch. Pick up to {MAX_URLS_PER_ITERATION} most promising.
            Example: [1, 3, 5]
            JSON array:"""
            }]
        )

        text = response.content[0].text.strip()
        parsed = self._parse_llm_json(text)

        if parsed is not None and isinstance(parsed, list):
            urls = []
            for idx in parsed[:MAX_URLS_PER_ITERATION]:
                try:
                    if 1 <= idx <= len(search_results):
                        url = search_results[idx - 1]["url"]
                        if url not in state.all_sources:
                            urls.append(url)
                except (TypeError, ValueError):
                    continue
            return urls
        else:
            logger.error(f"Failed to parse URL indices: {text}")
            return []

    def _fetch_pages(self, urls: List[str]) -> List[Dict[str, str]]:
        """Fetch content from URLs."""
        from services.web_retrieval_service import WebRetrievalService

        pages = []
        service = WebRetrievalService()

        for url in urls:
            try:
                result = run_async(
                    service.retrieve_webpage(url=url, extract_text_only=True)
                )

                webpage = result["webpage"]
                content = webpage.content[:6000]  # Limit per page
                pages.append({
                    "url": url,
                    "title": webpage.title,
                    "content": content
                })
            except Exception as e:
                logger.error(f"Fetch error for {url}: {e}")

        return pages

    def _extract_and_update(
        self,
        state: ResearchState,
        pages: List[Dict[str, str]],
        unfilled: List[ChecklistItem]
    ):
        """Extract relevant info from pages and update checklist."""
        for page in pages:
            state.all_sources.append(page["url"])

        # Build context of what we're looking for
        questions_text = "\n".join(f"{i+1}. {c.question}" for i, c in enumerate(unfilled))

        # Build page contents
        pages_text = ""
        for p in pages:
            pages_text += f"=== {p['title']} ({p['url']}) ===\n{p['content']}\n\n"

        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=2048,
            temperature=0.2,
            messages=[{
                "role": "user",
                "content": f"""Extract information from these pages that answers our questions.

                Questions we need to answer:
                {questions_text}

                Page contents:
                {pages_text}

                For each question, extract relevant facts found. Return JSON:
                {{
                "extractions": [
                    {{"question_index": 1, "findings": ["fact 1", "fact 2"], "complete": true/false}},
                    ...
                ]
                }}

                Only include questions where you found relevant information.
                JSON:"""
            }]
        )

        text = response.content[0].text.strip()
        parsed = self._parse_llm_json(text)

        if parsed is not None and isinstance(parsed, dict):
            for ext in parsed.get("extractions", []):
                idx = ext.get("question_index", 0) - 1
                if 0 <= idx < len(unfilled):
                    item = unfilled[idx]
                    item.findings.extend(ext.get("findings", []))
                    item.sources.extend(p["url"] for p in pages)
                    if ext.get("complete", False):
                        item.status = "complete"
                    elif item.findings:
                        item.status = "partial"
        else:
            logger.error(f"Failed to parse extractions: {text}")

    def _synthesize(self, state: ResearchState, topic: str) -> ToolResult:
        """Synthesize all findings into a final output."""
        # Build summary of what we found
        findings_text = ""
        for item in state.checklist:
            status_icon = {"complete": "✓", "partial": "◐", "unfilled": "○"}.get(item.status, "?")
            findings_text += f"\n{status_icon} {item.question}\n"
            if item.findings:
                for f in item.findings:
                    findings_text += f"  - {f}\n"
            else:
                findings_text += "  (No information found)\n"

        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=3000,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": f"""Synthesize these research findings into a comprehensive summary.

                Topic: {topic}
                Goal: {state.goal}

                Findings by question:
                {findings_text}

                Write a well-organized summary that addresses the research goal. Include key facts and insights.
                Be thorough but concise. Note any gaps where information couldn't be found."""
            }]
        )

        synthesis = response.content[0].text

        # Add sources
        if state.all_sources:
            synthesis += "\n\n**Sources:**\n"
            for url in state.all_sources[:10]:
                synthesis += f"- {url}\n"

        # Build structured data for potential UI use
        return ToolResult(
            text=synthesis,
            data={
                "type": "research_result",
                "topic": topic,
                "goal": state.goal,
                "checklist": [item.to_dict() for item in state.checklist],
                "sources": state.all_sources,
                "iterations": state.iteration
            }
        )


def execute_deep_research_streaming(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """Execute deep research on a topic with streaming progress."""
    topic = params.get("topic", "")
    goal = params.get("goal", "")

    if not topic:
        return ToolResult(text="Error: No research topic provided")
    if not goal:
        goal = f"Comprehensive research on {topic}"

    # Get cancellation token from context (passed by executor)
    cancellation_token = context.get("cancellation_token")

    engine = DeepResearchEngine(cancellation_token=cancellation_token)
    # Return the generator directly - services will iterate through it
    return engine.run_streaming(topic, goal, db, user_id)


DEEP_RESEARCH_TOOL = ToolConfig(
    name="deep_research",
    description="""Conduct comprehensive research on a topic. This tool automatically:
    1. Breaks your goal into specific questions
    2. Generates varied search queries
    3. Evaluates and fetches promising sources
    4. Extracts relevant information
    5. Synthesizes findings into a summary

    Use this instead of manual web_search + fetch_webpage loops when you need thorough research.""",
    input_schema={
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic to research"
            },
            "goal": {
                "type": "string",
                "description": "Specific research goal or questions to answer (optional - defaults to comprehensive research)"
            }
        },
        "required": ["topic"]
    },
    executor=execute_deep_research_streaming,
    category="research",
    streaming=True  # This tool streams progress updates
)


def register_research_tools():
    """Register research tools."""
    register_tool(DEEP_RESEARCH_TOOL)
    logger.info("Registered deep_research tool")
