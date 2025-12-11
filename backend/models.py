"""
CMR-Bot Database Models

Simplified models for the personal AI agent system.
Core entities: Users, Profiles, Conversations, Messages, Memories, Assets
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, JSON, Enum, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum


class MemoryType(str, PyEnum):
    """Types of memory entries"""
    WORKING = "working"      # Session-scoped, auto-expires
    FACT = "fact"            # Persistent knowledge about user
    PREFERENCE = "preference" # User preferences
    ENTITY = "entity"        # People, projects, systems
    PROJECT = "project"      # Active project context


class AssetType(str, PyEnum):
    """Types of assets"""
    FILE = "file"
    DOCUMENT = "document"
    DATA = "data"
    CODE = "code"
    LINK = "link"

Base = declarative_base()


class UserRole(str, PyEnum):
    """User privilege levels"""
    ADMIN = "admin"
    USER = "user"


class User(Base):
    """User authentication and basic information"""
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True)
    password = Column(String(255))
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(Enum(UserRole, name='userrole'), default=UserRole.USER, nullable=False)
    login_token = Column(String(255), nullable=True, index=True)  # One-time login token
    login_token_expires = Column(DateTime, nullable=True)  # Token expiration time
    registration_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False)


class UserProfile(Base):
    """User profile and preferences"""
    __tablename__ = "user_profiles"

    profile_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True)

    # Basic info
    display_name = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)

    # Preferences stored as JSON for flexibility
    preferences = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="profile")


class Conversation(Base):
    """Chat conversation container"""
    __tablename__ = "conversations"

    conversation_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    title = Column(String(255), nullable=True)  # Auto-generated or user-set
    is_archived = Column(Boolean, default=False)
    extra_data = Column(JSON, default=dict)  # Flexible storage for future needs
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Individual chat message"""
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user' or 'assistant'
    content = Column(Text, nullable=False)

    # Tool usage tracking
    tool_calls = Column(JSON, nullable=True)  # Array of {tool_name, input, output}

    # Rich response data (for assistant messages)
    suggested_values = Column(JSON, nullable=True)
    suggested_actions = Column(JSON, nullable=True)
    custom_payload = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class Memory(Base):
    """User memory for context enhancement"""
    __tablename__ = "memories"

    memory_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)

    # Classification
    memory_type = Column(Enum(MemoryType, name='memorytype'), nullable=False)
    category = Column(String(100), nullable=True)  # e.g., "work", "personal"

    # Content
    content = Column(Text, nullable=False)
    source_conversation_id = Column(Integer, ForeignKey("conversations.conversation_id", ondelete="SET NULL"), nullable=True)

    # Temporal
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # For working memory auto-cleanup
    last_accessed_at = Column(DateTime, nullable=True)
    access_count = Column(Integer, default=0)

    # Control
    is_active = Column(Boolean, default=True)  # Include in context
    is_pinned = Column(Boolean, default=False)  # Always include
    confidence = Column(Float, default=1.0)  # For auto-extracted memories

    # Relationships
    user = relationship("User")
    source_conversation = relationship("Conversation")


class Asset(Base):
    """User assets for context enhancement"""
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)

    # Identity
    name = Column(String(255), nullable=False)
    asset_type = Column(Enum(AssetType, name='assettype'), nullable=False)
    mime_type = Column(String(100), nullable=True)

    # Content (choose based on size/type)
    content = Column(Text, nullable=True)  # For small text content
    file_path = Column(String(500), nullable=True)  # For file storage reference
    external_url = Column(String(500), nullable=True)  # For links

    # Metadata
    description = Column(Text, nullable=True)
    tags = Column(JSON, default=list)  # Array of tags for filtering
    extra_data = Column(JSON, default=dict)  # Flexible extra data

    # Context control
    is_in_context = Column(Boolean, default=False)  # Currently active in context
    context_summary = Column(Text, nullable=True)  # Compressed version for context

    # Source tracking
    source_conversation_id = Column(Integer, ForeignKey("conversations.conversation_id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User")
    source_conversation = relationship("Conversation")
