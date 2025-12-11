"""
Memory Service

Handles CRUD operations for user memories and context retrieval.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from datetime import datetime, timedelta
import logging

from models import Memory, MemoryType

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for managing user memories."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def create_memory(
        self,
        content: str,
        memory_type: MemoryType,
        category: Optional[str] = None,
        source_conversation_id: Optional[int] = None,
        is_pinned: bool = False,
        expires_at: Optional[datetime] = None
    ) -> Memory:
        """Create a new memory."""
        # For working memory, set default expiration if not provided
        if memory_type == MemoryType.WORKING and expires_at is None:
            expires_at = datetime.utcnow() + timedelta(hours=24)

        memory = Memory(
            user_id=self.user_id,
            content=content,
            memory_type=memory_type,
            category=category,
            source_conversation_id=source_conversation_id,
            is_pinned=is_pinned,
            expires_at=expires_at,
            is_active=True
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        logger.info(f"Created {memory_type.value} memory {memory.memory_id} for user {self.user_id}")
        return memory

    def get_memory(self, memory_id: int) -> Optional[Memory]:
        """Get a memory by ID (must belong to user)."""
        return self.db.query(Memory).filter(
            Memory.memory_id == memory_id,
            Memory.user_id == self.user_id
        ).first()

    def list_memories(
        self,
        memory_type: Optional[MemoryType] = None,
        category: Optional[str] = None,
        active_only: bool = True,
        include_expired: bool = False,
        limit: int = 100,
        offset: int = 0
    ) -> List[Memory]:
        """List memories with filters."""
        query = self.db.query(Memory).filter(Memory.user_id == self.user_id)

        if memory_type:
            query = query.filter(Memory.memory_type == memory_type)

        if category:
            query = query.filter(Memory.category == category)

        if active_only:
            query = query.filter(Memory.is_active == True)

        if not include_expired:
            query = query.filter(
                or_(
                    Memory.expires_at.is_(None),
                    Memory.expires_at > datetime.utcnow()
                )
            )

        return query.order_by(desc(Memory.is_pinned), desc(Memory.created_at)).offset(offset).limit(limit).all()

    def update_memory(
        self,
        memory_id: int,
        content: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_pinned: Optional[bool] = None
    ) -> Optional[Memory]:
        """Update a memory."""
        memory = self.get_memory(memory_id)
        if not memory:
            return None

        if content is not None:
            memory.content = content
        if category is not None:
            memory.category = category
        if is_active is not None:
            memory.is_active = is_active
        if is_pinned is not None:
            memory.is_pinned = is_pinned

        self.db.commit()
        self.db.refresh(memory)
        return memory

    def delete_memory(self, memory_id: int) -> bool:
        """Delete a memory."""
        memory = self.get_memory(memory_id)
        if not memory:
            return False

        self.db.delete(memory)
        self.db.commit()
        logger.info(f"Deleted memory {memory_id}")
        return True

    def toggle_active(self, memory_id: int) -> Optional[Memory]:
        """Toggle memory's is_active status."""
        memory = self.get_memory(memory_id)
        if not memory:
            return None

        memory.is_active = not memory.is_active
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def toggle_pinned(self, memory_id: int) -> Optional[Memory]:
        """Toggle memory's is_pinned status."""
        memory = self.get_memory(memory_id)
        if not memory:
            return None

        memory.is_pinned = not memory.is_pinned
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def get_context_memories(self) -> Dict[str, List[Memory]]:
        """Get memories organized for context injection."""
        # Clean up expired working memories first
        self._cleanup_expired()

        result = {
            "pinned": [],
            "working": [],
            "facts": [],
            "preferences": [],
            "entities": [],
            "projects": []
        }

        memories = self.list_memories(active_only=True)

        for memory in memories:
            if memory.is_pinned:
                result["pinned"].append(memory)
            elif memory.memory_type == MemoryType.WORKING:
                result["working"].append(memory)
            elif memory.memory_type == MemoryType.FACT:
                result["facts"].append(memory)
            elif memory.memory_type == MemoryType.PREFERENCE:
                result["preferences"].append(memory)
            elif memory.memory_type == MemoryType.ENTITY:
                result["entities"].append(memory)
            elif memory.memory_type == MemoryType.PROJECT:
                result["projects"].append(memory)

            # Update access tracking
            memory.last_accessed_at = datetime.utcnow()
            memory.access_count += 1

        self.db.commit()
        return result

    def add_working_memory(self, content: str, source_conversation_id: Optional[int] = None) -> Memory:
        """Convenience method to add working memory."""
        return self.create_memory(
            content=content,
            memory_type=MemoryType.WORKING,
            source_conversation_id=source_conversation_id
        )

    def clear_working_memory(self) -> int:
        """Clear all working memories for the user."""
        count = self.db.query(Memory).filter(
            Memory.user_id == self.user_id,
            Memory.memory_type == MemoryType.WORKING
        ).delete()
        self.db.commit()
        logger.info(f"Cleared {count} working memories for user {self.user_id}")
        return count

    def _cleanup_expired(self) -> int:
        """Remove expired memories."""
        count = self.db.query(Memory).filter(
            Memory.user_id == self.user_id,
            Memory.expires_at.isnot(None),
            Memory.expires_at < datetime.utcnow()
        ).delete()
        if count > 0:
            self.db.commit()
            logger.info(f"Cleaned up {count} expired memories for user {self.user_id}")
        return count

    def format_for_prompt(self) -> str:
        """Format memories for inclusion in system prompt."""
        context_memories = self.get_context_memories()
        parts = []

        # Pinned memories (highest priority)
        if context_memories["pinned"]:
            parts.append("## Key Information (Pinned)")
            for m in context_memories["pinned"]:
                parts.append(f"- {m.content}")

        # Working memory (current session)
        if context_memories["working"]:
            parts.append("\n## Current Session Notes")
            for m in context_memories["working"]:
                parts.append(f"- {m.content}")

        # User facts and preferences
        facts_prefs = context_memories["facts"] + context_memories["preferences"]
        if facts_prefs:
            parts.append("\n## About the User")
            for m in facts_prefs:
                parts.append(f"- {m.content}")

        # Entities and projects
        entities_projects = context_memories["entities"] + context_memories["projects"]
        if entities_projects:
            parts.append("\n## Known Entities & Projects")
            for m in entities_projects:
                parts.append(f"- {m.content}")

        return "\n".join(parts) if parts else ""
