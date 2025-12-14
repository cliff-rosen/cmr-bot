"""
General chat domain types and payload types

Domain types: GeneralChatMessage, ActionMetadata, SuggestedValue, SuggestedAction, CustomPayload
Response payload type: ChatResponsePayload (structured final response)
Request/Response models (ChatRequest, ChatStreamChunk, ChatStatusResponse) are in routers/general_chat.py
"""

from pydantic import BaseModel
from typing import List, Optional, Any, Literal, Union


# ============================================================================
# Domain Types
# ============================================================================

class GeneralChatMessage(BaseModel):
    """Simple chat message for general chat API"""
    role: Literal["user", "assistant"]
    content: str
    timestamp: str


class SuggestedValue(BaseModel):
    """A suggested value that the user can select"""
    label: str
    value: str


class SuggestedAction(BaseModel):
    """A suggested action button"""
    label: str
    action: str
    handler: Literal["client", "server"]
    data: Optional[Any] = None
    style: Optional[Literal["primary", "secondary", "warning"]] = None


class CustomPayload(BaseModel):
    """Custom payload for specialized chat responses"""
    type: str
    data: Any


class ActionMetadata(BaseModel):
    """Metadata for action-based interactions"""
    action_identifier: str
    action_data: Optional[Any] = None



# ============================================================================
# Response Payload Type (structured final response data)
# ============================================================================

class ChatResponsePayload(BaseModel):
    """Structured payload for final chat responses"""
    message: str
    conversation_id: Optional[int] = None  # The conversation this message belongs to
    suggested_values: Optional[List[SuggestedValue]] = None
    suggested_actions: Optional[List[SuggestedAction]] = None
    custom_payload: Optional[CustomPayload] = None
    workspace_payload: Optional[Any] = None  # Direct workspace payload from tools (takes precedence over parsed message payloads)


# ============================================================================
# Stream Event Types (discriminated union with explicit 'type' field)
# ============================================================================

class TextDeltaEvent(BaseModel):
    """Streaming text token"""
    type: Literal["text_delta"] = "text_delta"
    text: str


class StatusEvent(BaseModel):
    """Status message (thinking, processing, etc.)"""
    type: Literal["status"] = "status"
    message: str


class ToolStartEvent(BaseModel):
    """Tool execution begins"""
    type: Literal["tool_start"] = "tool_start"
    tool: str
    input: Any
    tool_use_id: str


class ToolProgressEvent(BaseModel):
    """Tool execution progress update"""
    type: Literal["tool_progress"] = "tool_progress"
    tool: str
    stage: str
    message: str
    progress: float  # 0.0 to 1.0
    data: Optional[Any] = None


class ToolCompleteEvent(BaseModel):
    """Tool execution finished"""
    type: Literal["tool_complete"] = "tool_complete"
    tool: str
    index: int  # Index into tool_history


class CompleteEvent(BaseModel):
    """Final response with payload"""
    type: Literal["complete"] = "complete"
    payload: ChatResponsePayload


class ErrorEvent(BaseModel):
    """Error occurred"""
    type: Literal["error"] = "error"
    message: str


class CancelledEvent(BaseModel):
    """Request was cancelled"""
    type: Literal["cancelled"] = "cancelled"


# Union of all stream event types
StreamEvent = Union[
    TextDeltaEvent,
    StatusEvent,
    ToolStartEvent,
    ToolProgressEvent,
    ToolCompleteEvent,
    CompleteEvent,
    ErrorEvent,
    CancelledEvent
]
