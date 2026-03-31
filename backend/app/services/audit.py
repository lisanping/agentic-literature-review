"""Audit logging service — best-effort, non-blocking — v0.4."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = structlog.stdlib.get_logger()


async def log_action(
    db: AsyncSession,
    *,
    action: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Record an audit log entry. Best-effort: failures are logged but not raised."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.flush()
    except Exception:
        logger.warning(
            "audit.log_failed",
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            exc_info=True,
        )
