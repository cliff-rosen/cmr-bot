"""
Research Workflow Template (Graph-Based)

A structured research workflow with:
1. Question formulation (LLM refines the user's question)
2. Answer checklist (LLM creates a checklist of what a complete answer needs)
3. Iterative retrieval (search and collect findings)
4. Final compilation (LLM synthesizes the answer)

Graph structure:
    [formulate_question] -> [question_checkpoint] -> [build_checklist] -> [checklist_checkpoint]
                                                                                    |
                                                                                    v
    [final_checkpoint] <- [compile_final] <- [retrieval_checkpoint] <- [run_retrieval] <-+
                                                                              |          |
                                                                              +----------+
                                                                         (loop if not complete)
"""

import logging
import json
import asyncio
from typing import Any, Dict, List, AsyncGenerator, Union, Optional
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

# LLM client - initialized lazily (async client)
_async_client = None

# Research constants
RESEARCH_MODEL = "claude-sonnet-4-20250514"
MAX_URLS_PER_ITERATION = 3
MAX_SEARCH_RESULTS = 8


def get_async_llm_client():
    """Get the async Anthropic client."""
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic()
    return _async_client


def _parse_llm_json(text: str) -> Optional[Any]:
    """Parse JSON from LLM response, handling markdown code blocks."""
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

async def formulate_question(context: WorkflowContext) -> StepOutput:
    """
    Step 1: Formulate a refined research question from the user's query.
    """
    user_query = context.initial_input.get("query", "")

    if not user_query:
        return StepOutput(
            success=False,
            error="No query provided"
        )

    try:
        client = get_async_llm_client()

        prompt = f"""You are helping formulate a clear, focused research question.

        User's original query: "{user_query}"

        Please provide:
        1. A refined, specific research question
        2. The scope and boundaries of this research
        3. Key terms and concepts to explore

        Respond in JSON format:
        {{
            "refined_question": "The refined research question",
            "scope": "Description of what is in and out of scope",
            "key_terms": ["term1", "term2", "term3"],
            "rationale": "Brief explanation of how you refined the question"
        }}"""

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        content = response.content[0].text

        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        return StepOutput(
            success=True,
            data={
                "original_query": user_query,
                "refined_question": data.get("refined_question", user_query),
                "scope": data.get("scope", ""),
                "key_terms": data.get("key_terms", []),
                "rationale": data.get("rationale", ""),
                "approved": False
            },
            display_title="Research Question",
            display_content=f"**Refined Question:**\n{data.get('refined_question', user_query)}\n\n**Scope:**\n{data.get('scope', '')}",
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error formulating question")
        return StepOutput(
            success=False,
            error=f"Failed to formulate question: {str(e)}"
        )


async def build_checklist(context: WorkflowContext) -> StepOutput:
    """
    Step 2: Build a checklist of what a complete answer should contain.
    """
    question_data = context.get_step_output("formulate_question")
    if not question_data:
        return StepOutput(success=False, error="No question data available")

    # Check for user edits
    user_edits = context.user_edits.get("question_checkpoint", {})
    refined_question = user_edits.get("refined_question", question_data.get("refined_question", ""))
    scope = user_edits.get("scope", question_data.get("scope", ""))

    try:
        client = get_async_llm_client()

        prompt = f"""You are helping create a comprehensive answer checklist for a research question.

        Research Question: "{refined_question}"
        Scope: "{scope}"

        Create a checklist of 4-8 items that a complete answer to this question should address.
        Each item should be:
        - Specific and verifiable
        - Important for answering the question comprehensively
        - Prioritized (high, medium, low)

        Respond in JSON format:
        {{
            "items": [
                {{
                    "id": "1",
                    "description": "What this checklist item covers",
                    "rationale": "Why this is important for the answer",
                    "priority": "high|medium|low"
                }}
            ]
        }}"""

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        content = response.content[0].text

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        # Add status to each item
        items = []
        for i, item in enumerate(data.get("items", [])):
            items.append({
                "id": str(i + 1),
                "description": item.get("description", ""),
                "rationale": item.get("rationale", ""),
                "priority": item.get("priority", "medium"),
                "status": "pending",
                "findings": []
            })

        display_content = "## Answer Checklist\n\n"
        for item in items:
            priority_emoji = {"high": "!", "medium": "-", "low": "."}.get(item["priority"], "-")
            display_content += f"- [{priority_emoji}] **{item['description']}**\n  _{item['rationale']}_\n\n"

        return StepOutput(
            success=True,
            data={
                "refined_question": refined_question,
                "scope": scope,
                "items": items
            },
            display_title="Answer Checklist",
            display_content=display_content,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error building checklist")
        return StepOutput(
            success=False,
            error=f"Failed to build checklist: {str(e)}"
        )


async def run_retrieval_iteration(
    context: WorkflowContext
) -> AsyncGenerator[Union[StepProgress, StepOutput], None]:
    """
    Step 3: Run one iteration of the retrieval loop.

    Uses actual search and web retrieval services:
    1. Generate search queries for pending checklist items
    2. Execute real web searches
    3. Evaluate and select promising URLs
    4. Fetch actual web pages
    5. Extract relevant information using LLM
    6. Update checklist with findings

    Yields progress updates during execution, then yields the final StepOutput.
    """
    from services.search_service import SearchService, SearchQuotaExceededError, SearchAPIError
    from services.web_retrieval_service import WebRetrievalService

    # Get checklist data from either build_checklist or previous retrieval
    checklist_data = context.get_step_output("run_retrieval") or context.get_step_output("build_checklist")
    if not checklist_data:
        yield StepOutput(success=False, error="No checklist data available")
        return

    # Get or initialize retrieval state
    iteration = context.get_variable("retrieval_iteration", 0) + 1
    context.set_variable("retrieval_iteration", iteration)

    # Track queries we've used to avoid repeats
    used_queries = context.get_variable("used_queries", [])
    all_sources = context.get_variable("all_sources", [])

    items = checklist_data.get("items", [])
    refined_question = checklist_data.get("refined_question", "")

    # Calculate progress
    total_items = len(items)
    completed_items = len([item for item in items if item.get("status") == "complete"])

    # Find pending items to research
    pending_items = [item for item in items if item.get("status") in ["pending", "partial"]]

    if not pending_items:
        # All items complete - set flag for edge condition
        context.set_variable("retrieval_complete", True)
        yield StepOutput(
            success=True,
            data={
                **checklist_data,
                "retrieval_complete": True,
                "total_iterations": iteration,
                "sources": all_sources
            },
            display_title="Retrieval Complete",
            display_content=f"All checklist items have been addressed after {iteration} iterations.\n\n**Sources consulted:** {len(all_sources)}",
            content_type="markdown"
        )
        return

    # Focus on top 3 pending items
    target_items = pending_items[:3]

    yield StepProgress(
        message=f"Iteration {iteration}: Generating search queries...",
        progress=completed_items / total_items if total_items > 0 else 0,
        details={"iteration": iteration, "pending_items": len(pending_items)}
    )

    try:
        client = get_async_llm_client()

        # Step 1: Generate search queries
        unfilled_text = "\n".join(f"- {item['description']}" for item in target_items)
        used_queries_text = "\n".join(f"- {q}" for q in used_queries[-10:]) or "None yet"

        query_response = await client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=512,
            temperature=0.5,
            messages=[{
                "role": "user",
                "content": f"""Generate 2-3 search queries to find information for these research needs:

                {unfilled_text}

                Research question context: {refined_question}

                Previously used queries (avoid repeating):
                {used_queries_text}

                Return ONLY a JSON array of search query strings. Be specific and varied.
                JSON array:"""
            }]
        )

        queries = _parse_llm_json(query_response.content[0].text)
        if not queries or not isinstance(queries, list):
            queries = [refined_question]  # Fallback

        # Filter out already-used queries
        new_queries = [q for q in queries if q not in used_queries][:3]
        used_queries.extend(new_queries)
        context.set_variable("used_queries", used_queries)

        if not new_queries:
            yield StepProgress(message="No new queries to try", progress=completed_items / total_items)
            context.set_variable("retrieval_complete", True)
            yield StepOutput(
                success=True,
                data={**checklist_data, "retrieval_complete": True, "sources": all_sources},
                display_title="Retrieval Complete",
                display_content="No more search queries to try."
            )
            return

        yield StepProgress(
            message=f"Executing {len(new_queries)} web searches...",
            progress=completed_items / total_items if total_items > 0 else 0.1,
            details={"queries": new_queries}
        )

        # Step 2: Execute real web searches
        search_service = SearchService()
        if not search_service.initialized:
            search_service.initialize()

        all_results = []
        for query in new_queries:
            yield StepProgress(
                message=f"Searching: \"{query[:50]}...\"",
                progress=completed_items / total_items if total_items > 0 else 0.15
            )
            try:
                result = await search_service.search(search_term=query, num_results=MAX_SEARCH_RESULTS)
                for item in result.get("search_results", []):
                    all_results.append({
                        "title": item.title,
                        "url": item.url,
                        "snippet": item.snippet,
                        "query": query
                    })
            except SearchQuotaExceededError as e:
                logger.warning(f"Search quota exceeded: {e}")
                break
            except SearchAPIError as e:
                logger.error(f"Search API error: {e}")
            except Exception as e:
                logger.error(f"Search error: {e}")

        # Dedupe by URL
        seen_urls = set(all_sources)  # Skip already-fetched URLs
        deduped_results = []
        for r in all_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                deduped_results.append(r)

        if not deduped_results:
            yield StepProgress(message="No new search results found", progress=0.5)
            # Mark iteration done but continue if more iterations allowed
            max_iterations = context.get_variable("max_iterations", 5)
            if iteration >= max_iterations:
                context.set_variable("retrieval_complete", True)
            yield StepOutput(
                success=True,
                data={**checklist_data, "current_iteration": iteration, "sources": all_sources},
                display_title=f"Iteration {iteration}",
                display_content="No new search results found this iteration."
            )
            return

        yield StepProgress(
            message=f"Found {len(deduped_results)} search results, evaluating...",
            progress=0.3
        )

        # Step 3: Evaluate which URLs to fetch
        results_text = ""
        for i, r in enumerate(deduped_results[:15]):
            results_text += f"{i+1}. {r['title']}\n   URL: {r['url']}\n   {r['snippet']}\n\n"

        eval_response = await client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=256,
            temperature=0.2,
            messages=[{
                "role": "user",
                "content": f"""Which search results are most likely to contain useful information?

                Information needed:
                {unfilled_text}

                Search results:
                {results_text}

                Return ONLY a JSON array of result numbers (1-indexed) to fetch. Pick up to {MAX_URLS_PER_ITERATION} most promising.
                Example: [1, 3, 5]
                JSON array:"""
            }]
        )

        selected_indices = _parse_llm_json(eval_response.content[0].text)
        urls_to_fetch = []
        if selected_indices and isinstance(selected_indices, list):
            for idx in selected_indices[:MAX_URLS_PER_ITERATION]:
                try:
                    if isinstance(idx, int) and 1 <= idx <= len(deduped_results):
                        urls_to_fetch.append(deduped_results[idx - 1]["url"])
                except (TypeError, ValueError):
                    continue

        if not urls_to_fetch:
            # Fallback: take first few results
            urls_to_fetch = [r["url"] for r in deduped_results[:MAX_URLS_PER_ITERATION]]

        yield StepProgress(
            message=f"Fetching {len(urls_to_fetch)} web pages...",
            progress=0.4,
            details={"urls": urls_to_fetch}
        )

        # Step 4: Fetch actual web pages
        web_service = WebRetrievalService()
        pages = []
        for url in urls_to_fetch:
            yield StepProgress(
                message=f"Fetching: {url[:60]}...",
                progress=0.5
            )
            try:
                result = await web_service.retrieve_webpage(url=url, extract_text_only=True)
                webpage = result["webpage"]
                pages.append({
                    "url": url,
                    "title": webpage.title,
                    "content": webpage.content[:6000]  # Limit per page
                })
                all_sources.append(url)
            except Exception as e:
                logger.error(f"Fetch error for {url}: {e}")

        context.set_variable("all_sources", all_sources)

        if not pages:
            yield StepProgress(message="Failed to fetch any pages", progress=0.6)
            max_iterations = context.get_variable("max_iterations", 5)
            if iteration >= max_iterations:
                context.set_variable("retrieval_complete", True)
            yield StepOutput(
                success=True,
                data={**checklist_data, "current_iteration": iteration, "sources": all_sources},
                display_title=f"Iteration {iteration}",
                display_content="Could not fetch any web pages this iteration."
            )
            return

        yield StepProgress(
            message=f"Extracting information from {len(pages)} pages...",
            progress=0.7,
            details={"pages_fetched": len(pages)}
        )

        # Step 5: Extract relevant information
        questions_text = "\n".join(f"{i+1}. {item['description']}" for i, item in enumerate(target_items))
        pages_text = ""
        for p in pages:
            pages_text += f"=== {p['title']} ({p['url']}) ===\n{p['content']}\n\n"

        extract_response = await client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=2048,
            temperature=0.2,
            messages=[{
                "role": "user",
                "content": f"""Extract information from these pages that answers our research questions.

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

        extractions = _parse_llm_json(extract_response.content[0].text)

        # Step 6: Update checklist with findings
        if extractions and isinstance(extractions, dict):
            for ext in extractions.get("extractions", []):
                idx = ext.get("question_index", 0) - 1
                if 0 <= idx < len(target_items):
                    target_id = target_items[idx]["id"]
                    # Find and update the actual item in items list
                    for item in items:
                        if item["id"] == target_id:
                            new_findings = ext.get("findings", [])
                            # Add findings with source info
                            for finding in new_findings:
                                item["findings"].append({
                                    "content": finding,
                                    "source": pages[0]["url"] if pages else "unknown",
                                    "confidence": "medium"
                                })
                            if ext.get("complete", False):
                                item["status"] = "complete"
                            elif item["findings"]:
                                item["status"] = "partial"
                            break

        # Calculate new progress
        new_completed = len([item for item in items if item.get("status") == "complete"])
        all_complete = all(item.get("status") == "complete" for item in items)

        yield StepProgress(
            message=f"Updated checklist: {new_completed}/{total_items} items complete",
            progress=new_completed / total_items if total_items > 0 else 0.9
        )

        # Check completion
        max_iterations = context.get_variable("max_iterations", 5)
        if all_complete or iteration >= max_iterations:
            context.set_variable("retrieval_complete", True)
        else:
            context.set_variable("retrieval_complete", False)

        # Build display content
        display_content = f"## Retrieval Iteration {iteration}\n\n"
        display_content += f"**Queries used:** {', '.join(new_queries)}\n\n"
        display_content += f"**Pages fetched:** {len(pages)}\n"
        for p in pages:
            display_content += f"- [{p['title']}]({p['url']})\n"
        display_content += f"\n**Checklist progress:** {new_completed}/{total_items} complete\n"

        yield StepOutput(
            success=True,
            data={
                **checklist_data,
                "items": items,
                "retrieval_complete": all_complete or iteration >= max_iterations,
                "current_iteration": iteration,
                "sources": all_sources
            },
            display_title=f"Retrieval Iteration {iteration}",
            display_content=display_content,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error in retrieval iteration")
        yield StepOutput(
            success=False,
            error=f"Failed retrieval iteration: {str(e)}"
        )


async def compile_final_answer(context: WorkflowContext) -> StepOutput:
    """
    Step 4: Compile all findings into a final comprehensive answer.
    """
    retrieval_data = context.get_step_output("run_retrieval")
    if not retrieval_data:
        return StepOutput(success=False, error="No retrieval data available")

    refined_question = retrieval_data.get("refined_question", "")
    items = retrieval_data.get("items", [])

    try:
        client = get_async_llm_client()

        # Build context from all findings
        findings_context = ""
        for item in items:
            findings_context += f"\n## {item['description']}\n"
            for finding in item.get("findings", []):
                findings_context += f"- {finding.get('content', '')} (Source: {finding.get('source', 'Unknown')})\n"

        prompt = f"""You are compiling a comprehensive research answer.

        Research Question: "{refined_question}"

        Collected Findings:
        {findings_context}

        Please write a comprehensive, well-structured answer that:
        1. Directly addresses the research question
        2. Synthesizes all the findings coherently
        3. Notes any gaps or uncertainties
        4. Provides a clear conclusion

        Write in a clear, professional style."""

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )

        final_answer = response.content[0].text

        # Collect all sources
        sources = []
        for item in items:
            for finding in item.get("findings", []):
                if finding.get("source"):
                    sources.append(finding["source"])

        return StepOutput(
            success=True,
            data={
                "question": refined_question,
                "answer": final_answer,
                "sources": list(set(sources)),
                "checklist_summary": [
                    {
                        "description": item["description"],
                        "status": item["status"],
                        "findings_count": len(item.get("findings", []))
                    }
                    for item in items
                ]
            },
            display_title="Research Complete",
            display_content=final_answer,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error compiling final answer")
        return StepOutput(
            success=False,
            error=f"Failed to compile answer: {str(e)}"
        )


# =============================================================================
# Edge Condition Functions
# =============================================================================

def should_continue_retrieval(context: WorkflowContext) -> bool:
    """Edge condition: Return True if we should loop back to retrieval."""
    return not context.get_variable("retrieval_complete", False)


def retrieval_is_complete(context: WorkflowContext) -> bool:
    """Edge condition: Return True if retrieval is done."""
    return context.get_variable("retrieval_complete", False)


# =============================================================================
# Workflow Graph Definition
# =============================================================================

research_workflow = WorkflowGraph(
    id="research",
    name="Research Workflow",
    description="Structured research with question refinement, answer checklist, iterative retrieval, and synthesis",
    icon="beaker",
    category="research",

    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The research question or topic"
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

    entry_node="formulate_question",

    nodes={
        # Step 1: Formulate question
        "formulate_question": StepNode(
            id="formulate_question",
            name="Formulate Question",
            description="Refine the research question for clarity and focus",
            node_type="execute",
            execute_fn=formulate_question,
            ui_component="question_stage"
        ),

        # Checkpoint: User approves/edits question
        "question_checkpoint": StepNode(
            id="question_checkpoint",
            name="Review Question",
            description="Review and approve the refined question",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Research Question",
                description="Please review the refined question. You can edit it or approve to continue.",
                allowed_actions=[
                    CheckpointAction.APPROVE,
                    CheckpointAction.EDIT,
                    CheckpointAction.REJECT
                ],
                editable_fields=["refined_question", "scope"]
            ),
            ui_component="question_stage"
        ),

        # Step 2: Build checklist
        "build_checklist": StepNode(
            id="build_checklist",
            name="Build Answer Checklist",
            description="Create a checklist of what a complete answer needs",
            node_type="execute",
            execute_fn=build_checklist,
            ui_component="checklist_stage"
        ),

        # Checkpoint: User reviews/edits checklist
        "checklist_checkpoint": StepNode(
            id="checklist_checkpoint",
            name="Review Checklist",
            description="Review and modify the answer checklist",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Answer Checklist",
                description="Review the checklist items. You can add, remove, or modify items.",
                allowed_actions=[
                    CheckpointAction.APPROVE,
                    CheckpointAction.EDIT,
                    CheckpointAction.REJECT
                ],
                editable_fields=["items"]
            ),
            ui_component="checklist_stage"
        ),

        # Step 3: Retrieval iteration
        "run_retrieval": StepNode(
            id="run_retrieval",
            name="Run Retrieval",
            description="Search and collect findings for checklist items",
            node_type="execute",
            execute_fn=run_retrieval_iteration,
            ui_component="retrieval_stage"
        ),

        # Checkpoint: User reviews retrieval results
        "retrieval_checkpoint": StepNode(
            id="retrieval_checkpoint",
            name="Review Findings",
            description="Review collected findings before final synthesis",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Research Findings",
                description="Review the findings collected. You can request more research or proceed to synthesis.",
                allowed_actions=[
                    CheckpointAction.APPROVE,
                    CheckpointAction.REJECT  # Reject = do more retrieval
                ],
                editable_fields=[]
            ),
            ui_component="retrieval_stage"
        ),

        # Step 4: Compile final answer
        "compile_final": StepNode(
            id="compile_final",
            name="Compile Answer",
            description="Synthesize all findings into a comprehensive answer",
            node_type="execute",
            execute_fn=compile_final_answer,
            ui_component="final_stage"
        ),

        # Final checkpoint: User accepts the answer
        "final_checkpoint": StepNode(
            id="final_checkpoint",
            name="Review Final Answer",
            description="Review the final compiled answer",
            node_type="checkpoint",
            checkpoint_config=CheckpointConfig(
                title="Review Final Answer",
                description="Review the final answer. Save it or request revisions.",
                allowed_actions=[
                    CheckpointAction.APPROVE,
                    CheckpointAction.REJECT
                ],
                editable_fields=[]
            ),
            ui_component="final_stage"
        ),
    },

    edges=[
        # Linear flow: formulate -> question checkpoint -> build checklist -> checklist checkpoint
        Edge(from_node="formulate_question", to_node="question_checkpoint"),
        Edge(from_node="question_checkpoint", to_node="build_checklist"),
        Edge(from_node="build_checklist", to_node="checklist_checkpoint"),
        Edge(from_node="checklist_checkpoint", to_node="run_retrieval"),

        # Retrieval loop: run_retrieval -> (loop back if not complete, else to checkpoint)
        Edge(from_node="run_retrieval", to_node="run_retrieval",
             condition=should_continue_retrieval, label="continue"),
        Edge(from_node="run_retrieval", to_node="retrieval_checkpoint",
             condition=retrieval_is_complete, label="complete"),

        # After retrieval checkpoint -> compile
        Edge(from_node="retrieval_checkpoint", to_node="compile_final"),

        # Final flow
        Edge(from_node="compile_final", to_node="final_checkpoint"),
        # final_checkpoint has no outgoing edges = end of workflow
    ]
)
