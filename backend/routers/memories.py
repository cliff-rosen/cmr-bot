"""
Memories API Router

Endpoints for managing user memories.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

from database import get_db
from models import User, MemoryType
from routers.auth import get_current_user
from services.memory_service import MemoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memories", tags=["memories"])


# =============================================================================
# Request/Response Models
# =============================================================================

class MemoryCreate(BaseModel):
    content: str
    memory_type: str  # 'working', 'fact', 'preference', 'entity', 'project'
    category: Optional[str] = None
    is_pinned: bool = False
    source_conversation_id: Optional[int] = None


class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    is_pinned: Optional[bool] = None


class MemoryResponse(BaseModel):
    memory_id: int
    user_id: int
    memory_type: str
    category: Optional[str]
    content: str
    source_conversation_id: Optional[int]
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    is_pinned: bool
    confidence: float

    class Config:
        from_attributes = True


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=List[MemoryResponse])
async def list_memories(
    memory_type: Optional[str] = None,
    category: Optional[str] = None,
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's memories with optional filters."""
    service = MemoryService(db, current_user.user_id)

    # Convert string to enum if provided
    mem_type = None
    if memory_type:
        try:
            mem_type = MemoryType(memory_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid memory_type: {memory_type}")

    memories = service.list_memories(
        memory_type=mem_type,
        category=category,
        active_only=active_only,
        limit=limit,
        offset=offset
    )

    return [
        MemoryResponse(
            memory_id=m.memory_id,
            user_id=m.user_id,
            memory_type=m.memory_type.value,
            category=m.category,
            content=m.content,
            source_conversation_id=m.source_conversation_id,
            created_at=m.created_at,
            expires_at=m.expires_at,
            is_active=m.is_active,
            is_pinned=m.is_pinned,
            confidence=m.confidence
        )
        for m in memories
    ]


@router.post("", response_model=MemoryResponse)
async def create_memory(
    request: MemoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new memory."""
    service = MemoryService(db, current_user.user_id)

    try:
        mem_type = MemoryType(request.memory_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid memory_type: {request.memory_type}")

    memory = service.create_memory(
        content=request.content,
        memory_type=mem_type,
        category=request.category,
        is_pinned=request.is_pinned,
        source_conversation_id=request.source_conversation_id
    )

    return MemoryResponse(
        memory_id=memory.memory_id,
        user_id=memory.user_id,
        memory_type=memory.memory_type.value,
        category=memory.category,
        content=memory.content,
        source_conversation_id=memory.source_conversation_id,
        created_at=memory.created_at,
        expires_at=memory.expires_at,
        is_active=memory.is_active,
        is_pinned=memory.is_pinned,
        confidence=memory.confidence
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific memory."""
    service = MemoryService(db, current_user.user_id)
    memory = service.get_memory(memory_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryResponse(
        memory_id=memory.memory_id,
        user_id=memory.user_id,
        memory_type=memory.memory_type.value,
        category=memory.category,
        content=memory.content,
        source_conversation_id=memory.source_conversation_id,
        created_at=memory.created_at,
        expires_at=memory.expires_at,
        is_active=memory.is_active,
        is_pinned=memory.is_pinned,
        confidence=memory.confidence
    )


@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    request: MemoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a memory."""
    service = MemoryService(db, current_user.user_id)
    memory = service.update_memory(
        memory_id=memory_id,
        content=request.content,
        category=request.category,
        is_active=request.is_active,
        is_pinned=request.is_pinned
    )

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return MemoryResponse(
        memory_id=memory.memory_id,
        user_id=memory.user_id,
        memory_type=memory.memory_type.value,
        category=memory.category,
        content=memory.content,
        source_conversation_id=memory.source_conversation_id,
        created_at=memory.created_at,
        expires_at=memory.expires_at,
        is_active=memory.is_active,
        is_pinned=memory.is_pinned,
        confidence=memory.confidence
    )


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a memory."""
    service = MemoryService(db, current_user.user_id)
    success = service.delete_memory(memory_id)

    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"status": "deleted", "memory_id": memory_id}


@router.post("/{memory_id}/toggle")
async def toggle_memory_active(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Toggle memory's active status."""
    service = MemoryService(db, current_user.user_id)
    memory = service.toggle_active(memory_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"memory_id": memory_id, "is_active": memory.is_active}


@router.post("/{memory_id}/pin")
async def toggle_memory_pinned(
    memory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Toggle memory's pinned status."""
    service = MemoryService(db, current_user.user_id)
    memory = service.toggle_pinned(memory_id)

    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")

    return {"memory_id": memory_id, "is_pinned": memory.is_pinned}


@router.delete("/working/clear")
async def clear_working_memory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Clear all working memories."""
    service = MemoryService(db, current_user.user_id)
    count = service.clear_working_memory()
    return {"status": "cleared", "count": count}
