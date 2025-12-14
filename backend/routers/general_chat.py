"""
General-purpose chat endpoint
"""

import asyncio
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Literal
import logging

from database import get_db
from models import User
from routers.auth import get_current_user
from schemas.general_chat import (
    ActionMetadata,
    ChatResponsePayload,
    StreamEvent,
    TextDeltaEvent,
    StatusEvent,
    ToolStartEvent,
    ToolProgressEvent,
    ToolCompleteEvent,
    CompleteEvent,
    ErrorEvent,
    CancelledEvent,
)
from services.general_chat_service import GeneralChatService, CancellationToken

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Request model for general chat endpoint"""
    message: str
    conversation_id: Optional[int] = None  # If None, creates new conversation
    context: Dict[str, Any] = {}
    interaction_type: Literal["text_input", "value_selected", "action_executed"] = "text_input"
    action_metadata: Optional[ActionMetadata] = None
    enabled_tools: Optional[List[str]] = None  # List of tool IDs to enable (None = all tools)
    include_profile: bool = True  # Whether to include user profile in context


@router.post("/stream",
    response_class=EventSourceResponse,
    responses={
        200: {
            "description": "Server-Sent Events stream of chat responses",
            "content": {
                "text/event-stream": {
                    "schema": {
                        "oneOf": [
                            TextDeltaEvent.model_json_schema(),
                            StatusEvent.model_json_schema(),
                            ToolStartEvent.model_json_schema(),
                            ToolProgressEvent.model_json_schema(),
                            ToolCompleteEvent.model_json_schema(),
                            CompleteEvent.model_json_schema(),
                            ErrorEvent.model_json_schema(),
                            CancelledEvent.model_json_schema(),
                        ]
                    }
                }
            }
        }
    },
    summary="Stream chat responses",
    description="Streams chat responses in real-time using Server-Sent Events"
)
async def chat_stream(
    chat_request: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> EventSourceResponse:
    """
    General purpose chat streaming endpoint.

    Accepts user message with context and streams:
    - Token-by-token response
    - Final structured response with suggested values/actions
    """
    # Create cancellation token that monitors client disconnection
    cancellation_token = CancellationToken()

    async def monitor_disconnect():
        """Monitor for client disconnection and cancel the token"""
        while not cancellation_token.is_cancelled:
            if await request.is_disconnected():
                logger.info("Client disconnected, cancelling request")
                cancellation_token.cancel()
                break
            await asyncio.sleep(0.5)  # Check every 500ms

    async def event_generator():
        """Generate SSE events"""
        # Start disconnect monitor as background task
        monitor_task = asyncio.create_task(monitor_disconnect())

        try:
            service = GeneralChatService(db, current_user.user_id)

            # Stream the response from the service with cancellation support
            async for chunk in service.stream_chat_message(chat_request, cancellation_token):
                if cancellation_token.is_cancelled:
                    logger.info("Request cancelled, stopping stream")
                    break
                # Yield as SSE event
                yield {
                    "event": "message",
                    "data": chunk
                }

        except asyncio.CancelledError:
            logger.info("Chat stream cancelled")
        except Exception as e:
            logger.error(f"Error in chat stream: {str(e)}")
            yield {
                "event": "message",
                "data": ErrorEvent(message=str(e)).model_dump_json()
            }
        finally:
            # Clean up: cancel the monitor and mark token as cancelled
            cancellation_token.cancel()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass

    return EventSourceResponse(
        event_generator(),
        ping=1,  # Send ping every 1 second to keep connection alive
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
