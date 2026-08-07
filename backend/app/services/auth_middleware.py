"""
Backward-compatibility stub for authentication middleware.
Re-exports from app.core.auth_middleware.
"""

from app.core.auth_middleware import (
    optional_auth,
    require_auth,
)

__all__ = ["require_auth", "optional_auth"]
