"""
Smart Search Tool

A lightweight research tool for quick factual questions.
Faster than deep_research but smarter than raw web_search.

Workflow:
1. Execute web search
2. Evaluate if snippets can answer the question
3. If yes → synthesize from snippets (fast path)
4. If no → fetch best URL, extract answer
5. Return answer with source
"""

import json
import logging
import os
from typing import Any, Dict, Generator, List, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
import anthropic

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from tools.executor import run_async

logger = logging.getLogger(__name__)

SMART_SEARCH_MODEL = "claude-sonnet-4-20250514"
MAX_SEARCH_RESULTS = 8


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str


def _execute_search(query: str) -> List[SearchResult]:
    """Execute web search and return results."""
    from services.search_service import SearchService, SearchQuotaExceededError, SearchAPIError

    search_service = SearchService()
    if not search_service.initialized:
        search_service.initialize()

    try:
        result = run_async(
            search_service.search(search_term=query, num_results=MAX_SEARCH_RESULTS)
        )

        return [
            SearchResult(
                title=item.title,
                url=item.url,
                snippet=item.snippet
            )
            for item in result.get("search_results", [])
        ]
    except (SearchQuotaExceededError, SearchAPIError) as e:
        logger.error(f"Search error: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected search error: {e}")
        return []


def _fetch_page(url: str) -> Optional[Dict[str, str]]:
    """Fetch a single webpage."""
    from services.web_retrieval_service import WebRetrievalService

    service = WebRetrievalService()
    try:
        result = run_async(
            service.retrieve_webpage(url=url, extract_text_only=True)
        )
        webpage = result["webpage"]
        return {
            "url": url,
            "title": webpage.title,
            "content": webpage.content[:8000]  # Limit content size
        }
    except Exception as e:
        logger.error(f"Fetch error for {url}: {e}")
        return None


def execute_smart_search(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Execute a smart search - quick research for factual questions.

    This is a streaming tool that yields progress updates.
    """
    question = params.get("question", "")
    mode = params.get("mode", "answer")  # "answer" or "summary"

    if not question:
        return ToolResult(text="Error: No question provided")

    cancellation_token = context.get("cancellation_token")
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    # Step 1: Search
    yield ToolProgress(
        stage="searching",
        message=f"Searching for: {question}",
        data={"question": question},
        progress=0.1
    )

    if cancellation_token and cancellation_token.is_cancelled:
        return ToolResult(text="Search cancelled")

    results = _execute_search(question)

    if not results:
        yield ToolProgress(
            stage="no_results",
            message="No search results found",
            data={},
            progress=1.0
        )
        return ToolResult(
            text="I couldn't find any search results for that question.",
            data={"success": False, "reason": "no_search_results"}
        )

    yield ToolProgress(
        stage="search_complete",
        message=f"Found {len(results)} results",
        data={
            "result_count": len(results),
            "titles": [r.title for r in results[:5]]
        },
        progress=0.3
    )

    # Step 2: Evaluate if snippets are sufficient
    yield ToolProgress(
        stage="evaluating",
        message="Evaluating search results...",
        data={},
        progress=0.4
    )

    if cancellation_token and cancellation_token.is_cancelled:
        return ToolResult(text="Search cancelled")

    # Format results for LLM evaluation
    results_text = ""
    for i, r in enumerate(results, 1):
        results_text += f"{i}. {r.title}\n   URL: {r.url}\n   {r.snippet}\n\n"

    eval_response = client.messages.create(
        model=SMART_SEARCH_MODEL,
        max_tokens=512,
        temperature=0.2,
        messages=[{
            "role": "user",
            "content": f"""Question: {question}

Search results:
{results_text}

Can you confidently answer this question using ONLY the information in these search snippets?

Respond with JSON:
{{
  "can_answer": true/false,
  "confidence": "high"/"medium"/"low",
  "answer": "your answer if can_answer is true, otherwise null",
  "best_url_index": <1-indexed number of best URL to fetch if can_answer is false, otherwise null>,
  "reasoning": "brief explanation"
}}

JSON response:"""
        }]
    )

    eval_text = eval_response.content[0].text.strip()

    # Parse evaluation
    try:
        # Handle markdown code blocks
        if eval_text.startswith("```"):
            lines = eval_text.split("\n")
            start_idx = 1
            end_idx = len(lines)
            for i, line in enumerate(lines[1:], 1):
                if line.strip() == "```":
                    end_idx = i
                    break
            eval_text = "\n".join(lines[start_idx:end_idx]).strip()
            if eval_text.startswith("json"):
                eval_text = eval_text[4:].strip()

        evaluation = json.loads(eval_text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse evaluation: {eval_text}")
        # Default to needing a fetch
        evaluation = {
            "can_answer": False,
            "best_url_index": 1,
            "reasoning": "Could not parse evaluation"
        }

    # Step 3: Either answer from snippets or fetch a page
    if evaluation.get("can_answer") and evaluation.get("answer"):
        # Fast path - answer from snippets
        yield ToolProgress(
            stage="answering",
            message="Answering from search results...",
            data={"source": "snippets", "confidence": evaluation.get("confidence", "medium")},
            progress=0.8
        )

        answer = evaluation["answer"]
        source_urls = [r.url for r in results[:3]]

        yield ToolProgress(
            stage="complete",
            message="Answer found",
            data={"source": "snippets"},
            progress=1.0
        )

        # Format final answer
        if mode == "summary":
            final_text = f"**Summary:** {answer}\n\n**Sources:**\n" + "\n".join(f"- {url}" for url in source_urls[:3])
        else:
            final_text = f"{answer}\n\n**Source:** {source_urls[0]}"

        return ToolResult(
            text=final_text,
            data={
                "success": True,
                "answer": answer,
                "source": "snippets",
                "confidence": evaluation.get("confidence", "medium"),
                "sources": source_urls[:3]
            }
        )

    else:
        # Need to fetch a page
        best_idx = evaluation.get("best_url_index", 1)
        if not isinstance(best_idx, int) or best_idx < 1 or best_idx > len(results):
            best_idx = 1

        best_result = results[best_idx - 1]

        yield ToolProgress(
            stage="fetching",
            message=f"Reading: {best_result.title}",
            data={"url": best_result.url},
            progress=0.5
        )

        if cancellation_token and cancellation_token.is_cancelled:
            return ToolResult(text="Search cancelled")

        page = _fetch_page(best_result.url)

        if not page:
            # Fallback to snippet-based answer
            yield ToolProgress(
                stage="fetch_failed",
                message="Could not fetch page, using snippets",
                data={},
                progress=0.7
            )

            # Try to answer from snippets anyway
            fallback_response = client.messages.create(
                model=SMART_SEARCH_MODEL,
                max_tokens=1024,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": f"""Question: {question}

Based on these search snippets, provide the best answer you can:
{results_text}

{"Provide a brief summary." if mode == "summary" else "Provide a direct, concise answer."}"""
                }]
            )

            answer = fallback_response.content[0].text
            source_urls = [r.url for r in results[:3]]

            return ToolResult(
                text=f"{answer}\n\n**Sources:**\n" + "\n".join(f"- {url}" for url in source_urls[:3]),
                data={
                    "success": True,
                    "answer": answer,
                    "source": "snippets_fallback",
                    "confidence": "low",
                    "sources": source_urls[:3]
                }
            )

        # Extract answer from page
        yield ToolProgress(
            stage="extracting",
            message="Extracting answer...",
            data={},
            progress=0.8
        )

        extract_response = client.messages.create(
            model=SMART_SEARCH_MODEL,
            max_tokens=1024,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": f"""Question: {question}

Page content from {page['title']}:
{page['content']}

{"Provide a brief summary answering the question." if mode == "summary" else "Provide a direct, concise answer to the question."}

If the page doesn't contain the answer, say so clearly."""
            }]
        )

        answer = extract_response.content[0].text

        yield ToolProgress(
            stage="complete",
            message="Answer extracted",
            data={"source": "page_fetch"},
            progress=1.0
        )

        return ToolResult(
            text=f"{answer}\n\n**Source:** {page['url']}",
            data={
                "success": True,
                "answer": answer,
                "source": "page_fetch",
                "confidence": "high",
                "sources": [page['url']]
            }
        )


SMART_SEARCH_TOOL = ToolConfig(
    name="smart_search",
    description="""Quick research tool for factual questions and simple lookups.

Use this when you need to:
- Answer a specific factual question ("Who won the Yankees game last night?")
- Look up current information (prices, dates, scores, weather)
- Get a quick answer without comprehensive research

This is FASTER than deep_research but more intelligent than raw web_search.
It searches, evaluates if snippets are sufficient, and fetches a page only if needed.

For comprehensive, multi-faceted research, use deep_research instead.""",
    input_schema={
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to answer or topic to look up"
            },
            "mode": {
                "type": "string",
                "enum": ["answer", "summary"],
                "default": "answer",
                "description": "answer = direct concise answer, summary = brief summary of findings"
            }
        },
        "required": ["question"]
    },
    executor=execute_smart_search,
    category="research",
    streaming=True
)


def register_smart_search_tools():
    """Register the smart_search tool."""
    register_tool(SMART_SEARCH_TOOL)
    logger.info("Registered smart_search tool")
