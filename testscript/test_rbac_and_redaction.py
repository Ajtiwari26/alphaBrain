"""
Tests for P0 RBAC roles, project-scoped authorization, secret redaction,
worker identity tokens, artifact path validation, and kill switch.
"""

import pytest
from fastapi import HTTPException

from alpha_core.security import (
    REDACTED,
    ROLE_PERMISSIONS,
    AuthPrincipal,
    PrincipalRole,
    create_worker_identity_token,
    redact_dict,
    redact_secrets,
    require_permission,
    require_project_access,
    require_safe_artifact_id,
    validate_artifact_identifier,
    verify_worker_identity_token,
    worker_kill_switch,
)

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

    def test_client_without_scoping_accesses_all(self):
        principal = AuthPrincipal(subject="client-open", role=PrincipalRole.CLIENT)
        assert principal.can_access_project("prj_any")

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
    def test_redacts_google_api_key(self):
        text = "key=AIzaSyABCDEFGHIJKLMNOPQRSTUVWXYZ12345678"
        assert REDACTED in redact_secrets(text)
        assert "AIzaSy" not in redact_secrets(text)

    def test_redacts_openai_key(self):
        text = "token: sk-abcdefghijklmnop12345678901234"
        assert REDACTED in redact_secrets(text)

    def test_redacts_stitch_key(self):
        text = "api_key: AQ.Ab8RN6Luc_b6ENWV5-7zW3"
        assert REDACTED in redact_secrets(text)

    def test_redacts_bearer_token(self):
        text = "Authorization: Bearer alpha-local-meeting-2026-test-token-32chars"
        assert REDACTED in redact_secrets(text)

    def test_redact_dict_strips_secret_fields(self):
        data = {
            "api_key": "super-secret-key",
            "password": "hunter2",
            "name": "Ajay",
            "nested": {
                "signing_secret": "very-secret",
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
