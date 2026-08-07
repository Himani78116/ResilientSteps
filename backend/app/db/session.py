"""
Backward-compatibility stub for database session.
Re-exports from app.core.database.
"""

from app.core.database import (
    DATABASE_URL,
    AsyncSessionLocal,
    engine,
    get_db,
)

__all__ = ["DATABASE_URL", "AsyncSessionLocal", "engine", "get_db"]
