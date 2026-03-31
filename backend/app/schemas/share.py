"""Project sharing Pydantic schemas — v0.4."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class ProjectShareCreate(BaseModel):
    """Request to share a project with another user."""

    email: EmailStr
    permission: Literal["viewer", "collaborator"] = "viewer"


class ProjectShareUpdate(BaseModel):
    """Request to update share permission."""

    permission: Literal["viewer", "collaborator"]


class ProjectShareResponse(BaseModel):
    """Share record in API responses."""

    id: str
    project_id: str
    user_id: str
    username: str
    email: str
    permission: str
    created_at: datetime

    model_config = {"from_attributes": True}
