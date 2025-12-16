"""
Workflow API Router

Endpoints for listing, starting, and managing workflows.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from workflows import (
    workflow_registry,
    workflow_engine,
    CheckpointAction,
    WorkflowStatus,
)
from schemas.workflow import WorkflowGraph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# =============================================================================
# Request/Response Models
# =============================================================================

class WorkflowSummary(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    category: str


class WorkflowListResponse(BaseModel):
    workflows: List[WorkflowSummary]
    categories: List[str]


class StartWorkflowRequest(BaseModel):
    workflow_id: Optional[str] = None  # Reference to registered template
    workflow_graph: Optional[Dict[str, Any]] = None  # Inline graph definition
    initial_input: Dict[str, Any]
    conversation_id: Optional[int] = None


class StartWorkflowResponse(BaseModel):
    instance_id: str
    workflow_id: str
    status: str


class ResumeWorkflowRequest(BaseModel):
    action: str  # "approve", "edit", "reject", "skip"
    user_data: Optional[Dict[str, Any]] = None


class WorkflowStateResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    current_node: Optional[Dict[str, Any]]
    step_data: Dict[str, Any]
    node_states: Dict[str, Any]
    created_at: str
    updated_at: str
    completed_at: Optional[str]


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/list", response_model=WorkflowListResponse)
async def list_workflows():
    """List all available workflow templates."""
    workflows = workflow_registry.list_all_dict()
    categories = workflow_registry.list_categories()

    return WorkflowListResponse(
        workflows=[WorkflowSummary(**w) for w in workflows],
        categories=categories
    )


@router.get("/templates/{workflow_id}")
async def get_workflow_template(workflow_id: str):
    """Get details of a specific workflow template."""
    workflow_dict = workflow_registry.to_dict(workflow_id)
    if not workflow_dict:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return workflow_dict


@router.post("/start", response_model=StartWorkflowResponse)
async def start_workflow(request: StartWorkflowRequest):
    """
    Start a new workflow instance.

    Can accept either:
    - workflow_id: Reference to a registered template
    - workflow_graph: Inline graph definition (for agent-designed workflows)
    """
    try:
        if request.workflow_graph:
            # Create instance from inline graph definition
            graph = WorkflowGraph.from_dict(request.workflow_graph)

            # Validate the graph
            validation_errors = graph.validate()
            if validation_errors:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid workflow graph: {', '.join(validation_errors)}"
                )

            instance = workflow_engine.create_instance_from_graph(
                graph=graph,
                initial_input=request.initial_input,
                conversation_id=request.conversation_id
            )
        elif request.workflow_id:
            # Create instance from registered template
            instance = workflow_engine.create_instance(
                workflow_id=request.workflow_id,
                initial_input=request.initial_input,
                conversation_id=request.conversation_id
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either workflow_id or workflow_graph must be provided"
            )

        return StartWorkflowResponse(
            instance_id=instance.id,
            workflow_id=instance.workflow_id,
            status=instance.status.value
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/instances/{instance_id}/run")
async def run_workflow(instance_id: str):
    """
    Start or continue running a workflow instance.
    Returns a stream of events as the workflow executes.
    """
    instance = workflow_engine.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")

    async def event_stream():
        try:
            async for event in workflow_engine.start(instance_id):
                event_data = {
                    'event_type': event.event_type,
                    'instance_id': event.instance_id,
                    'node_id': event.node_id,
                    'node_name': event.node_name,
                    'data': event.data,
                    'error': event.error
                }
                yield f"data: {json.dumps(event_data)}\n\n"
        except Exception as e:
            logger.exception(f"Error in workflow event stream: {e}")
            yield f"data: {json.dumps({'event_type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/instances/{instance_id}/resume")
async def resume_workflow(instance_id: str, request: ResumeWorkflowRequest):
    """
    Resume a workflow from a checkpoint.
    Returns a stream of events as the workflow continues.
    """
    instance = workflow_engine.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")

    if instance.status != WorkflowStatus.WAITING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume instance in status '{instance.status.value}'"
        )

    # Map string action to enum
    try:
        action = CheckpointAction(request.action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}")

    async def event_stream():
        try:
            async for event in workflow_engine.resume(instance_id, action, request.user_data):
                event_data = {
                    'event_type': event.event_type,
                    'instance_id': event.instance_id,
                    'node_id': event.node_id,
                    'node_name': event.node_name,
                    'data': event.data,
                    'error': event.error
                }
                yield f"data: {json.dumps(event_data)}\n\n"
        except Exception as e:
            logger.exception(f"Error in workflow resume stream: {e}")
            yield f"data: {json.dumps({'event_type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/instances/{instance_id}", response_model=WorkflowStateResponse)
async def get_workflow_state(instance_id: str):
    """Get the current state of a workflow instance."""
    state = workflow_engine.get_instance_state(instance_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Instance '{instance_id}' not found")
    return WorkflowStateResponse(**state)


@router.post("/instances/{instance_id}/cancel")
async def cancel_workflow(instance_id: str):
    """Cancel a running workflow."""
    success = workflow_engine.cancel(instance_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel workflow")
    return {"status": "cancelled"}


@router.post("/instances/{instance_id}/pause")
async def pause_workflow(instance_id: str):
    """Pause a running workflow."""
    success = workflow_engine.pause(instance_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot pause workflow")
    return {"status": "paused"}
