# Workflow Systems Inventory

## Overview

We have three separate workflow orchestration approaches that need consolidation:

| System | Orchestrator | Status |
|--------|--------------|--------|
| Frontend Orchestration | JavaScript (MainPage.tsx) | **Phase Out** |
| LLM Orchestration | Chat Agent via tools | **Table for Later** |
| Pipeline Engine | Python Backend | **Keep & Overhaul** |

---

## 1. Frontend Orchestration (PHASE OUT)

Frontend controls workflow execution step-by-step via API calls.

### Backend Components

| File | Purpose |
|------|---------|
| `backend/routers/workflow.py` | `/workflow/execute-step` endpoint |
| `backend/services/step_execution_service.py` | Executes individual steps with LLM+tools |

### Frontend Components

| File | Purpose |
|------|---------|
| `frontend/src/lib/api/workflowApi.ts` | `executeStepStreaming()` API client |
| `frontend/src/pages/MainPage.tsx` | Orchestration logic: `executeStep()`, `handleAcceptWip()`, `handleAcceptPlan()`, `activeWorkflow` state |
| `frontend/src/components/panels/workspace/WorkflowPipelineView.tsx` | Step-by-step execution view |

### Data Flow
```
Agent: design_workflow tool → WorkflowPlan payload
                                    ↓
Frontend: handleAcceptPlan() → executeStep(step1)
                                    ↓
API: POST /workflow/execute-step
                                    ↓
Backend: StepExecutionService.execute_streaming()
                                    ↓
Frontend: handleAcceptWip() → executeStep(step2)
                                    ↓
                              ... repeat ...
```

---

## 2. LLM Orchestration (TABLE FOR LATER)

Chat agent decides when to advance workflow via tool calls.

### Backend Components

| File | Purpose |
|------|---------|
| `backend/tools/builtin/research_workflow.py` | Interactive research tool with actions: start, approve_question, approve_checklist, run_iteration, compile |
| `backend/tools/builtin/workflow_builder.py` | `design_workflow` tool for agent to create workflow plans |

### Frontend Components

| File | Purpose |
|------|---------|
| `frontend/src/components/panels/workspace/ResearchWorkflowView.tsx` | Research-specific UI (938 lines) |
| `frontend/src/pages/MainPage.tsx` | Research workflow handlers: `handleProceedToNextStage()`, `handleRunRetrieval()` |

### Data Flow
```
User: "Research psilocybin"
           ↓
Agent: research_workflow(action="start")
           ↓
Tool: Returns workspace_payload {type: "research", research_data: {...}}
           ↓
Frontend: ResearchWorkflowView renders
           ↓
User: Clicks "Approve Question"
           ↓
Agent: research_workflow(action="approve_question", workflow_state={...})
           ↓
                              ... repeat ...
```

---

## 3. Pipeline Engine (KEEP & OVERHAUL)

Backend controls workflow execution with checkpoints for user input.

### Backend Components

| File | Purpose |
|------|---------|
| `backend/workflows/engine.py` | Workflow execution engine (current: linked-list with special step types) |
| `backend/workflows/registry.py` | Workflow template registry |
| `backend/workflows/templates/research.py` | Research workflow template (simulated retrieval) |
| `backend/workflows/templates/__init__.py` | Template exports |
| `backend/routers/workflows.py` | `/api/workflows/*` endpoints: list, start, resume, state |
| `backend/schemas/workflow.py` | Pydantic models for workflow data |

### Frontend Components

| File | Purpose |
|------|---------|
| `frontend/src/lib/api/workflowEngineApi.ts` | API client for engine endpoints |
| `frontend/src/lib/workflows/registry.ts` | Frontend workflow type registry |
| `frontend/src/lib/workflows/index.ts` | Workflow utilities export |
| `frontend/src/components/panels/workspace/WorkflowExecutionView.tsx` | Generic workflow execution view |
| `frontend/src/types/workflow.ts` | TypeScript types for workflow state |

### Data Flow
```
User/Agent: Start workflow via API
                    ↓
Backend: workflow_engine.start_workflow()
                    ↓
Engine: Execute steps, emit events via SSE
                    ↓
Engine: Hit checkpoint → pause, wait for user
                    ↓
Frontend: Show checkpoint UI
                    ↓
User: Approve/Edit/Reject
                    ↓
API: POST /api/workflows/{id}/resume
                    ↓
Engine: Continue execution
                    ↓
                ... repeat ...
```

---

## Consolidation Plan

### Target Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend                            │
│  ┌─────────────────────────────────────────────────┐    │
│  │  WorkflowExecutionView (generic)                │    │
│  │  - Renders current step                         │    │
│  │  - Shows checkpoint UI when paused              │    │
│  │  - Calls resume API on user action              │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend API                            │
│  POST /api/workflows/start                               │
│  POST /api/workflows/{id}/resume                         │
│  GET  /api/workflows/{id}/stream (SSE)                   │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│              Graph-Based Workflow Engine                 │
│  ┌─────────────────────────────────────────────────┐    │
│  │  WorkflowGraph                                  │    │
│  │  - nodes: Dict[str, StepNode]                   │    │
│  │  - edges: List[Edge] with conditions            │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Engine                                         │    │
│  │  - Evaluates edges to determine next node       │    │
│  │  - Executes step nodes (LLM calls, tools)       │    │
│  │  - Pauses at checkpoint nodes                   │    │
│  │  - Emits events via async generator             │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### What Changes

| Action | Files |
|--------|-------|
| **DELETE** | `backend/routers/workflow.py`, `backend/services/step_execution_service.py` |
| **DELETE** | `frontend/src/lib/api/workflowApi.ts` |
| **MODIFY** | `frontend/src/pages/MainPage.tsx` - Remove orchestration logic |
| **MODIFY** | `backend/workflows/engine.py` - Graph-based rewrite |
| **MODIFY** | `backend/schemas/workflow.py` - Graph schema |
| **MODIFY** | `backend/tools/builtin/workflow_builder.py` - Output graph format |
| **KEEP** | `backend/routers/workflows.py` - Engine API (expand as needed) |
| **KEEP** | `frontend/src/components/panels/workspace/WorkflowExecutionView.tsx` - Enhance |
| **TABLE** | `backend/tools/builtin/research_workflow.py` - LLM orchestration for later |
| **TABLE** | `frontend/src/components/panels/workspace/ResearchWorkflowView.tsx` |

---

## Graph-Based Engine Design (Proposed)

```python
@dataclass
class StepNode:
    id: str
    name: str
    node_type: Literal["execute", "checkpoint"]
    execute_fn: Optional[Callable]  # For execute nodes
    checkpoint_config: Optional[CheckpointConfig]  # For checkpoint nodes

@dataclass
class Edge:
    from_node: str
    to_node: str
    condition: Optional[Callable[[WorkflowContext], bool]] = None  # None = always take

@dataclass
class WorkflowGraph:
    nodes: Dict[str, StepNode]
    edges: List[Edge]
    entry_node: str
```

**Loops** = Edge pointing back to earlier node with condition
**Conditionals** = Multiple edges from same node with different conditions
**Linear flow** = Single edge with no condition
