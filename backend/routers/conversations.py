"""
Conversations API Router

Endpoints for managing conversations and retrieving messages.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
import logging

from database import get_db
from models import User
from routers.auth import get_current_user
from services.conversation_service import ConversationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# =============================================================================
# Request/Response Models
# =============================================================================

class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_archived: Optional[bool] = None


class MessageResponse(BaseModel):
    message_id: int
    conversation_id: int
    role: str
    content: str
    tool_calls: Optional[List[Any]] = None
    suggested_values: Optional[List[Any]] = None
    suggested_actions: Optional[List[Any]] = None
    custom_payload: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    conversation_id: int
    user_id: int
    title: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = None

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationResponse):
    messages: List[MessageResponse] = []


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = 20,
    offset: int = 0,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's conversations, most recent first."""
    service = ConversationService(db, current_user.user_id)
    conversations = service.list_conversations(limit, offset, include_archived)

    # Add message count to each conversation
    result = []
    for conv in conversations:
        conv_dict = {
            "conversation_id": conv.conversation_id,
            "user_id": conv.user_id,
            "title": conv.title,
            "is_archived": conv.is_archived,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": len(conv.messages)
        }
        result.append(conv_dict)

    return result


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new conversation."""
    service = ConversationService(db, current_user.user_id)
    conversation = service.create_conversation(request.title)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific conversation with its messages."""
    service = ConversationService(db, current_user.user_id)
    conversation = service.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = service.get_messages(conversation_id)

    return {
        "conversation_id": conversation.conversation_id,
        "user_id": conversation.user_id,
        "title": conversation.title,
        "is_archived": conversation.is_archived,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": messages
    }


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    request: ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a conversation (title, archive status)."""
    service = ConversationService(db, current_user.user_id)
    conversation = service.update_conversation(
        conversation_id,
        title=request.title,
        is_archived=request.is_archived
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a conversation and all its messages."""
    service = ConversationService(db, current_user.user_id)
    success = service.delete_conversation(conversation_id)

    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"status": "deleted", "conversation_id": conversation_id}


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: int,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get messages for a conversation."""
    service = ConversationService(db, current_user.user_id)
    conversation = service.get_conversation(conversation_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return service.get_messages(conversation_id, limit, offset)
