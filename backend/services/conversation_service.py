"""
Conversation Service

Handles CRUD operations for conversations and messages.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
import logging

from models import Conversation, Message

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and messages."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def create_conversation(self, title: Optional[str] = None) -> Conversation:
        """Create a new conversation."""
        conversation = Conversation(
            user_id=self.user_id,
            title=title
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        logger.info(f"Created conversation {conversation.conversation_id} for user {self.user_id}")
        return conversation

    def get_conversation(self, conversation_id: int) -> Optional[Conversation]:
        """Get a conversation by ID (must belong to user)."""
        return self.db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id,
            Conversation.user_id == self.user_id
        ).first()

    def list_conversations(
        self,
        limit: int = 20,
        offset: int = 0,
        include_archived: bool = False
    ) -> List[Conversation]:
        """List conversations for the user, most recent first."""
        query = self.db.query(Conversation).filter(
            Conversation.user_id == self.user_id
        )

        if not include_archived:
            query = query.filter(Conversation.is_archived == False)

        return query.order_by(desc(Conversation.updated_at)).offset(offset).limit(limit).all()

    def update_conversation(
        self,
        conversation_id: int,
        title: Optional[str] = None,
        is_archived: Optional[bool] = None
    ) -> Optional[Conversation]:
        """Update a conversation."""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        if title is not None:
            conversation.title = title
        if is_archived is not None:
            conversation.is_archived = is_archived

        conversation.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def delete_conversation(self, conversation_id: int) -> bool:
        """Delete a conversation and all its messages."""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return False

        self.db.delete(conversation)
        self.db.commit()
        logger.info(f"Deleted conversation {conversation_id}")
        return True

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        suggested_values: Optional[List[Dict[str, Any]]] = None,
        suggested_actions: Optional[List[Dict[str, Any]]] = None,
        custom_payload: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """Add a message to a conversation."""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            suggested_values=suggested_values,
            suggested_actions=suggested_actions,
            custom_payload=custom_payload
        )
        self.db.add(message)

        # Update conversation's updated_at
        conversation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(message)
        return message

    def get_messages(
        self,
        conversation_id: int,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Get messages for a conversation, oldest first."""
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []

        return self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at).offset(offset).limit(limit).all()

    def generate_title(self, conversation_id: int) -> Optional[str]:
        """Generate a title from the first user message."""
        messages = self.get_messages(conversation_id, limit=1)
        if not messages:
            return None

        first_message = messages[0]
        if first_message.role != 'user':
            return None

        # Take first 50 chars of the first message as title
        content = first_message.content.strip()
        if len(content) > 50:
            title = content[:47] + "..."
        else:
            title = content

        return title

    def auto_title_if_needed(self, conversation_id: int) -> Optional[Conversation]:
        """Auto-generate title if conversation has no title."""
        conversation = self.get_conversation(conversation_id)
        if not conversation or conversation.title:
            return conversation

        title = self.generate_title(conversation_id)
        if title:
            return self.update_conversation(conversation_id, title=title)

        return conversation
