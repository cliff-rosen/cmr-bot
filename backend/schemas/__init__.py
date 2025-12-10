"""
Schemas package for CMR-Bot API
"""

from .auth import (
    UserBase,
    UserCreate,
    UserResponse,
    Token,
    TokenData
)

__all__ = [
    # Auth schemas
    'UserBase',
    'UserCreate',
    'UserResponse',
    'Token',
    'TokenData',
]
