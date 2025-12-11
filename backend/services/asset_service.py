"""
Asset Service

Handles CRUD operations for user assets and context management.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
import logging

from models import Asset, AssetType

logger = logging.getLogger(__name__)


class AssetService:
    """Service for managing user assets."""

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def create_asset(
        self,
        name: str,
        asset_type: AssetType,
        content: Optional[str] = None,
        file_path: Optional[str] = None,
        external_url: Optional[str] = None,
        mime_type: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source_conversation_id: Optional[int] = None,
        context_summary: Optional[str] = None
    ) -> Asset:
        """Create a new asset."""
        asset = Asset(
            user_id=self.user_id,
            name=name,
            asset_type=asset_type,
            content=content,
            file_path=file_path,
            external_url=external_url,
            mime_type=mime_type,
            description=description,
            tags=tags or [],
            source_conversation_id=source_conversation_id,
            context_summary=context_summary,
            is_in_context=False
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        logger.info(f"Created asset {asset.asset_id} '{name}' for user {self.user_id}")
        return asset

    def get_asset(self, asset_id: int) -> Optional[Asset]:
        """Get an asset by ID (must belong to user)."""
        return self.db.query(Asset).filter(
            Asset.asset_id == asset_id,
            Asset.user_id == self.user_id
        ).first()

    def list_assets(
        self,
        asset_type: Optional[AssetType] = None,
        in_context_only: bool = False,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Asset]:
        """List assets with filters."""
        query = self.db.query(Asset).filter(Asset.user_id == self.user_id)

        if asset_type:
            query = query.filter(Asset.asset_type == asset_type)

        if in_context_only:
            query = query.filter(Asset.is_in_context == True)

        # Note: JSON tag filtering would need database-specific syntax
        # For now, filter in Python if tags provided
        assets = query.order_by(desc(Asset.is_in_context), desc(Asset.updated_at)).offset(offset).limit(limit).all()

        if tags:
            assets = [a for a in assets if any(t in (a.tags or []) for t in tags)]

        return assets

    def update_asset(
        self,
        asset_id: int,
        name: Optional[str] = None,
        content: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        context_summary: Optional[str] = None
    ) -> Optional[Asset]:
        """Update an asset."""
        asset = self.get_asset(asset_id)
        if not asset:
            return None

        if name is not None:
            asset.name = name
        if content is not None:
            asset.content = content
        if description is not None:
            asset.description = description
        if tags is not None:
            asset.tags = tags
        if context_summary is not None:
            asset.context_summary = context_summary

        asset.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset."""
        asset = self.get_asset(asset_id)
        if not asset:
            return False

        self.db.delete(asset)
        self.db.commit()
        logger.info(f"Deleted asset {asset_id}")
        return True

    def toggle_context(self, asset_id: int) -> Optional[Asset]:
        """Toggle asset's is_in_context status."""
        asset = self.get_asset(asset_id)
        if not asset:
            return None

        asset.is_in_context = not asset.is_in_context
        asset.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def add_to_context(self, asset_id: int) -> Optional[Asset]:
        """Add asset to active context."""
        asset = self.get_asset(asset_id)
        if not asset:
            return None

        asset.is_in_context = True
        asset.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def remove_from_context(self, asset_id: int) -> Optional[Asset]:
        """Remove asset from active context."""
        asset = self.get_asset(asset_id)
        if not asset:
            return None

        asset.is_in_context = False
        asset.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_context_assets(self) -> List[Asset]:
        """Get all assets currently in context."""
        return self.list_assets(in_context_only=True)

    def clear_context(self) -> int:
        """Remove all assets from context."""
        count = self.db.query(Asset).filter(
            Asset.user_id == self.user_id,
            Asset.is_in_context == True
        ).update({"is_in_context": False})
        self.db.commit()
        logger.info(f"Cleared {count} assets from context for user {self.user_id}")
        return count

    def format_for_prompt(self) -> str:
        """Format assets for inclusion in system prompt."""
        assets = self.get_context_assets()
        if not assets:
            return ""

        parts = ["## Active Assets"]
        for asset in assets:
            parts.append(f"\n### {asset.name} ({asset.asset_type.value})")
            if asset.description:
                parts.append(f"Description: {asset.description}")
            if asset.context_summary:
                parts.append(f"Summary: {asset.context_summary}")
            elif asset.content and len(asset.content) < 2000:
                parts.append(f"Content:\n```\n{asset.content}\n```")
            elif asset.external_url:
                parts.append(f"URL: {asset.external_url}")

        return "\n".join(parts)
