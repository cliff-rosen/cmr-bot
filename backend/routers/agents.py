"""
Autonomous Agents API Router

Endpoints for managing autonomous background agents.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime

from database import get_db
from models import User, AgentLifecycle, AgentStatus, AgentRunStatus, AgentRunEventType
from routers.auth import get_current_user
from services.autonomous_agent_service import AutonomousAgentService

router = APIRouter(prefix="/api/agents", tags=["agents"])


# =============================================================================
# Request/Response Models
# =============================================================================

class CreateAgentRequest(BaseModel):
    name: str
    instructions: str
    lifecycle: AgentLifecycle
    description: Optional[str] = None
    tools: Optional[List[str]] = None
    schedule: Optional[str] = None
    monitor_interval_minutes: Optional[int] = None


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    instructions: Optional[str] = None
    tools: Optional[List[str]] = None
    schedule: Optional[str] = None
    monitor_interval_minutes: Optional[int] = None


class AgentResponse(BaseModel):
    agent_id: int
    name: str
    description: Optional[str]
    lifecycle: AgentLifecycle
    instructions: str
    tools: List[str]
    schedule: Optional[str]
    monitor_interval_minutes: Optional[int]
    status: AgentStatus
    total_runs: int
    total_assets_created: int
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class AgentRunResponse(BaseModel):
    run_id: int
    agent_id: int
    status: AgentRunStatus
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    result_summary: Optional[str]
    error: Optional[str]
    assets_created: int
    created_at: datetime

    class Config:
        from_attributes = True


class AgentDetailResponse(AgentResponse):
    recent_runs: List[AgentRunResponse]


class AgentRunEventResponse(BaseModel):
    event_id: int
    run_id: int
    event_type: AgentRunEventType
    message: str
    data: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/", response_model=AgentResponse)
async def create_agent(
    request: CreateAgentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new autonomous agent."""
    service = AutonomousAgentService(db, current_user.user_id)

    agent = service.create_agent(
        name=request.name,
        instructions=request.instructions,
        lifecycle=request.lifecycle,
        description=request.description,
        tools=request.tools,
        schedule=request.schedule,
        monitor_interval_minutes=request.monitor_interval_minutes
    )

    return AgentResponse.model_validate(agent)


@router.get("/", response_model=List[AgentResponse])
async def list_agents(
    include_completed: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all autonomous agents for the current user."""
    service = AutonomousAgentService(db, current_user.user_id)
    agents = service.list_agents(include_completed=include_completed)
    return [AgentResponse.model_validate(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get details of a specific agent including recent runs."""
    service = AutonomousAgentService(db, current_user.user_id)

    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    runs = service.get_agent_runs(agent_id, limit=10)

    return AgentDetailResponse(
        **AgentResponse.model_validate(agent).model_dump(),
        recent_runs=[AgentRunResponse.model_validate(r) for r in runs]
    )


@router.patch("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    request: UpdateAgentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an agent's properties."""
    service = AutonomousAgentService(db, current_user.user_id)

    update_data = request.model_dump(exclude_unset=True)
    agent = service.update_agent(agent_id, **update_data)

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse.model_validate(agent)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an agent and all its runs."""
    service = AutonomousAgentService(db, current_user.user_id)

    if not service.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agent not found")

    return {"success": True, "message": "Agent deleted"}


@router.post("/{agent_id}/pause", response_model=AgentResponse)
async def pause_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Pause an agent."""
    service = AutonomousAgentService(db, current_user.user_id)

    agent = service.pause_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return AgentResponse.model_validate(agent)


@router.post("/{agent_id}/resume", response_model=AgentResponse)
async def resume_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Resume a paused agent."""
    service = AutonomousAgentService(db, current_user.user_id)

    agent = service.resume_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found or not paused")

    return AgentResponse.model_validate(agent)


@router.post("/{agent_id}/run", response_model=AgentRunResponse)
async def trigger_run(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Manually trigger a run for an agent."""
    service = AutonomousAgentService(db, current_user.user_id)

    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    run = service.queue_run(agent_id)
    if not run:
        raise HTTPException(status_code=400, detail="Could not queue run - agent may not be active")

    return AgentRunResponse.model_validate(run)


@router.get("/{agent_id}/runs", response_model=List[AgentRunResponse])
async def get_agent_runs(
    agent_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get runs for a specific agent."""
    service = AutonomousAgentService(db, current_user.user_id)

    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    runs = service.get_agent_runs(agent_id, limit=limit)
    return [AgentRunResponse.model_validate(r) for r in runs]


@router.get("/runs/{run_id}/events", response_model=List[AgentRunEventResponse])
async def get_run_events(
    run_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get telemetry events for a specific run."""
    service = AutonomousAgentService(db, current_user.user_id)

    run = service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify the run belongs to an agent owned by the user
    agent = service.get_agent(run.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    events = service.get_run_events(run_id, limit=limit)
    return [AgentRunEventResponse.model_validate(e) for e in events]


class AssetSummaryResponse(BaseModel):
    asset_id: int
    name: str
    asset_type: str
    description: Optional[str]
    created_at: datetime
    run_id: Optional[int]

    class Config:
        from_attributes = True


@router.get("/{agent_id}/assets", response_model=List[AssetSummaryResponse])
async def get_agent_assets(
    agent_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get assets created by a specific agent."""
    from models import Asset

    service = AutonomousAgentService(db, current_user.user_id)

    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Query assets created by this agent
    assets = db.query(Asset).filter(
        Asset.created_by_agent_id == agent_id,
        Asset.user_id == current_user.user_id
    ).order_by(Asset.created_at.desc()).limit(limit).all()

    return [
        AssetSummaryResponse(
            asset_id=a.asset_id,
            name=a.name,
            asset_type=a.asset_type.value,
            description=a.description,
            created_at=a.created_at,
            run_id=a.agent_run_id
        )
        for a in assets
    ]
