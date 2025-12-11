"""
Memory Service

Handles CRUD operations for user memories and context retrieval.
Includes semantic search via embeddings.
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_
from datetime import datetime, timedelta
import logging

from models import Memory, MemoryType

logger = logging.getLogger(__name__)

# Similarity threshold for semantic search
SIMILARITY_THRESHOLD = 0.7


class MemoryService:
    """Service for managing user memories."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._embedding_service = None

    @property
    def embedding_service(self):
        """Lazy load embedding service."""
        if self._embedding_service is None:
            from services.embedding_service import get_embedding_service
            self._embedding_service = get_embedding_service()
        return self._embedding_service

    def create_memory(
        self,
        content: str,
        memory_type: MemoryType,
        category: Optional[str] = None,
        source_conversation_id: Optional[int] = None,
        is_pinned: bool = False,
        expires_at: Optional[datetime] = None,
        generate_embedding: bool = True
    ) -> Memory:
        """Create a new memory with optional embedding."""
        # For working memory, set default expiration if not provided
        if memory_type == MemoryType.WORKING and expires_at is None:
            expires_at = datetime.utcnow() + timedelta(hours=24)

        # Generate embedding for semantic search
        embedding = None
        if generate_embedding and memory_type != MemoryType.WORKING:
            try:
                embedding = self.embedding_service.get_embedding(content)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")

        memory = Memory(
            user_id=self.user_id,
            content=content,
            memory_type=memory_type,
            category=category,
            source_conversation_id=source_conversation_id,
            is_pinned=is_pinned,
            expires_at=expires_at,
            embedding=embedding,
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

    def search_memories(
        self,
        query: str,
        limit: int = 10,
        threshold: float = SIMILARITY_THRESHOLD,
        memory_type: Optional[MemoryType] = None
    ) -> List[Tuple[Memory, float]]:
        """
        Search memories using semantic similarity.
        Returns list of (memory, similarity_score) tuples.
        """
        try:
            query_embedding = self.embedding_service.get_embedding(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            # Fall back to keyword search
            return self._keyword_search(query, limit, memory_type)

        # Get all active memories with embeddings
        db_query = self.db.query(Memory).filter(
            Memory.user_id == self.user_id,
            Memory.is_active == True,
            Memory.embedding.isnot(None),
            or_(
                Memory.expires_at.is_(None),
                Memory.expires_at > datetime.utcnow()
            )
        )

        if memory_type:
            db_query = db_query.filter(Memory.memory_type == memory_type)

        memories = db_query.all()

        # Calculate similarities
        results = []
        for memory in memories:
            if memory.embedding:
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding, memory.embedding
                )
                if similarity >= threshold:
                    results.append((memory, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def _keyword_search(
        self,
        query: str,
        limit: int,
        memory_type: Optional[MemoryType] = None
    ) -> List[Tuple[Memory, float]]:
        """Fallback keyword search when embedding fails."""
        db_query = self.db.query(Memory).filter(
            Memory.user_id == self.user_id,
            Memory.is_active == True,
            Memory.content.ilike(f"%{query}%"),
            or_(
                Memory.expires_at.is_(None),
                Memory.expires_at > datetime.utcnow()
            )
        )

        if memory_type:
            db_query = db_query.filter(Memory.memory_type == memory_type)

        memories = db_query.limit(limit).all()
        # Return with fake similarity score of 0.8 for keyword matches
        return [(m, 0.8) for m in memories]

    def search_relevant_for_context(
        self,
        message: str,
        limit: int = 5,
        threshold: float = SIMILARITY_THRESHOLD
    ) -> List[Memory]:
        """
        Search for memories relevant to a user message.
        Used for automatic context injection.
        """
        results = self.search_memories(message, limit=limit, threshold=threshold)
        return [memory for memory, score in results]

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
            # Regenerate embedding if content changed
            if memory.memory_type != MemoryType.WORKING:
                try:
                    memory.embedding = self.embedding_service.get_embedding(content)
                except Exception as e:
                    logger.warning(f"Failed to regenerate embedding: {e}")

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

    def delete_by_content(self, content_substring: str) -> int:
        """Delete memories containing a substring. Returns count deleted."""
        count = self.db.query(Memory).filter(
            Memory.user_id == self.user_id,
            Memory.content.ilike(f"%{content_substring}%")
        ).delete(synchronize_session='fetch')
        self.db.commit()
        logger.info(f"Deleted {count} memories matching '{content_substring}'")
        return count

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
            source_conversation_id=source_conversation_id,
            generate_embedding=False  # Working memory doesn't need embeddings
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

    def format_for_prompt(self, include_relevant: Optional[str] = None) -> str:
        """
        Format memories for inclusion in system prompt.

        Args:
            include_relevant: If provided, also search for memories relevant to this text
        """
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

        # Add relevant memories from semantic search
        if include_relevant:
            relevant = self.search_relevant_for_context(include_relevant, limit=5)
            # Filter out memories already included
            included_ids = set()
            for category_memories in context_memories.values():
                for m in category_memories:
                    included_ids.add(m.memory_id)

            new_relevant = [m for m in relevant if m.memory_id not in included_ids]
            if new_relevant:
                parts.append("\n## Relevant Context")
                for m in new_relevant:
                    parts.append(f"- {m.content}")

        return "\n".join(parts) if parts else ""
