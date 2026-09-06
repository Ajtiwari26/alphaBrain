"""
Tests for P0 RBAC roles, project-scoped authorization, secret redaction,
worker identity tokens, artifact path validation, and kill switch.
"""

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from alpha_core.api.app import app
from alpha_core.security import (
    REDACTED,
    ROLE_PERMISSIONS,
    AuthPrincipal,
    PrincipalRole,
    create_scoped_principal_token,
    create_worker_identity_token,
    redact_dict,
    redact_secrets,
    require_permission,
    require_project_access,
    require_safe_artifact_id,
    validate_artifact_identifier,
    verify_scoped_principal_token,
    verify_worker_identity_token,
    worker_kill_switch,
)
from alpha_protocol import TaskEnvelope

# ---------------------------------------------------------------------------
# RBAC Role & Permission Tests
# ---------------------------------------------------------------------------


class TestRBACRoles:
    def test_all_roles_defined(self):
        """Every declared role must have a permission set."""
        for role in PrincipalRole:
            assert role in ROLE_PERMISSIONS, f"Missing permission set for {role}"

    def test_founder_has_full_permissions(self):
        principal = AuthPrincipal(subject="ajay", role=PrincipalRole.FOUNDER)
        assert principal.has_permission("project:read")
        assert principal.has_permission("project:write")
        assert principal.has_permission("project:delete")
        assert principal.has_permission("task:write")
        assert principal.has_permission("worker:kill")
        assert principal.has_permission("deployment:rollback")
        assert principal.has_permission("call:initiate")

    def test_client_has_limited_permissions(self):
        principal = AuthPrincipal(subject="client-maya", role=PrincipalRole.CLIENT)
        assert principal.has_permission("project:read")
        assert principal.has_permission("spec:approve")
        assert principal.has_permission("meeting:join")
        assert not principal.has_permission("task:write")
        assert not principal.has_permission("worker:kill")
        assert not principal.has_permission("deployment:approve")

    def test_worker_can_only_lease_and_submit(self):
        principal = AuthPrincipal(subject="mac-worker-01", role=PrincipalRole.WORKER)
        assert principal.has_permission("task:read")
        assert principal.has_permission("task:write")
        assert not principal.has_permission("project:write")
        assert not principal.has_permission("deployment:approve")
        assert not principal.has_permission("call:initiate")

    def test_service_has_inter_service_permissions(self):
        principal = AuthPrincipal(subject="agentline-svc", role=PrincipalRole.SERVICE)
        assert principal.has_permission("call:initiate")
        assert principal.has_permission("task:write")
        assert not principal.has_permission("worker:kill")

    def test_require_permission_raises_403(self):
        client = AuthPrincipal(subject="client-1", role=PrincipalRole.CLIENT)
        with pytest.raises(HTTPException) as exc:
            require_permission(client, "task:write")
        assert exc.value.status_code == 403
        assert "lacks permission" in exc.value.detail

    def test_require_permission_passes_for_valid_role(self):
        founder = AuthPrincipal(subject="ajay", role=PrincipalRole.FOUNDER)
        require_permission(founder, "deployment:approve")  # Should not raise


# ---------------------------------------------------------------------------
# Project Scoped Access Tests
# ---------------------------------------------------------------------------


class TestProjectAccess:
    def test_founder_accesses_any_project(self):
        principal = AuthPrincipal(subject="ajay", role=PrincipalRole.FOUNDER)
        assert principal.can_access_project("prj_alpha")
        assert principal.can_access_project("prj_anything")

    def test_client_scoped_to_specific_projects(self):
        principal = AuthPrincipal(
            subject="client-maya",
            role=PrincipalRole.CLIENT,
            project_ids=("prj_alpha",),
        )
        assert principal.can_access_project("prj_alpha")
        assert not principal.can_access_project("prj_other")

    def test_client_without_scoping_fails_closed(self):
        principal = AuthPrincipal(subject="client-unscoped", role=PrincipalRole.CLIENT)
        assert not principal.can_access_project("prj_any")

    def test_require_project_access_raises_403(self):
        scoped = AuthPrincipal(
            subject="client-x",
            role=PrincipalRole.CLIENT,
            project_ids=("prj_alpha",),
        )
        with pytest.raises(HTTPException) as exc:
            require_project_access(scoped, "prj_other_project")
        assert exc.value.status_code == 403
        assert "project not in authorized scope" in exc.value.detail


# ---------------------------------------------------------------------------
# Worker Identity Token Tests
# ---------------------------------------------------------------------------


class TestWorkerIdentityTokens:
    def test_create_and_verify_worker_token(self):
        token = create_worker_identity_token("mac-worker-01", capabilities=["run_tests"])
        claims = verify_worker_identity_token(token)
        assert claims is not None
        assert claims["sub"] == "mac-worker-01"
        assert claims["role"] == "worker"
        assert "run_tests" in claims["cap"]

    def test_tampered_token_fails(self):
        token = create_worker_identity_token("mac-worker-01")
        assert verify_worker_identity_token(token + "x") is None

    def test_expired_token_fails(self, monkeypatch):
        import alpha_core.security as sec_module

        monkeypatch.setattr(sec_module.time, "time", lambda: 1_000)
        token = create_worker_identity_token("mac-worker-01", ttl_seconds=60)

        monkeypatch.setattr(sec_module.time, "time", lambda: 1_061)
        assert verify_worker_identity_token(token) is None

    def test_none_and_empty_token_fail(self):
        assert verify_worker_identity_token(None) is None
        assert verify_worker_identity_token("") is None


# ---------------------------------------------------------------------------
# Secret Redaction Tests
# ---------------------------------------------------------------------------


class TestSecretRedaction:
    def test_redacts_generic_api_key(self):
        text = "api_key: synthetic_api_key_value_12345"
        assert REDACTED in redact_secrets(text)
        assert "synthetic_api_key_value_12345" not in redact_secrets(text)

    def test_redacts_token_assignment(self):
        text = "token: synthetic_auth_token_value_12345"
        assert REDACTED in redact_secrets(text)
        assert "synthetic_auth_token_value_12345" not in redact_secrets(text)

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer synthetic_bearer_token_value_12345"
        assert REDACTED in redact_secrets(text)
        assert "synthetic_bearer_token_value_12345" not in redact_secrets(text)

    def test_redact_dict_strips_secret_fields(self):
        data = {
            "api_key": "synthetic_key_value",
            "password": "synthetic_password_value",
            "name": "Ajay",
            "nested": {
                "signing_secret": "synthetic_secret_value",
                "safe": "okay",
            },
        }
        cleaned = redact_dict(data)
        assert cleaned["api_key"] == REDACTED
        assert cleaned["password"] == REDACTED
        assert cleaned["name"] == "Ajay"
        assert cleaned["nested"]["signing_secret"] == REDACTED
        assert cleaned["nested"]["safe"] == "okay"

    def test_preserves_non_secret_content(self):
        text = "Hello World, this is a normal log message"
        assert redact_secrets(text) == text


# ---------------------------------------------------------------------------
# Artifact Path Validation Tests
# ---------------------------------------------------------------------------


class TestArtifactValidation:
    def test_valid_artifact_ids(self):
        assert validate_artifact_identifier("report.pdf") is True
        assert validate_artifact_identifier("artifacts/build/output.log") is True
        assert validate_artifact_identifier("v1.2.3-rc1") is True

    def test_rejects_path_traversal(self):
        assert validate_artifact_identifier("../escape") is False
        assert validate_artifact_identifier("foo/../bar") is False

    def test_rejects_absolute_paths(self):
        assert validate_artifact_identifier("/etc/passwd") is False

    def test_rejects_empty_and_special(self):
        assert validate_artifact_identifier("") is False
        assert validate_artifact_identifier(" spaces bad") is False

    def test_require_safe_raises_400(self):
        with pytest.raises(HTTPException) as exc:
            require_safe_artifact_id("../escape")
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Worker Kill Switch Tests
# ---------------------------------------------------------------------------


class TestWorkerKillSwitch:
    def setup_method(self):
        worker_kill_switch.resume_all()

    def test_default_allows_execution(self):
        assert worker_kill_switch.can_execute("prj_alpha") is True

    def test_global_kill_blocks_all(self):
        worker_kill_switch.kill_all()
        assert worker_kill_switch.can_execute() is False
        assert worker_kill_switch.can_execute("prj_alpha") is False

    def test_resume_restores_execution(self):
        worker_kill_switch.kill_all()
        worker_kill_switch.resume_all()
        assert worker_kill_switch.can_execute("prj_alpha") is True

    def test_project_pause_blocks_only_that_project(self):
        worker_kill_switch.pause_project("prj_alpha")
        assert worker_kill_switch.can_execute("prj_alpha") is False
        assert worker_kill_switch.can_execute("prj_beta") is True

    def test_project_resume_unpauses(self):
        worker_kill_switch.pause_project("prj_alpha")
        worker_kill_switch.resume_project("prj_alpha")
        assert worker_kill_switch.can_execute("prj_alpha") is True


# ---------------------------------------------------------------------------
# Scoped Principal Token Tests
# ---------------------------------------------------------------------------


class TestScopedPrincipalTokens:
    def test_create_and_verify_scoped_principal_token(self):
        token = create_scoped_principal_token(
            subject="client-maya",
            role=PrincipalRole.CLIENT,
            project_ids=["prj_alpha", "prj_shared"],
            ttl_seconds=1800,
        )
        principal = verify_scoped_principal_token(token)
        assert principal is not None
        assert principal.subject == "client-maya"
        assert principal.role == PrincipalRole.CLIENT
        assert principal.project_ids == ("prj_alpha", "prj_shared")
        assert principal.can_access_project("prj_alpha") is True
        assert principal.can_access_project("prj_shared") is True
        assert principal.can_access_project("prj_other") is False

    def test_tampered_scoped_principal_token_fails(self):
        token = create_scoped_principal_token(
            subject="client-1",
            role=PrincipalRole.CLIENT,
            project_ids=["prj_alpha"],
        )
        assert verify_scoped_principal_token(token + "tampered") is None

    def test_expired_scoped_principal_token_fails(self, monkeypatch):
        import alpha_core.security as sec_module

        monkeypatch.setattr(sec_module.time, "time", lambda: 5000)
        token = create_scoped_principal_token(
            subject="client-1",
            role=PrincipalRole.CLIENT,
            project_ids=["prj_alpha"],
            ttl_seconds=30,
        )
        monkeypatch.setattr(sec_module.time, "time", lambda: 5035)
        assert verify_scoped_principal_token(token) is None


# ---------------------------------------------------------------------------
# Real API Cross-Project 403 Tests
# ---------------------------------------------------------------------------


class TestAPICrossProjectAccess:
    @pytest.mark.asyncio
    async def test_cross_project_api_returns_403_for_scoped_client(self, api_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Founder submits two tasks for different projects
            task_alpha = TaskEnvelope(
                task_id="tsk_api_proj_alpha_01",
                project_id="prj_alpha",
                repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
                objective="Alpha task",
                allowed_paths=["."],
                base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )
            task_beta = TaskEnvelope(
                task_id="tsk_api_proj_beta_01",
                project_id="prj_beta",
                repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
                objective="Beta task",
                allowed_paths=["."],
                base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )
            res_sub_alpha = await client.post(
                "/api/tasks",
                json=task_alpha.model_dump(mode="json"),
                headers=api_headers,
            )
            assert res_sub_alpha.status_code == 200

            res_sub_beta = await client.post(
                "/api/tasks",
                json=task_beta.model_dump(mode="json"),
                headers=api_headers,
            )
            assert res_sub_beta.status_code == 200

            # 2. Mint client token scoped ONLY to prj_alpha
            client_token = create_scoped_principal_token(
                subject="client_alpha_only",
                role=PrincipalRole.CLIENT,
                project_ids=["prj_alpha"],
            )
            client_headers = {"Authorization": f"Bearer {client_token}"}

            # 3. Client reading authorized task (prj_alpha) -> 200 OK
            res_read_alpha = await client.get(
                f"/api/tasks/{task_alpha.task_id}",
                headers=client_headers,
            )
            assert res_read_alpha.status_code == 200

            # 4. Client reading unauthorized task (prj_beta) -> 403 Forbidden!
            res_read_beta = await client.get(
                f"/api/tasks/{task_beta.task_id}",
                headers=client_headers,
            )
            assert res_read_beta.status_code == 403
            assert "project not in authorized scope" in res_read_beta.json()["detail"]

            # 5. Client getting progress of authorized project -> 200 OK
            res_prog_alpha = await client.get(
                "/api/projects/prj_alpha/progress",
                headers=client_headers,
            )
            assert res_prog_alpha.status_code == 200

            # 6. Client getting progress of unauthorized project -> 403 Forbidden!
            res_prog_beta = await client.get(
                "/api/projects/prj_beta/progress",
                headers=client_headers,
            )
            assert res_prog_beta.status_code == 403
            assert "project not in authorized scope" in res_prog_beta.json()["detail"]

            # 7. Client attempting to submit task (unauthorized permission) -> 403 Forbidden!
            res_sub_client = await client.post(
                "/api/tasks",
                json=task_alpha.model_dump(mode="json"),
                headers=client_headers,
            )
            assert res_sub_client.status_code == 403
            assert "lacks permission 'task:write'" in res_sub_client.json()["detail"]

            # 8. Client attempting slide access for unauthorized project -> 403 Forbidden!
            res_slide_beta = await client.get(
                "/api/meet/slide?project=prj_beta",
                headers=client_headers,
            )
            assert res_slide_beta.status_code == 403

            # 9. Client attempting slide access for authorized project -> 200 OK
            res_slide_alpha = await client.get(
                "/api/meet/slide?project=prj_alpha",
                headers=client_headers,
            )
            assert res_slide_alpha.status_code == 200


# ---------------------------------------------------------------------------
# Kill Switch API Enforcement Tests
# ---------------------------------------------------------------------------


class TestKillSwitchAPIEnforcement:
    def setup_method(self):
        worker_kill_switch.resume_all()

    def teardown_method(self):
        worker_kill_switch.resume_all()

    @pytest.mark.asyncio
    async def test_paused_project_rejects_task_submission(self, api_headers):
        worker_kill_switch.pause_project("prj_paused")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            task = TaskEnvelope(
                task_id="tsk_api_paused_01",
                project_id="prj_paused",
                repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
                objective="Paused task",
                allowed_paths=["."],
                base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )
            res = await client.post(
                "/api/tasks",
                json=task.model_dump(mode="json"),
                headers=api_headers,
            )
            assert res.status_code == 403
            assert "paused for this project" in res.json()["detail"]

    @pytest.mark.asyncio
    async def test_global_kill_switch_stops_leasing(self, worker_headers):
        worker_kill_switch.kill_all()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/tasks/lease",
                json={"worker_id": "alpha_worker"},
                headers=worker_headers,
            )
            assert res.status_code == 200
            assert res.json()["status"] == "no_tasks_available"
