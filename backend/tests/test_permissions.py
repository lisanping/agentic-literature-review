"""Unit tests for v0.4 permissions — project isolation, sharing, RBAC, audit log."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.project import Project
from app.models.project_share import ProjectShare
from app.models.user import User
from app.services.auth import hash_password


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════


async def _register(client: AsyncClient, email: str, username: str = "user") -> dict:
    """Register a user and return token response."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "password": "test-password-123",
    })
    assert resp.status_code == 201
    return resp.json()


def _auth(tokens: dict) -> dict:
    """Build Authorization header."""
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _create_project(client: AsyncClient, tokens: dict, query: str = "test query") -> dict:
    """Create a project and return response."""
    resp = await client.post(
        "/api/v1/projects",
        json={"user_query": query},
        headers=_auth(tokens),
    )
    assert resp.status_code == 201
    return resp.json()


# ═══════════════════════════════════════════════════
# Project isolation
# ═══════════════════════════════════════════════════


class TestProjectIsolation:
    @pytest.mark.asyncio
    async def test_user_sees_only_own_projects(self, client: AsyncClient):
        """User A should not see User B's projects."""
        user_a = await _register(client, "a@test.com", "user-a")
        user_b = await _register(client, "b@test.com", "user-b")

        await _create_project(client, user_a, "User A project")
        await _create_project(client, user_b, "User B project")

        # User A lists projects — should see only their own
        resp = await client.get("/api/v1/projects", headers=_auth(user_a))
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["user_query"] == "User A project"

        # User B lists projects — should see only their own
        resp = await client.get("/api/v1/projects", headers=_auth(user_b))
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["user_query"] == "User B project"

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_project(self, client: AsyncClient):
        """User A cannot view/edit/delete User B's project."""
        user_a = await _register(client, "iso-a@test.com", "user-a")
        user_b = await _register(client, "iso-b@test.com", "user-b")

        project_b = await _create_project(client, user_b, "B's project")
        pid = project_b["id"]

        # User A tries to access User B's project
        resp = await client.get(f"/api/v1/projects/{pid}", headers=_auth(user_a))
        assert resp.status_code == 403

        resp = await client.patch(
            f"/api/v1/projects/{pid}",
            json={"token_budget": 999},
            headers=_auth(user_a),
        )
        assert resp.status_code == 403

        resp = await client.delete(f"/api/v1/projects/{pid}", headers=_auth(user_a))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_create_project_assigns_user_id(self, client: AsyncClient, db_session: AsyncSession):
        """Project.user_id should be set to current user."""
        tokens = await _register(client, "owner@test.com", "owner")
        project = await _create_project(client, tokens, "owner's project")

        result = await db_session.execute(
            select(Project).where(Project.id == project["id"])
        )
        p = result.scalar_one()
        # user_id should be set
        assert p.user_id is not None


# ═══════════════════════════════════════════════════
# Project sharing
# ═══════════════════════════════════════════════════


class TestProjectSharing:
    @pytest.mark.asyncio
    async def test_share_project_viewer(self, client: AsyncClient):
        """Owner can share a project as viewer."""
        owner = await _register(client, "share-owner@test.com", "owner")
        viewer = await _register(client, "share-viewer@test.com", "viewer")

        project = await _create_project(client, owner, "shared project")
        pid = project["id"]

        # Share
        resp = await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "share-viewer@test.com", "permission": "viewer"},
            headers=_auth(owner),
        )
        assert resp.status_code == 201
        share = resp.json()
        assert share["permission"] == "viewer"
        assert share["email"] == "share-viewer@test.com"

        # Viewer can now access the project
        resp = await client.get(f"/api/v1/projects/{pid}", headers=_auth(viewer))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_shared_project_in_list(self, client: AsyncClient):
        """Shared projects appear in the recipient's project list."""
        owner = await _register(client, "list-owner@test.com", "owner")
        viewer = await _register(client, "list-viewer@test.com", "viewer")

        project = await _create_project(client, owner, "shared-listed")
        pid = project["id"]

        # Before sharing: viewer sees 0 projects
        resp = await client.get("/api/v1/projects", headers=_auth(viewer))
        assert resp.json()["total"] == 0

        # Share
        await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "list-viewer@test.com"},
            headers=_auth(owner),
        )

        # After sharing: viewer sees 1 project
        resp = await client.get("/api/v1/projects", headers=_auth(viewer))
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_viewer_cannot_start_workflow(self, client: AsyncClient):
        """Viewer permission is insufficient for workflow start."""
        owner = await _register(client, "wf-owner@test.com", "owner")
        viewer = await _register(client, "wf-viewer@test.com", "viewer")

        project = await _create_project(client, owner, "wf project")
        pid = project["id"]

        await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "wf-viewer@test.com", "permission": "viewer"},
            headers=_auth(owner),
        )

        # Viewer tries to start workflow
        resp = await client.post(
            f"/api/v1/projects/{pid}/workflow/start",
            headers=_auth(viewer),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_collaborator_can_start_workflow(self, client: AsyncClient):
        """Collaborator permission allows workflow start (not blocked by 403)."""
        owner = await _register(client, "collab-owner@test.com", "owner")
        collab = await _register(client, "collab-user@test.com", "collaborator")

        project = await _create_project(client, owner, "collab project")
        pid = project["id"]

        await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "collab-user@test.com", "permission": "collaborator"},
            headers=_auth(owner),
        )

        # Mock Celery task to avoid Redis connection timeout
        mock_task = MagicMock()
        mock_task.id = "mock-task-id"
        with patch("app.tasks.run_review_segment.delay", return_value=mock_task):
            resp = await client.post(
                f"/api/v1/projects/{pid}/workflow/start",
                headers=_auth(collab),
            )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_share_with_self_rejected(self, client: AsyncClient):
        """Cannot share a project with yourself."""
        owner = await _register(client, "self-share@test.com", "owner")
        project = await _create_project(client, owner, "self project")
        pid = project["id"]

        resp = await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "self-share@test.com"},
            headers=_auth(owner),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_duplicate_share_rejected(self, client: AsyncClient):
        """Cannot share the same project with the same user twice."""
        owner = await _register(client, "dup-owner@test.com", "owner")
        target = await _register(client, "dup-target@test.com", "target")

        project = await _create_project(client, owner, "dup project")
        pid = project["id"]

        resp1 = await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "dup-target@test.com"},
            headers=_auth(owner),
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "dup-target@test.com"},
            headers=_auth(owner),
        )
        assert resp2.status_code == 409

    @pytest.mark.asyncio
    async def test_revoke_share(self, client: AsyncClient):
        """Revoking a share removes access immediately."""
        owner = await _register(client, "rev-owner@test.com", "owner")
        viewer = await _register(client, "rev-viewer@test.com", "viewer")

        project = await _create_project(client, owner, "revoke project")
        pid = project["id"]

        # Share
        resp = await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "rev-viewer@test.com"},
            headers=_auth(owner),
        )
        share_id = resp.json()["id"]

        # Viewer has access
        resp = await client.get(f"/api/v1/projects/{pid}", headers=_auth(viewer))
        assert resp.status_code == 200

        # Revoke
        resp = await client.delete(
            f"/api/v1/projects/{pid}/shares/{share_id}",
            headers=_auth(owner),
        )
        assert resp.status_code == 204

        # Viewer no longer has access
        resp = await client.get(f"/api/v1/projects/{pid}", headers=_auth(viewer))
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_list_shares(self, client: AsyncClient):
        """Owner can list all active shares."""
        owner = await _register(client, "ls-owner@test.com", "owner")
        viewer = await _register(client, "ls-viewer@test.com", "viewer")

        project = await _create_project(client, owner, "list shares")
        pid = project["id"]

        await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "ls-viewer@test.com"},
            headers=_auth(owner),
        )

        resp = await client.get(
            f"/api/v1/projects/{pid}/shares",
            headers=_auth(owner),
        )
        assert resp.status_code == 200
        shares = resp.json()
        assert len(shares) == 1
        assert shares[0]["email"] == "ls-viewer@test.com"

    @pytest.mark.asyncio
    async def test_update_share_permission(self, client: AsyncClient):
        """Owner can upgrade permission from viewer to collaborator."""
        owner = await _register(client, "up-owner@test.com", "owner")
        target = await _register(client, "up-target@test.com", "target")

        project = await _create_project(client, owner, "upgrade project")
        pid = project["id"]

        resp = await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "up-target@test.com", "permission": "viewer"},
            headers=_auth(owner),
        )
        share_id = resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/projects/{pid}/shares/{share_id}",
            json={"permission": "collaborator"},
            headers=_auth(owner),
        )
        assert resp.status_code == 200
        assert resp.json()["permission"] == "collaborator"


# ═══════════════════════════════════════════════════
# Admin privileges
# ═══════════════════════════════════════════════════


class TestAdminAccess:
    @pytest.mark.asyncio
    async def test_admin_can_access_any_project(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can access any user's project."""
        regular = await _register(client, "adm-reg@test.com", "regular")
        admin_tokens = await _register(client, "admin@test.com", "admin")

        # Promote to admin
        result = await db_session.execute(
            select(User).where(User.email == "admin@test.com")
        )
        admin_user = result.scalar_one()
        admin_user.role = "admin"
        await db_session.commit()

        # Re-login to get a token with admin role
        resp = await client.post("/api/v1/auth/login", json={
            "email": "admin@test.com",
            "password": "test-password-123",
        })
        admin_tokens = resp.json()

        project = await _create_project(client, regular, "regular's project")
        pid = project["id"]

        # Admin can access it
        resp = await client.get(f"/api/v1/projects/{pid}", headers=_auth(admin_tokens))
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_can_list_users(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can list all users."""
        await _register(client, "admin-lu@test.com", "admin")
        result = await db_session.execute(
            select(User).where(User.email == "admin-lu@test.com")
        )
        admin_user = result.scalar_one()
        admin_user.role = "admin"
        await db_session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "admin-lu@test.com",
            "password": "test-password-123",
        })
        admin_tokens = resp.json()

        resp = await client.get("/api/v1/users", headers=_auth(admin_tokens))
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    @pytest.mark.asyncio
    async def test_regular_user_cannot_list_users(self, client: AsyncClient):
        """Non-admin users cannot access user list."""
        tokens = await _register(client, "nonadmin@test.com", "user")
        resp = await client.get("/api/v1/users", headers=_auth(tokens))
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════
# User management API
# ═══════════════════════════════════════════════════


class TestUserManagement:
    @pytest.mark.asyncio
    async def test_get_me(self, client: AsyncClient):
        """Authenticated user can retrieve their profile."""
        tokens = await _register(client, "me@test.com", "myname")
        resp = await client.get("/api/v1/users/me", headers=_auth(tokens))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert data["username"] == "myname"

    @pytest.mark.asyncio
    async def test_update_me(self, client: AsyncClient):
        """User can update their own profile."""
        tokens = await _register(client, "update-me@test.com", "old-name")
        resp = await client.patch(
            "/api/v1/users/me",
            json={"username": "new-name"},
            headers=_auth(tokens),
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == "new-name"

    @pytest.mark.asyncio
    async def test_change_password(self, client: AsyncClient):
        """User can change their password."""
        tokens = await _register(client, "pw@test.com", "user")
        resp = await client.put(
            "/api/v1/users/me/password",
            json={"current_password": "test-password-123", "new_password": "new-password-456"},
            headers=_auth(tokens),
        )
        assert resp.status_code == 204

        # Login with new password
        resp = await client.post("/api/v1/auth/login", json={
            "email": "pw@test.com",
            "password": "new-password-456",
        })
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, client: AsyncClient):
        """Wrong current password is rejected."""
        tokens = await _register(client, "pw-wrong@test.com", "user")
        resp = await client.put(
            "/api/v1/users/me/password",
            json={"current_password": "wrong", "new_password": "new-password-456"},
            headers=_auth(tokens),
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_admin_deactivate_user(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin can deactivate another user."""
        await _register(client, "deact-admin@test.com", "admin")
        target = await _register(client, "deact-target@test.com", "target")

        result = await db_session.execute(
            select(User).where(User.email == "deact-admin@test.com")
        )
        admin_user = result.scalar_one()
        admin_user.role = "admin"
        await db_session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "deact-admin@test.com",
            "password": "test-password-123",
        })
        admin_tokens = resp.json()

        # Get target user id
        target_result = await db_session.execute(
            select(User).where(User.email == "deact-target@test.com")
        )
        target_user = target_result.scalar_one()

        resp = await client.delete(
            f"/api/v1/users/{target_user.id}",
            headers=_auth(admin_tokens),
        )
        assert resp.status_code == 204

        # Target can no longer login
        resp = await client.post("/api/v1/auth/login", json={
            "email": "deact-target@test.com",
            "password": "test-password-123",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_admin_cannot_deactivate_self(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Admin cannot deactivate themselves."""
        await _register(client, "self-deact@test.com", "admin")
        result = await db_session.execute(
            select(User).where(User.email == "self-deact@test.com")
        )
        admin_user = result.scalar_one()
        admin_user.role = "admin"
        await db_session.commit()

        resp = await client.post("/api/v1/auth/login", json={
            "email": "self-deact@test.com",
            "password": "test-password-123",
        })
        admin_tokens = resp.json()

        resp = await client.delete(
            f"/api/v1/users/{admin_user.id}",
            headers=_auth(admin_tokens),
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════
# Audit log
# ═══════════════════════════════════════════════════


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_share_creates_audit_entry(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Sharing a project should create an audit log entry."""
        owner = await _register(client, "audit-owner@test.com", "owner")
        viewer = await _register(client, "audit-viewer@test.com", "viewer")

        project = await _create_project(client, owner, "audit project")
        pid = project["id"]

        await client.post(
            f"/api/v1/projects/{pid}/shares",
            json={"email": "audit-viewer@test.com"},
            headers=_auth(owner),
        )

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "share_project",
                AuditLog.resource_id == pid,
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.resource_type == "project"


# ═══════════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════════


class TestBackwardCompat:
    @pytest.mark.asyncio
    async def test_no_auth_still_works(self, client: AsyncClient):
        """With AUTH_REQUIRED=false, existing APIs work without auth."""
        # Create project without auth
        resp = await client.post("/api/v1/projects", json={"user_query": "no auth"})
        assert resp.status_code == 201
        pid = resp.json()["id"]

        # List without auth
        resp = await client.get("/api/v1/projects")
        assert resp.status_code == 200

        # Get without auth
        resp = await client.get(f"/api/v1/projects/{pid}")
        assert resp.status_code == 200

        # Workflow status without auth
        resp = await client.get(f"/api/v1/projects/{pid}/workflow/status")
        assert resp.status_code == 200
