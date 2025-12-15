"""
Simple Search Workflow Template

A minimal workflow for testing the workflow engine.
Takes a user question and does one pass of search/retrieval.

Graph structure:
    [generate_query] -> [execute_search] -> [evaluate_results] -> [generate_answer] -> [answer_checkpoint]
"""

import logging
import json
from typing import Any, Dict, Optional, AsyncGenerator, Union

import anthropic

from schemas.workflow import (
    WorkflowGraph,
    StepNode,
    Edge,
    StepOutput,
    StepProgress,
    CheckpointConfig,
    CheckpointAction,
    WorkflowContext,
)

logger = logging.getLogger(__name__)

# LLM client
_client = None
MODEL = "claude-sonnet-4-20250514"


def get_llm_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def _parse_json(text: str) -> Optional[Any]:
    """Parse JSON from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        start_idx = 1
        end_idx = len(lines)
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[start_idx:end_idx]).strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse error: {e}")
        return None


# =============================================================================
# Step Implementations
# =============================================================================

async def generate_query(context: WorkflowContext) -> StepOutput:
    """
    Step 1: Generate a search query from the user's question.
    """
    user_question = context.initial_input.get("query", "")

    if not user_question:
        return StepOutput(success=False, error="No query provided")

    try:
        client = get_llm_client()

        response = client.messages.create(
            model=MODEL,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": f"""Generate a concise, effective web search query for this question:

Question: "{user_question}"

Return ONLY a JSON object:
{{"query": "your search query here", "intent": "brief description of what we're looking for"}}

JSON:"""
            }]
        )

        data = _parse_json(response.content[0].text)
        if not data:
            data = {"query": user_question, "intent": "Direct search"}

        return StepOutput(
            success=True,
            data={
                "original_question": user_question,
                "search_query": data.get("query", user_question),
                "intent": data.get("intent", "")
            },
            display_title="Search Query Generated",
            display_content=f"**Query:** {data.get('query', user_question)}\n\n**Intent:** {data.get('intent', '')}",
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error generating query")
        return StepOutput(success=False, error=str(e))


async def execute_search(context: WorkflowContext) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Step 2: Execute the search and get results.
    """
    from services.search_service import SearchService

    query_data = context.get_step_output("generate_query")
    if not query_data:
        yield StepOutput(success=False, error="No query data")
        return

    search_query = query_data.get("search_query", "")

    yield StepProgress(message=f"Searching: {search_query[:50]}...", progress=0.2)

    try:
        search_service = SearchService()
        if not search_service.initialized:
            search_service.initialize()

        result = await search_service.search(search_term=search_query, num_results=10)

        results = []
        for item in result.get("search_results", []):
            results.append({
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet
            })

        yield StepProgress(message=f"Found {len(results)} results", progress=0.5)

        display = f"## Search Results ({len(results)})\n\n"
        for i, r in enumerate(results[:5], 1):
            display += f"{i}. **{r['title']}**\n   {r['snippet'][:150]}...\n\n"

        yield StepOutput(
            success=True,
            data={
                **query_data,
                "search_results": results,
                "results_count": len(results)
            },
            display_title="Search Complete",
            display_content=display,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Search error")
        yield StepOutput(success=False, error=str(e))


async def evaluate_and_retrieve(context: WorkflowContext) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Step 3: Evaluate search results and retrieve promising ones.
    """
    from services.web_retrieval_service import WebRetrievalService

    search_data = context.get_step_output("execute_search")
    if not search_data:
        yield StepOutput(success=False, error="No search data")
        return

    results = search_data.get("search_results", [])
    original_question = search_data.get("original_question", "")

    if not results:
        yield StepOutput(
            success=True,
            data={**search_data, "retrieved_content": [], "has_content": False},
            display_title="No Results",
            display_content="No search results to evaluate."
        )
        return

    yield StepProgress(message="Evaluating which results to retrieve...", progress=0.2)

    try:
        client = get_llm_client()

        # Ask LLM which results look promising
        results_text = "\n".join(
            f"{i+1}. {r['title']}\n   {r['snippet']}"
            for i, r in enumerate(results[:8])
        )

        response = client.messages.create(
            model=MODEL,
            max_tokens=128,
            messages=[{
                "role": "user",
                "content": f"""Which search results are most likely to answer: "{original_question}"?

Results:
{results_text}

Return a JSON array of result numbers (1-indexed) to fetch, max 3.
Example: [1, 3]
JSON array:"""
            }]
        )

        selected = _parse_json(response.content[0].text)
        if not selected or not isinstance(selected, list):
            selected = [1, 2]  # Default to first two

        urls_to_fetch = []
        for idx in selected[:3]:
            try:
                if isinstance(idx, int) and 1 <= idx <= len(results):
                    urls_to_fetch.append(results[idx - 1]["url"])
            except (TypeError, ValueError):
                continue

        if not urls_to_fetch:
            urls_to_fetch = [results[0]["url"]] if results else []

        yield StepProgress(message=f"Fetching {len(urls_to_fetch)} pages...", progress=0.5)

        # Fetch pages
        web_service = WebRetrievalService()
        retrieved = []

        for url in urls_to_fetch:
            try:
                result = await web_service.retrieve_webpage(url=url, extract_text_only=True)
                webpage = result["webpage"]
                retrieved.append({
                    "url": url,
                    "title": webpage.title,
                    "content": webpage.content[:4000]
                })
            except Exception as e:
                logger.warning(f"Failed to fetch {url}: {e}")

        yield StepProgress(message=f"Retrieved {len(retrieved)} pages", progress=0.8)

        display = f"## Retrieved Content\n\n"
        for r in retrieved:
            display += f"- **{r['title']}**\n  {r['url']}\n\n"

        yield StepOutput(
            success=True,
            data={
                **search_data,
                "retrieved_content": retrieved,
                "has_content": len(retrieved) > 0
            },
            display_title="Content Retrieved",
            display_content=display,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Retrieval error")
        yield StepOutput(success=False, error=str(e))


async def generate_answer(context: WorkflowContext) -> StepOutput:
    """
    Step 4: Generate an answer from retrieved content.
    """
    retrieval_data = context.get_step_output("evaluate_results")
    if not retrieval_data:
        return StepOutput(success=False, error="No retrieval data")

    original_question = retrieval_data.get("original_question", "")
    retrieved = retrieval_data.get("retrieved_content", [])

    if not retrieved:
        return StepOutput(
            success=True,
            data={
                "question": original_question,
                "answer": "No relevant content was found to answer this question.",
                "sources": [],
                "confidence": "low"
            },
            display_title="No Answer Available",
            display_content="Could not find relevant information to answer the question.",
            content_type="markdown"
        )

    try:
        client = get_llm_client()

        # Build context from retrieved content
        content_text = ""
        for page in retrieved:
            content_text += f"=== {page['title']} ({page['url']}) ===\n{page['content']}\n\n"

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Answer this question based on the provided content:

Question: "{original_question}"

Content:
{content_text}

Provide a clear, concise answer. If the content doesn't fully answer the question, note what's missing.
Include relevant facts and cite sources where applicable."""
            }]
        )

        answer = response.content[0].text

        return StepOutput(
            success=True,
            data={
                "question": original_question,
                "answer": answer,
                "sources": [p["url"] for p in retrieved],
                "confidence": "medium" if len(retrieved) >= 2 else "low"
            },
            display_title="Answer",
            display_content=answer,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Answer generation error")
        return StepOutput(success=False, error=str(e))


# =============================================================================
# Workflow Graph Definition
# =============================================================================

simple_search_workflow = WorkflowGraph(
    id="simple_search",
    name="Simple Search",
    description="Quick single-pass search and answer workflow for testing",
    icon="magnifying-glass",
    category="search",

    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The question to answer"
            }
        },
        "required": ["query"]
    },

    output_schema={
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "answer": {"type": "string"},
            "sources": {"type": "array", "items": {"type": "string"}}
        }
    },

    entry_node="generate_query",

    nodes={
        "generate_query": StepNode(
            id="generate_query",
            name="Generate Query",
            description="Convert question to search query",
            node_type="execute",
            execute_fn=generate_query
        ),

        "execute_search": StepNode(
            id="execute_search",
            name="Execute Search",
            description="Run web search",
            node_type="execute",
            execute_fn=execute_search
        ),

        "evaluate_results": StepNode(
            id="evaluate_results",
            name="Evaluate & Retrieve",
            description="Select and fetch promising results",
            node_type="execute",
            execute_fn=evaluate_and_retrieve
        ),

        "generate_answer": StepNode(
            id="generate_answer",
            name="Generate Answer",
            description="Synthesize answer from content",
            node_type="execute",
            execute_fn=generate_answer
        ),

        "answer_checkpoint": StepNode(
            id="answer_checkpoint",
            name="Review Answer",
            description="Review the generated answer",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Answer",
                description="Review the answer. Accept to complete or reject to cancel.",
                allowed_actions=[CheckpointAction.APPROVE, CheckpointAction.REJECT],
                editable_fields=[]
            )
        ),
    },

    edges=[
        Edge(from_node="generate_query", to_node="execute_search"),
        Edge(from_node="execute_search", to_node="evaluate_results"),
        Edge(from_node="evaluate_results", to_node="generate_answer"),
        Edge(from_node="generate_answer", to_node="answer_checkpoint"),
        # answer_checkpoint has no outgoing edges = workflow complete
    ]
)
