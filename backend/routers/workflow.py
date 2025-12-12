"""
Workflow API Router

Handles workflow step execution via dedicated step agent.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
import json

from database import get_db
from services.step_execution_service import StepExecutionService, StepAssignment

router = APIRouter(prefix="/workflow", tags=["workflow"])

# For now, hardcode user_id = 1 (same as other routers)
def get_current_user_id() -> int:
    return 1


class StepExecutionRequest(BaseModel):
    step_number: int
    description: str
    input_data: str
    output_format: str
    available_tools: List[str] = []


class StepExecutionResponse(BaseModel):
    success: bool
    output: str
    content_type: str
    error: Optional[str] = None


@router.post("/execute-step", response_model=StepExecutionResponse)
async def execute_step(
    request: StepExecutionRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Execute a single workflow step using the dedicated step agent."""

    service = StepExecutionService(db, user_id)

    assignment = StepAssignment(
        step_number=request.step_number,
        description=request.description,
        input_data=request.input_data,
        output_format=request.output_format,
        available_tools=request.available_tools
    )

    result = await service.execute(assignment)

    return StepExecutionResponse(
        success=result.success,
        output=result.output,
        content_type=result.content_type,
        error=result.error
    )
