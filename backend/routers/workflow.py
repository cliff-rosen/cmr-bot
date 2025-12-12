"""
Workflow API Router

Handles workflow step execution via dedicated step agent with SSE streaming.
Also provides tool registry endpoints.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import asyncio

from database import get_db
from services.step_execution_service import (
    StepExecutionService,
    StepAssignment,
    StepInputSource as StepInputSourceDataclass
)
from tools import get_all_tools

router = APIRouter(prefix="/workflow", tags=["workflow"])


# For now, hardcode user_id = 1 (same as other routers)
def get_current_user_id() -> int:
    return 1


class StepInputSource(BaseModel):
    content: str
    data: Optional[Any] = None  # Structured data when source produced 'data' content_type


class StepExecutionRequest(BaseModel):
    step_number: int
    description: str
    input_data: Dict[str, StepInputSource]  # Named inputs with content and optional structured data
    output_format: str
    available_tools: List[str] = []


@router.post("/execute-step")
async def execute_step(
    request: StepExecutionRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Execute a workflow step with SSE streaming for status updates."""

    service = StepExecutionService(db, user_id)

    # Convert Pydantic models to dataclass objects
    input_data_converted = {
        key: StepInputSourceDataclass(content=source.content, data=source.data)
        for key, source in request.input_data.items()
    }

    assignment = StepAssignment(
        step_number=request.step_number,
        description=request.description,
        input_data=input_data_converted,
        output_format=request.output_format,
        available_tools=request.available_tools
    )

    async def event_generator():
        async for update in service.execute_streaming(assignment):
            yield f"data: {update.to_json()}\n\n"
            await asyncio.sleep(0)  # Allow other tasks to run

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# =============================================================================
# Tool Registry Endpoints
# =============================================================================

class ToolInfo(BaseModel):
    """Tool information for frontend."""
    name: str
    description: str
    category: str


@router.get("/tools", response_model=List[ToolInfo])
async def list_tools():
    """Get all available tools."""
    tools = get_all_tools()
    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            category=t.category
        )
        for t in tools
    ]
