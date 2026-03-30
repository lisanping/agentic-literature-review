"""SQLAlchemy async engine, session factory, and declarative Base.

This module will be fully populated in Phase 2 (data layer).
For now it provides the Base class needed by the test infrastructure.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass
