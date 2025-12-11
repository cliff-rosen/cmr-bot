"""
Assets API Router

Endpoints for managing user assets.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

from database import get_db
from models import User, AssetType
from routers.auth import get_current_user
from services.asset_service import AssetService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/assets", tags=["assets"])


# =============================================================================
# Request/Response Models
# =============================================================================

class AssetCreate(BaseModel):
    name: str
    asset_type: str  # 'file', 'document', 'data', 'code', 'link'
    content: Optional[str] = None
    external_url: Optional[str] = None
    mime_type: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    context_summary: Optional[str] = None
    source_conversation_id: Optional[int] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    context_summary: Optional[str] = None


class AssetResponse(BaseModel):
    asset_id: int
    user_id: int
    name: str
    asset_type: str
    mime_type: Optional[str]
    content: Optional[str]
    external_url: Optional[str]
    description: Optional[str]
    tags: List[str]
    is_in_context: bool
    context_summary: Optional[str]
    source_conversation_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=List[AssetResponse])
async def list_assets(
    asset_type: Optional[str] = None,
    in_context_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's assets with optional filters."""
    service = AssetService(db, current_user.user_id)

    # Convert string to enum if provided
    a_type = None
    if asset_type:
        try:
            a_type = AssetType(asset_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid asset_type: {asset_type}")

    assets = service.list_assets(
        asset_type=a_type,
        in_context_only=in_context_only,
        limit=limit,
        offset=offset
    )

    return [
        AssetResponse(
            asset_id=a.asset_id,
            user_id=a.user_id,
            name=a.name,
            asset_type=a.asset_type.value,
            mime_type=a.mime_type,
            content=a.content,
            external_url=a.external_url,
            description=a.description,
            tags=a.tags or [],
            is_in_context=a.is_in_context,
            context_summary=a.context_summary,
            source_conversation_id=a.source_conversation_id,
            created_at=a.created_at,
            updated_at=a.updated_at
        )
        for a in assets
    ]


@router.post("", response_model=AssetResponse)
async def create_asset(
    request: AssetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new asset."""
    service = AssetService(db, current_user.user_id)

    try:
        a_type = AssetType(request.asset_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid asset_type: {request.asset_type}")

    asset = service.create_asset(
        name=request.name,
        asset_type=a_type,
        content=request.content,
        external_url=request.external_url,
        mime_type=request.mime_type,
        description=request.description,
        tags=request.tags,
        context_summary=request.context_summary,
        source_conversation_id=request.source_conversation_id
    )

    return AssetResponse(
        asset_id=asset.asset_id,
        user_id=asset.user_id,
        name=asset.name,
        asset_type=asset.asset_type.value,
        mime_type=asset.mime_type,
        content=asset.content,
        external_url=asset.external_url,
        description=asset.description,
        tags=asset.tags or [],
        is_in_context=asset.is_in_context,
        context_summary=asset.context_summary,
        source_conversation_id=asset.source_conversation_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific asset."""
    service = AssetService(db, current_user.user_id)
    asset = service.get_asset(asset_id)

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return AssetResponse(
        asset_id=asset.asset_id,
        user_id=asset.user_id,
        name=asset.name,
        asset_type=asset.asset_type.value,
        mime_type=asset.mime_type,
        content=asset.content,
        external_url=asset.external_url,
        description=asset.description,
        tags=asset.tags or [],
        is_in_context=asset.is_in_context,
        context_summary=asset.context_summary,
        source_conversation_id=asset.source_conversation_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: int,
    request: AssetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an asset."""
    service = AssetService(db, current_user.user_id)
    asset = service.update_asset(
        asset_id=asset_id,
        name=request.name,
        content=request.content,
        description=request.description,
        tags=request.tags,
        context_summary=request.context_summary
    )

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return AssetResponse(
        asset_id=asset.asset_id,
        user_id=asset.user_id,
        name=asset.name,
        asset_type=asset.asset_type.value,
        mime_type=asset.mime_type,
        content=asset.content,
        external_url=asset.external_url,
        description=asset.description,
        tags=asset.tags or [],
        is_in_context=asset.is_in_context,
        context_summary=asset.context_summary,
        source_conversation_id=asset.source_conversation_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at
    )


@router.delete("/{asset_id}")
async def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an asset."""
    service = AssetService(db, current_user.user_id)
    success = service.delete_asset(asset_id)

    if not success:
        raise HTTPException(status_code=404, detail="Asset not found")

    return {"status": "deleted", "asset_id": asset_id}


@router.post("/{asset_id}/context")
async def toggle_asset_context(
    asset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Toggle asset's in-context status."""
    service = AssetService(db, current_user.user_id)
    asset = service.toggle_context(asset_id)

    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    return {"asset_id": asset_id, "is_in_context": asset.is_in_context}


@router.delete("/context/clear")
async def clear_context(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Remove all assets from context."""
    service = AssetService(db, current_user.user_id)
    count = service.clear_context()
    return {"status": "cleared", "count": count}
