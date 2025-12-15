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
from typing import Any, Dict
import anthropic

from schemas.workflow import (
    WorkflowGraph,
    StepNode,
    Edge,
    StepOutput,
    CheckpointConfig,
    CheckpointAction,
    WorkflowContext,
)

logger = logging.getLogger(__name__)

# LLM client - initialized lazily
_client = None


def get_llm_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


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
        client = get_llm_client()

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

        response = client.messages.create(
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
        client = get_llm_client()

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

        response = client.messages.create(
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


async def run_retrieval_iteration(context: WorkflowContext) -> StepOutput:
    """
    Step 3: Run one iteration of the retrieval loop.
    Searches for information and updates the checklist with findings.
    """
    # Get checklist data from either build_checklist or previous retrieval
    checklist_data = context.get_step_output("run_retrieval") or context.get_step_output("build_checklist")
    if not checklist_data:
        return StepOutput(success=False, error="No checklist data available")

    # Get or initialize retrieval state
    iteration = context.get_variable("retrieval_iteration", 0) + 1
    context.set_variable("retrieval_iteration", iteration)

    items = checklist_data.get("items", [])
    refined_question = checklist_data.get("refined_question", "")

    # Find pending items to research
    pending_items = [item for item in items if item.get("status") == "pending"]

    if not pending_items:
        # All items complete - set flag for edge condition
        context.set_variable("retrieval_complete", True)
        return StepOutput(
            success=True,
            data={
                **checklist_data,
                "retrieval_complete": True,
                "total_iterations": iteration
            },
            display_title=f"Retrieval Complete",
            display_content=f"All checklist items have been addressed after {iteration} iterations.",
            content_type="markdown"
        )

    try:
        # For now, simulate retrieval with LLM
        # In production, this would use actual search tools
        client = get_llm_client()

        target_item = pending_items[0]  # Focus on highest priority pending

        prompt = f"""You are researching to answer a question. Focus on finding information for one specific aspect.

        Research Question: "{refined_question}"

        Current focus: "{target_item['description']}"

        Provide findings that address this aspect. Include:
        1. Key facts or information found
        2. Any sources or references (simulate for now)
        3. Confidence level in the findings

        Respond in JSON format:
        {{
            "findings": [
                {{
                    "content": "The finding or fact",
                    "source": "Source reference",
                    "confidence": "high|medium|low"
                }}
            ],
            "status": "complete|partial|pending",
            "summary": "Brief summary of what was found"
        }}"""

        response = client.messages.create(
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

        result = json.loads(content.strip())

        # Update the target item with findings
        for item in items:
            if item["id"] == target_item["id"]:
                item["findings"].extend(result.get("findings", []))
                item["status"] = result.get("status", "partial")
                break

        # Check completion and set flag for edge condition
        all_complete = all(item.get("status") == "complete" for item in items)
        context.set_variable("retrieval_complete", all_complete)

        # Check max iterations
        max_iterations = context.get_variable("max_iterations", 10)
        if iteration >= max_iterations:
            context.set_variable("retrieval_complete", True)

        display_content = f"## Retrieval Iteration {iteration}\n\n"
        display_content += f"**Researching:** {target_item['description']}\n\n"
        display_content += f"**Summary:** {result.get('summary', 'No summary')}\n\n"
        display_content += "### Findings:\n"
        for finding in result.get("findings", []):
            display_content += f"- {finding.get('content', '')} _{finding.get('source', '')}_\n"

        return StepOutput(
            success=True,
            data={
                **checklist_data,
                "items": items,
                "retrieval_complete": all_complete or iteration >= max_iterations,
                "current_iteration": iteration,
                "last_researched": target_item["id"]
            },
            display_title=f"Retrieval Iteration {iteration}",
            display_content=display_content,
            content_type="markdown"
        )

    except Exception as e:
        logger.exception("Error in retrieval iteration")
        return StepOutput(
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
        client = get_llm_client()

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

        response = client.messages.create(
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
