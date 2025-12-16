"""
Interactive Research Workflow Tool

An interactive research workflow that pauses at each stage for user review and approval:

1. Question Formulation - Refine the research question
2. Checklist Building - Define what a complete answer needs
3. Retrieval Loop - Iterative search and findings collection
4. Final Compilation - Synthesize findings into answer

Unlike deep_research which runs autonomously, this tool returns workspace payloads
at each stage and waits for user interaction before proceeding.
"""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Generator
from dataclasses import dataclass, field, asdict
from sqlalchemy.orm import Session
import anthropic

from tools.registry import ToolConfig, ToolResult, ToolProgress, register_tool
from tools.executor import run_async

logger = logging.getLogger(__name__)

RESEARCH_MODEL = "claude-sonnet-4-20250514"


def generate_id() -> str:
    """Generate a unique ID."""
    return str(uuid.uuid4())[:8]


def now_iso() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


class ResearchWorkflowEngine:
    """Manages interactive research workflow stages."""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    def _call_llm(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.3) -> str:
        """Make an LLM call and return the response text."""
        response = self.client.messages.create(
            model=RESEARCH_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    def _parse_json(self, text: str) -> Optional[Any]:
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

    def start_workflow(self, query: str) -> Dict[str, Any]:
        """
        Start a new research workflow by formulating the question.
        Returns the workflow state at the 'question' stage.
        """
        workflow_id = generate_id()

        # Use LLM to refine the question
        prompt = f"""Analyze this research query and formulate a proper research question.

        User's query: "{query}"

        Respond with JSON:
        {{
            "refined_question": "A clear, well-scoped research question",
            "scope": "Description of what is and isn't included in this research",
            "key_terms": ["term1", "term2", "term3"],
            "constraints": ["Any limitations or constraints mentioned or implied"]
        }}

        JSON:"""

        response_text = self._call_llm(prompt)
        parsed = self._parse_json(response_text)

        if not parsed:
            # Fallback
            parsed = {
                "refined_question": query,
                "scope": "General research on the topic",
                "key_terms": [],
                "constraints": []
            }

        workflow = {
            "id": workflow_id,
            "stage": "question",
            "original_query": query,
            "created_at": now_iso(),
            "question": {
                "original": query,
                "refined": parsed.get("refined_question", query),
                "scope": parsed.get("scope", ""),
                "key_terms": parsed.get("key_terms", []),
                "constraints": parsed.get("constraints", []),
                "approved": False
            }
        }

        return workflow

    def build_checklist(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the answer checklist based on the approved question.
        Returns updated workflow at 'checklist' stage.
        """
        question = workflow.get("question", {})
        refined = question.get("refined", workflow.get("original_query", ""))
        scope = question.get("scope", "")

        prompt = f"""Create a checklist of what a complete answer to this research question should include.

        Research Question: {refined}
        Scope: {scope}

        Create 4-7 specific checklist items. Each item should be a distinct aspect of the answer.

        Respond with JSON:
        {{
            "items": [
                {{
                    "description": "What this part of the answer should cover",
                    "rationale": "Why this is needed for a complete answer",
                    "priority": "high|medium|low"
                }}
            ]
        }}

        JSON:"""

        response_text = self._call_llm(prompt)
        parsed = self._parse_json(response_text)

        if not parsed or not parsed.get("items"):
            # Fallback
            parsed = {
                "items": [
                    {"description": "Overview and background", "rationale": "Provides context", "priority": "high"},
                    {"description": "Key findings and evidence", "rationale": "Core content", "priority": "high"},
                    {"description": "Different perspectives or approaches", "rationale": "Comprehensive coverage", "priority": "medium"},
                    {"description": "Limitations and gaps", "rationale": "Honest assessment", "priority": "medium"}
                ]
            }

        checklist_items = []
        for item in parsed.get("items", []):
            checklist_items.append({
                "id": generate_id(),
                "description": item.get("description", ""),
                "rationale": item.get("rationale", ""),
                "status": "pending",
                "findings": [],
                "priority": item.get("priority", "medium")
            })

        workflow["stage"] = "checklist"
        workflow["checklist"] = {
            "items": checklist_items,
            "approved": False
        }

        return workflow

    def start_retrieval(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize the retrieval state.
        Returns updated workflow ready for retrieval.
        """
        workflow["stage"] = "retrieval"
        workflow["retrieval"] = {
            "iteration": 0,
            "max_iterations": 10,
            "iterations": [],
            "current_focus": [],
            "status": "paused"
        }
        return workflow

    def run_retrieval_iteration(
        self, workflow: Dict[str, Any], db: Session, user_id: int
    ) -> Generator[ToolProgress, None, Dict[str, Any]]:
        """
        Run one iteration of the retrieval loop.
        Yields progress updates and returns updated workflow.
        """
        retrieval = workflow.get("retrieval", {})
        checklist = workflow.get("checklist", {})
        question = workflow.get("question", {})

        retrieval["status"] = "searching"
        retrieval["iteration"] = retrieval.get("iteration", 0) + 1
        iteration_num = retrieval["iteration"]

        yield ToolProgress(
            stage="iteration_start",
            message=f"Starting iteration {iteration_num}",
            data={"iteration": iteration_num}
        )

        # Find pending/partial checklist items to focus on
        items = checklist.get("items", [])
        focus_items = [item for item in items if item["status"] in ("pending", "partial")][:3]
        focus_ids = [item["id"] for item in focus_items]
        retrieval["current_focus"] = focus_ids

        if not focus_items:
            retrieval["status"] = "complete"
            yield ToolProgress(
                stage="complete",
                message="All checklist items satisfied",
                data={}
            )
            workflow["retrieval"] = retrieval
            return workflow

        # Generate search queries
        yield ToolProgress(
            stage="generating_queries",
            message="Generating search queries...",
            data={"focus_items": [f["description"] for f in focus_items]}
        )

        focus_text = "\n".join(f"- {f['description']}" for f in focus_items)
        refined_question = question.get("refined", "")

        prompt = f"""Generate search queries to find information for these aspects of the research:

        Research question: {refined_question}

        Information needed:
        {focus_text}

        Generate 2-3 targeted search queries. Mix PubMed-style queries (for scientific literature) and general web queries.

        Respond with JSON:
        {{
            "queries": [
                {{"query": "search query text", "source": "pubmed_smart|web", "rationale": "why this query"}}
            ]
        }}

        JSON:"""

        response_text = self._call_llm(prompt, temperature=0.5)
        parsed = self._parse_json(response_text)

        queries = []
        if parsed and parsed.get("queries"):
            for q in parsed["queries"][:3]:
                queries.append({
                    "id": generate_id(),
                    "query": q.get("query", ""),
                    "source": q.get("source", "web"),
                    "rationale": q.get("rationale", ""),
                    "results_count": 0,
                    "useful_results": 0,
                    "executed_at": now_iso()
                })

        yield ToolProgress(
            stage="queries_generated",
            message=f"Generated {len(queries)} queries",
            data={"queries": [q["query"] for q in queries]}
        )

        # Execute searches
        retrieval["status"] = "searching"
        yield ToolProgress(
            stage="searching",
            message="Executing searches...",
            data={}
        )

        all_results = []
        for query_info in queries:
            try:
                if query_info["source"] == "pubmed_smart":
                    # Use PubMed smart search
                    from services.pubmed_service import PubMedService
                    service = PubMedService()
                    articles, meta = service.search_articles(
                        query=query_info["query"],
                        max_results=10
                    )
                    query_info["results_count"] = len(articles)
                    for article in articles[:5]:
                        all_results.append({
                            "title": article.title,
                            "source": f"PubMed: {article.pmid}",
                            "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/",
                            "content": article.abstract or "",
                            "query_id": query_info["id"]
                        })
                else:
                    # Use web search
                    from services.search_service import SearchService
                    search_service = SearchService()
                    if not search_service.initialized:
                        search_service.initialize()
                    result = run_async(
                        search_service.search(search_term=query_info["query"], num_results=5)
                    )
                    search_results = result.get("search_results", [])
                    query_info["results_count"] = len(search_results)
                    for sr in search_results[:3]:
                        all_results.append({
                            "title": sr.title,
                            "source": "Web Search",
                            "source_url": sr.url,
                            "content": sr.snippet,
                            "query_id": query_info["id"]
                        })
            except Exception as e:
                logger.error(f"Search error for query '{query_info['query']}': {e}")

        yield ToolProgress(
            stage="search_complete",
            message=f"Found {len(all_results)} results",
            data={"result_count": len(all_results)}
        )

        # Review results and extract findings
        retrieval["status"] = "reviewing"
        yield ToolProgress(
            stage="reviewing",
            message="Reviewing results and extracting findings...",
            data={}
        )

        if all_results:
            # Use LLM to extract relevant findings
            results_text = ""
            for i, r in enumerate(all_results[:10]):
                results_text += f"{i+1}. {r['title']}\n   Source: {r['source']}\n   {r['content'][:500]}\n\n"

            prompt = f"""Review these search results and extract findings relevant to our research.

            Research question: {refined_question}

            Checklist items we're looking for:
            {focus_text}

            Search results:
            {results_text}

            For each checklist item, identify relevant findings from the results.

            Respond with JSON:
            {{
                "findings": [
                    {{
                        "checklist_item_description": "which checklist item this supports",
                        "title": "brief title for this finding",
                        "content": "the relevant information extracted",
                        "source_index": 1,
                        "relevance": "why this is relevant",
                        "confidence": "high|medium|low"
                    }}
                ]
            }}

            JSON:"""

            response_text = self._call_llm(prompt, max_tokens=2048)
            parsed = self._parse_json(response_text)

            findings_added = 0
            if parsed and parsed.get("findings"):
                for f in parsed["findings"]:
                    # Find matching checklist item
                    item_desc = f.get("checklist_item_description", "")
                    source_idx = f.get("source_index", 1) - 1

                    for item in items:
                        if item["description"].lower() in item_desc.lower() or item_desc.lower() in item["description"].lower():
                            # Add finding to this item
                            source_info = all_results[source_idx] if 0 <= source_idx < len(all_results) else {}
                            finding = {
                                "id": generate_id(),
                                "checklist_item_id": item["id"],
                                "source": source_info.get("source", "Unknown"),
                                "source_url": source_info.get("source_url"),
                                "title": f.get("title", ""),
                                "content": f.get("content", ""),
                                "relevance": f.get("relevance", ""),
                                "confidence": f.get("confidence", "medium"),
                                "added_at": now_iso()
                            }
                            item["findings"].append(finding)
                            findings_added += 1

                            # Update status
                            if len(item["findings"]) >= 3:
                                item["status"] = "complete"
                            elif len(item["findings"]) >= 1:
                                item["status"] = "partial"
                            break

                for q in queries:
                    q["useful_results"] = sum(1 for f in parsed.get("findings", []) if any(
                        r.get("query_id") == q["id"] for r in all_results
                    ))

        # Record iteration
        iteration_record = {
            "iteration_number": iteration_num,
            "focus_items": focus_ids,
            "queries": queries,
            "results_reviewed": len(all_results),
            "findings_added": findings_added,
            "notes": f"Searched {len(queries)} queries, reviewed {len(all_results)} results",
            "completed_at": now_iso()
        }
        retrieval["iterations"].append(iteration_record)
        retrieval["status"] = "paused"

        yield ToolProgress(
            stage="iteration_complete",
            message=f"Iteration {iteration_num} complete: added {findings_added} findings",
            data={
                "findings_added": findings_added,
                "checklist_progress": sum(1 for i in items if i["status"] == "complete") / len(items) * 100 if items else 0
            }
        )

        workflow["retrieval"] = retrieval
        workflow["checklist"]["items"] = items
        return workflow

    def compile_final(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compile all findings into a final answer.
        Returns updated workflow at 'complete' stage.
        """
        question = workflow.get("question", {})
        checklist = workflow.get("checklist", {})
        items = checklist.get("items", [])

        # Build findings summary
        findings_text = ""
        all_sources = []
        for item in items:
            findings_text += f"\n## {item['description']}\n"
            if item["findings"]:
                for f in item["findings"]:
                    findings_text += f"- {f['title']}: {f['content']}\n"
                    if f.get("source_url") and f["source_url"] not in [s.get("url") for s in all_sources]:
                        all_sources.append({
                            "id": generate_id(),
                            "title": f.get("title", ""),
                            "url": f.get("source_url"),
                            "citation": f.get("source", ""),
                            "contribution": f"Supports: {item['description']}"
                        })
            else:
                findings_text += "- No findings collected\n"

        prompt = f"""Synthesize these research findings into a comprehensive answer.

        Research Question: {question.get('refined', '')}
        Scope: {question.get('scope', '')}

        Findings by topic:
        {findings_text}

        Write a well-organized answer that:
        1. Directly addresses the research question
        2. Integrates findings from all sources
        3. Notes any gaps or limitations
        4. Is written in clear, professional prose

        Also provide:
        - A brief summary (2-3 sentences)
        - Overall confidence level (high/medium/low) with explanation
        - List of limitations

        Respond with JSON:
        {{
            "answer": "The full answer in markdown format...",
            "summary": "Brief summary...",
            "confidence": "high|medium|low",
            "confidence_explanation": "Why this confidence level...",
            "limitations": ["limitation 1", "limitation 2"]
        }}

        JSON:"""

        response_text = self._call_llm(prompt, max_tokens=4096)
        parsed = self._parse_json(response_text)

        if not parsed:
            parsed = {
                "answer": "Unable to compile findings. Please review the checklist items directly.",
                "summary": "Compilation failed",
                "confidence": "low",
                "confidence_explanation": "Could not synthesize findings",
                "limitations": ["Automatic compilation failed"]
            }

        workflow["stage"] = "complete"
        workflow["final"] = {
            "answer": parsed.get("answer", ""),
            "summary": parsed.get("summary", ""),
            "confidence": parsed.get("confidence", "medium"),
            "confidence_explanation": parsed.get("confidence_explanation", ""),
            "limitations": parsed.get("limitations", []),
            "sources": all_sources,
            "approved": False
        }

        return workflow


# =============================================================================
# Tool Executor
# =============================================================================

def execute_research_workflow(
    params: Dict[str, Any],
    db: Session,
    user_id: int,
    context: Dict[str, Any]
) -> Generator[ToolProgress, None, ToolResult]:
    """
    Execute a research workflow action.

    Actions:
    - start: Start a new workflow with a query
    - approve_question: Approve the question and build checklist
    - approve_checklist: Approve checklist and start retrieval
    - run_iteration: Run one retrieval iteration
    - compile: Compile findings into final answer
    """
    action = params.get("action", "start")
    query = params.get("query", "")
    workflow_state = params.get("workflow_state")

    # Parse workflow_state if it comes as a JSON string
    if isinstance(workflow_state, str):
        try:
            workflow_state = json.loads(workflow_state)
        except json.JSONDecodeError:
            return ToolResult(text="Error: Invalid workflow state - could not parse JSON")

    engine = ResearchWorkflowEngine()

    if action == "start":
        if not query:
            return ToolResult(text="Error: No query provided for research workflow")

        yield ToolProgress(
            stage="formulating",
            message="Formulating research question...",
            data={"query": query}
        )

        workflow = engine.start_workflow(query)

        yield ToolProgress(
            stage="question_ready",
            message="Research question formulated - awaiting approval",
            data={"workflow": workflow}
        )

        # Return workspace payload for the research workflow
        return ToolResult(
            text=f"I've formulated a research question based on your query. Please review it in the workspace and approve when ready.",
            data={"workflow": workflow},
            workspace_payload={
                "type": "research",
                "title": "Research Workflow",
                "content": f"Research: {query}",
                "research_data": workflow
            }
        )

    elif action == "approve_question":
        if not workflow_state:
            return ToolResult(text="Error: No workflow state provided. You must pass the full workflow_state from the previous step.")

        if "question" not in workflow_state:
            return ToolResult(
                text=f"Error: workflow_state is missing 'question' field. "
                     f"You must pass the complete workflow_state object from the 'research' workspace payload. "
                     f"Received keys: {list(workflow_state.keys()) if isinstance(workflow_state, dict) else 'not a dict'}"
            )

        yield ToolProgress(
            stage="building_checklist",
            message="Building answer checklist...",
            data={}
        )

        # Mark question as approved
        workflow_state["question"]["approved"] = True
        workflow = engine.build_checklist(workflow_state)

        yield ToolProgress(
            stage="checklist_ready",
            message="Checklist created - awaiting approval",
            data={"workflow": workflow}
        )

        return ToolResult(
            text="I've created a checklist of what a complete answer should include. Please review and modify as needed, then approve to start the research.",
            data={"workflow": workflow},
            workspace_payload={
                "type": "research",
                "title": "Research Workflow",
                "content": f"Research: {workflow_state.get('original_query', '')}",
                "research_data": workflow
            }
        )

    elif action == "approve_checklist":
        if not workflow_state:
            return ToolResult(text="Error: No workflow state provided. You must pass the full workflow_state from the previous step.")

        if "checklist" not in workflow_state:
            return ToolResult(
                text=f"Error: workflow_state is missing 'checklist' field. "
                     f"You must pass the complete workflow_state object from the 'research' workspace payload. "
                     f"Current stage should be 'checklist'. Received keys: {list(workflow_state.keys()) if isinstance(workflow_state, dict) else 'not a dict'}"
            )

        # Mark checklist as approved and initialize retrieval
        workflow_state["checklist"]["approved"] = True
        workflow = engine.start_retrieval(workflow_state)

        return ToolResult(
            text="Checklist approved! The research retrieval is now ready. Click 'Start Research' to begin the iterative search process.",
            data={"workflow": workflow},
            workspace_payload={
                "type": "research",
                "title": "Research Workflow",
                "content": f"Research: {workflow_state.get('original_query', '')}",
                "research_data": workflow
            }
        )

    elif action == "run_iteration":
        if not workflow_state:
            return ToolResult(text="Error: No workflow state provided. You must pass the full workflow_state from the previous step.")

        if "retrieval" not in workflow_state or "checklist" not in workflow_state:
            return ToolResult(
                text=f"Error: workflow_state is missing required fields for retrieval. "
                     f"You must pass the complete workflow_state object from the 'research' workspace payload. "
                     f"Current stage should be 'retrieval'. Received keys: {list(workflow_state.keys()) if isinstance(workflow_state, dict) else 'not a dict'}"
            )

        # Run one retrieval iteration
        workflow = workflow_state
        for progress in engine.run_retrieval_iteration(workflow, db, user_id):
            yield progress
            if isinstance(progress, ToolProgress):
                continue
            workflow = progress  # Last yield is the updated workflow

        # Get the updated workflow from the generator
        # The run_retrieval_iteration returns the workflow at the end

        return ToolResult(
            text=f"Completed retrieval iteration. Review the findings and continue searching or compile the final answer when ready.",
            data={"workflow": workflow},
            workspace_payload={
                "type": "research",
                "title": "Research Workflow",
                "content": f"Research: {workflow.get('original_query', '')}",
                "research_data": workflow
            }
        )

    elif action == "compile":
        if not workflow_state:
            return ToolResult(text="Error: No workflow state provided. You must pass the full workflow_state from the previous step.")

        if "question" not in workflow_state or "checklist" not in workflow_state:
            return ToolResult(
                text=f"Error: workflow_state is missing required fields for compilation. "
                     f"You must pass the complete workflow_state object from the 'research' workspace payload. "
                     f"Received keys: {list(workflow_state.keys()) if isinstance(workflow_state, dict) else 'not a dict'}"
            )

        yield ToolProgress(
            stage="compiling",
            message="Compiling findings into final answer...",
            data={}
        )

        workflow = engine.compile_final(workflow_state)

        yield ToolProgress(
            stage="complete",
            message="Research complete!",
            data={"workflow": workflow}
        )

        return ToolResult(
            text="I've compiled all the findings into a comprehensive answer. Please review it in the workspace.",
            data={"workflow": workflow},
            workspace_payload={
                "type": "research",
                "title": "Research Workflow",
                "content": f"Research: {workflow_state.get('original_query', '')}",
                "research_data": workflow
            }
        )

    else:
        return ToolResult(text=f"Unknown action: {action}")


RESEARCH_WORKFLOW_TOOL = ToolConfig(
    name="research_workflow",
    description="""Start or continue an interactive research workflow. This tool guides you through:

    1. Question Formulation - Refine and scope the research question
    2. Checklist Building - Define what a complete answer needs
    3. Retrieval Loop - Iteratively search and collect findings
    4. Final Compilation - Synthesize findings into a comprehensive answer

    Unlike automatic research, this workflow pauses at each stage for your review and approval.

    Actions:
    - start: Begin a new research workflow with a query
    - approve_question: Approve the formulated question and build checklist
    - approve_checklist: Approve the checklist and prepare for retrieval
    - run_iteration: Execute one iteration of the retrieval loop
    - compile: Compile all findings into the final answer""",
    input_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "approve_question", "approve_checklist", "run_iteration", "compile"],
                "description": "The workflow action to perform"
            },
            "query": {
                "type": "string",
                "description": "The research query (required for 'start' action)"
            },
            "workflow_state": {
                "type": "object",
                "description": "The current workflow state (required for actions other than 'start')"
            }
        },
        "required": ["action"]
    },
    executor=execute_research_workflow,
    category="research",
    streaming=True
)


def register_research_workflow_tool():
    """Register the interactive research workflow tool."""
    register_tool(RESEARCH_WORKFLOW_TOOL)
    logger.info("Registered research_workflow tool")
