"""
OAuth endpoints for third-party service integrations.

Handles OAuth2 authorization flows for services like Google (Gmail, etc.)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from config import settings
from database import get_db
from models import User, OAuthToken, OAuthProvider
from routers.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/oauth", tags=["oauth"])

# Google OAuth2 scopes for Gmail
# gmail.readonly allows full read access including search
# gmail.metadata is more limited and conflicts with search, so don't use both
GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.readonly",
]


# ============================================================================
# Response Models
# ============================================================================

class OAuthConnectionStatus(BaseModel):
    """Status of an OAuth connection."""
    provider: str
    connected: bool
    email: Optional[str] = None
    scopes: list[str] = []
    expires_at: Optional[datetime] = None


class OAuthConnections(BaseModel):
    """All OAuth connections for a user."""
    google: Optional[OAuthConnectionStatus] = None


# ============================================================================
# Helper Functions
# ============================================================================

def _get_google_flow(state: Optional[str] = None) -> Flow:
    """Create a Google OAuth2 flow."""
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )

    if state:
        flow.state = state

    return flow


def _get_user_email_from_google(credentials: Credentials) -> Optional[str]:
    """Get user's email from Google using the credentials."""
    try:
        service = build("oauth2", "v2", credentials=credentials)
        user_info = service.userinfo().get().execute()
        return user_info.get("email")
    except Exception as e:
        logger.error(f"Error getting user email from Google: {e}")
        return None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/connections", response_model=OAuthConnections)
async def get_oauth_connections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> OAuthConnections:
    """Get all OAuth connections for the current user."""
    connections = OAuthConnections()

    # Check Google connection
    google_token = db.query(OAuthToken).filter(
        OAuthToken.user_id == current_user.user_id,
        OAuthToken.provider == OAuthProvider.GOOGLE
    ).first()

    if google_token:
        connections.google = OAuthConnectionStatus(
            provider="google",
            connected=True,
            email=google_token.provider_data.get("email") if google_token.provider_data else None,
            scopes=google_token.scopes or [],
            expires_at=google_token.expires_at
        )
    else:
        connections.google = OAuthConnectionStatus(
            provider="google",
            connected=False
        )

    return connections


@router.get("/google/authorize")
async def google_authorize(
    current_user: User = Depends(get_current_user)
) -> dict:
    """
    Get the Google OAuth2 authorization URL.

    The frontend should redirect the user to this URL to initiate the OAuth flow.
    """
    flow = _get_google_flow()

    # Use user_id as state for security (will verify on callback)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # Force consent to get refresh token
        state=str(current_user.user_id)
    )

    return {
        "authorization_url": authorization_url,
        "state": state
    }


@router.get("/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Handle the Google OAuth2 callback.

    This endpoint receives the authorization code from Google and exchanges it for tokens.
    """
    try:
        # Parse user_id from state
        try:
            user_id = int(state)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        # Verify user exists
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="User not found")

        # Exchange code for tokens
        flow = _get_google_flow(state=state)
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user's email
        email = _get_user_email_from_google(credentials)

        # Calculate expiry
        expires_at = None
        if credentials.expiry:
            expires_at = credentials.expiry

        # Check if token already exists for this user/provider
        existing_token = db.query(OAuthToken).filter(
            OAuthToken.user_id == user_id,
            OAuthToken.provider == OAuthProvider.GOOGLE
        ).first()

        if existing_token:
            # Update existing token
            existing_token.access_token = credentials.token
            existing_token.refresh_token = credentials.refresh_token or existing_token.refresh_token
            existing_token.expires_at = expires_at
            existing_token.scopes = list(credentials.scopes) if credentials.scopes else GOOGLE_SCOPES
            existing_token.provider_data = {"email": email}
            existing_token.updated_at = datetime.utcnow()
        else:
            # Create new token
            new_token = OAuthToken(
                user_id=user_id,
                provider=OAuthProvider.GOOGLE,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                expires_at=expires_at,
                scopes=list(credentials.scopes) if credentials.scopes else GOOGLE_SCOPES,
                provider_data={"email": email}
            )
            db.add(new_token)

        db.commit()

        # Redirect to frontend with success
        redirect_url = f"{settings.FRONTEND_URL}/profile?oauth=success&provider=google"
        return RedirectResponse(url=redirect_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        redirect_url = f"{settings.FRONTEND_URL}/profile?oauth=error&message={str(e)}"
        return RedirectResponse(url=redirect_url)


@router.delete("/google/disconnect")
async def google_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    """Disconnect Google account (revoke and delete tokens)."""
    token = db.query(OAuthToken).filter(
        OAuthToken.user_id == current_user.user_id,
        OAuthToken.provider == OAuthProvider.GOOGLE
    ).first()

    if not token:
        raise HTTPException(status_code=404, detail="Google account not connected")

    # Try to revoke the token with Google
    try:
        import requests
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": token.access_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
    except Exception as e:
        logger.warning(f"Failed to revoke Google token: {e}")

    # Delete the token from our database
    db.delete(token)
    db.commit()

    return {"success": True, "message": "Google account disconnected"}
