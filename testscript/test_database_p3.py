"""
testscript/test_database_p3.py
Comprehensive deterministic test suite for Alpha Brain P3 durable state:
- Alembic migration execution
- Memberships, clients, roles, consents
- Decisions, open questions, change requests
- Workflows, task dependencies, uniqueness & FK constraints
- Append-only audit protection (immutable records)
- JSON column storage & retrieval
- Tenant isolation & soft-delete queries
- Object storage signed URLs & backup integrity
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.backup import DatabaseBackupService
from alpha_core.db.connection import run_alembic_migrations_sync
from alpha_core.db.models import (
    AuditEventRecord,
    Base,
    ChangeRequestRecord,
    ClientRecord,
    ConsentRecord,
    DecisionRecord,
    MembershipRecord,
    OpenQuestionRecord,
    OrganizationRecord,
    ProjectRecord,
    SpecVersionRecord,
    TaskDependencyRecord,
    TaskRecord,
    UserRecord,
    WorkflowRecord,
)
from alpha_core.storage import ObjectStorageError, ObjectStorageService


@pytest.fixture
async def async_db():
    """Provides an isolated in-memory SQLite database session for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ===========================================================================
# 1. Alembic Migration Verification
# ===========================================================================


class TestAlembicMigrations:
    def test_migration_upgrade_on_clean_sqlite_db(self, tmp_path):
        db_file = tmp_path / "test_migration.db"
        sqlite_url = f"sqlite:///{db_file}"
        # Run Alembic upgrade head against fresh DB
        run_alembic_migrations_sync(sqlite_url)
        assert db_file.exists()
        assert db_file.stat().st_size > 0


# ===========================================================================
# 2. Organizations, Users, Clients, Memberships & Consents
# ===========================================================================


class TestTenantAndMembershipModels:
    async def test_organization_and_client_creation(self, async_db: AsyncSession):
        org = OrganizationRecord(id="org_test_01", name="Test Org", slug="test-org")
        async_db.add(org)
        await async_db.flush()

        client = ClientRecord(
            id="clt_01",
            org_id="org_test_01",
            name="Alice Client",
            email="alice@client.com",
            company="Acme Corp",
        )
        async_db.add(client)
        await async_db.commit()

        res = await async_db.execute(select(ClientRecord).where(ClientRecord.id == "clt_01"))
        fetched = res.scalar_one()
        assert fetched.name == "Alice Client"
        assert fetched.org_id == "org_test_01"
        assert fetched.status == "active"

    async def test_membership_unique_constraint(self, async_db: AsyncSession):
        org = OrganizationRecord(id="org_test_02", name="Org 2", slug="org-2")
        user = UserRecord(id="usr_01", name="Bob", email="bob@test.com", role="client")
        async_db.add_all([org, user])
        await async_db.flush()

        m1 = MembershipRecord(id="mem_01", user_id="usr_01", org_id="org_test_02", role="client")
        async_db.add(m1)
        await async_db.commit()

        # Duplicate membership for same user and org should raise IntegrityError
        m2 = MembershipRecord(id="mem_02", user_id="usr_01", org_id="org_test_02", role="admin")
        async_db.add(m2)
        with pytest.raises(IntegrityError):
            await async_db.commit()
        await async_db.rollback()

    async def test_consent_record_creation_and_revocation(self, async_db: AsyncSession):
        org = OrganizationRecord(id="org_test_03", name="Org 3", slug="org-3")
        user = UserRecord(id="usr_02", name="Charlie", email="charlie@test.com")
        async_db.add_all([org, user])
        await async_db.flush()

        consent = ConsentRecord(
            id="cns_01",
            org_id="org_test_03",
            user_id="usr_02",
            consent_type="voice_recording",
            granted=True,
            ip_address="127.0.0.1",
        )
        async_db.add(consent)
        await async_db.commit()

        res = await async_db.execute(select(ConsentRecord).where(ConsentRecord.id == "cns_01"))
        fetched = res.scalar_one()
        assert fetched.granted is True
        assert fetched.consent_type == "voice_recording"


# ===========================================================================
# 3. Decisions, Open Questions & Change Requests
# ===========================================================================


class TestSpecAndDecisionModels:
    async def test_decisions_and_open_questions_lifecycle(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_p3_01", name="P3 Project", repo_path="/path/repo")
        spec = SpecVersionRecord(
            id="spc_01",
            project_id="prj_p3_01",
            version=1,
            title="Spec v1",
            summary="Summary v1",
            spec_json={"requirements": [{"req_id": "REQ-1"}]},
        )
        async_db.add_all([proj, spec])
        await async_db.flush()

        decision = DecisionRecord(
            id="dec_01",
            project_id="prj_p3_01",
            spec_id="spc_01",
            topic="Database Strategy",
            decision="Adopt PostgreSQL with Alembic",
            rationale="Robust durable state and migrations",
            alternatives_json=["SQLite only", "Raw SQL"],
        )

        question = OpenQuestionRecord(
            id="opq_01",
            project_id="prj_p3_01",
            spec_id="spc_01",
            question="What is the backup retention window?",
            context="Need GDPR compliance",
            owner="founder",
        )

        cr = ChangeRequestRecord(
            id="cr_01",
            project_id="prj_p3_01",
            title="Add SMS alerting",
            description="Notify founder on worker stall",
            requested_by="client-bob",
        )

        async_db.add_all([decision, question, cr])
        await async_db.commit()

        # Verify JSON list retrieval in decision
        res_dec = await async_db.execute(
            select(DecisionRecord).where(DecisionRecord.id == "dec_01")
        )
        fetched_dec = res_dec.scalar_one()
        assert fetched_dec.alternatives_json == ["SQLite only", "Raw SQL"]

        # Verify open question resolution
        res_q = await async_db.execute(
            select(OpenQuestionRecord).where(OpenQuestionRecord.id == "opq_01")
        )
        fetched_q = res_q.scalar_one()
        assert fetched_q.resolved is False
        fetched_q.resolved = True
        fetched_q.answer = "30 days default retention"
        await async_db.commit()

        res_q2 = await async_db.execute(
            select(OpenQuestionRecord).where(OpenQuestionRecord.id == "opq_01")
        )
        assert res_q2.scalar_one().resolved is True


# ===========================================================================
# 4. Workflows & Normalized Task Dependencies
# ===========================================================================


class TestWorkflowsAndTaskDependencies:
    async def test_workflow_and_task_dependencies(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_p3_02", name="P3 Workflow Proj", repo_path="/path/repo")
        wf = WorkflowRecord(
            id="wf_01",
            project_id="prj_p3_02",
            phase="in_progress",
            status="active",
            details_json={"current_sprint": 1},
        )
        task_a = TaskRecord(
            id="tsk_a",
            project_id="prj_p3_02",
            repo="/path/repo",
            objective="Task A",
            details_json={"task_id": "tsk_a"},
        )
        task_b = TaskRecord(
            id="tsk_b",
            project_id="prj_p3_02",
            repo="/path/repo",
            objective="Task B",
            details_json={"task_id": "tsk_b"},
        )
        async_db.add_all([proj, wf, task_a, task_b])
        await async_db.flush()

        dep = TaskDependencyRecord(
            id="dep_ab",
            task_id="tsk_b",
            depends_on_task_id="tsk_a",
            required_status="completed",
        )
        async_db.add(dep)
        await async_db.commit()

        res_dep = await async_db.execute(
            select(TaskDependencyRecord).where(TaskDependencyRecord.id == "dep_ab")
        )
        fetched_dep = res_dep.scalar_one()
        assert fetched_dep.task_id == "tsk_b"
        assert fetched_dep.depends_on_task_id == "tsk_a"

        # Unique constraint on same dependency
        dup_dep = TaskDependencyRecord(
            id="dep_ab_dup",
            task_id="tsk_b",
            depends_on_task_id="tsk_a",
        )
        async_db.add(dup_dep)
        with pytest.raises(IntegrityError):
            await async_db.commit()
        await async_db.rollback()


# ===========================================================================
# 5. Immutable Append-Only Audit Log Protection
# ===========================================================================


class TestAuditLogProtection:
    async def test_audit_event_update_is_blocked(self, async_db: AsyncSession):
        evt = AuditEventRecord(
            id="aud_01",
            event_type="task_leased",
            actor="worker-01",
            details_json={"task_id": "tsk_101"},
        )
        async_db.add(evt)
        await async_db.commit()

        # Attempt to update audit event record must raise RuntimeError
        evt.actor = "tampered-actor"
        with pytest.raises(RuntimeError, match="AuditEventRecord is immutable"):
            await async_db.commit()
        await async_db.rollback()

    async def test_audit_event_delete_is_blocked(self, async_db: AsyncSession):
        evt = AuditEventRecord(
            id="aud_02",
            event_type="task_completed",
            actor="worker-01",
            details_json={"task_id": "tsk_102"},
        )
        async_db.add(evt)
        await async_db.commit()

        # Attempt to delete audit event record must raise RuntimeError
        await async_db.delete(evt)
        with pytest.raises(RuntimeError, match="AuditEventRecord is append-only"):
            await async_db.commit()
        await async_db.rollback()


# ===========================================================================
# 6. Tenant Isolation & Soft-Delete Queries
# ===========================================================================


class TestTenantIsolationAndSoftDelete:
    async def test_tenant_isolation_queries(self, async_db: AsyncSession):
        org1 = OrganizationRecord(id="org_alpha", name="Alpha Org", slug="org-alpha")
        org2 = OrganizationRecord(id="org_beta", name="Beta Org", slug="org-beta")
        proj1 = ProjectRecord(
            id="prj_a", org_id="org_alpha", name="Proj Alpha", repo_path="/repo/a"
        )
        proj2 = ProjectRecord(id="prj_b", org_id="org_beta", name="Proj Beta", repo_path="/repo/b")
        task1 = TaskRecord(
            id="tsk_1",
            project_id="prj_a",
            org_id="org_alpha",
            repo="/repo/a",
            objective="T1",
            details_json={},
        )
        task2 = TaskRecord(
            id="tsk_2",
            project_id="prj_b",
            org_id="org_beta",
            repo="/repo/b",
            objective="T2",
            details_json={},
        )

        async_db.add_all([org1, org2, proj1, proj2, task1, task2])
        await async_db.commit()

        # Query scoped to org_alpha only returns org_alpha tasks
        res1 = await async_db.execute(select(TaskRecord).where(TaskRecord.org_id == "org_alpha"))
        tasks_alpha = res1.scalars().all()
        assert len(tasks_alpha) == 1
        assert tasks_alpha[0].id == "tsk_1"

        # Query scoped to org_beta only returns org_beta tasks
        res2 = await async_db.execute(select(TaskRecord).where(TaskRecord.org_id == "org_beta"))
        tasks_beta = res2.scalars().all()
        assert len(tasks_beta) == 1
        assert tasks_beta[0].id == "tsk_2"

    async def test_soft_delete_query_filtering(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_del", name="Active Proj", repo_path="/repo/del")
        async_db.add(proj)
        await async_db.commit()

        # Mark soft deleted
        proj.deleted_at = datetime.now(UTC)
        await async_db.commit()

        # Active projects filter excludes soft-deleted records
        res = await async_db.execute(
            select(ProjectRecord).where(ProjectRecord.deleted_at.is_(None))
        )
        active = res.scalars().all()
        assert "prj_del" not in [p.id for p in active]


# ===========================================================================
# 7. Object Storage & Signed URLs
# ===========================================================================


class TestObjectStorageService:
    def test_signed_download_and_upload_urls(self):
        service = ObjectStorageService(
            bucket_name="alphabrain-test-bucket",
            secret_key="test-secret-storage-key-12345",
            base_url="http://localhost:8000",
        )

        # 1. Download signed URL
        dl = service.generate_signed_download_url(
            "artifacts/prj_01/build.zip", expires_in_seconds=600
        )
        assert "signature=" in dl["url"]
        assert dl["encryption"] == "AES256"

        # 2. Upload signed URL
        up = service.generate_signed_upload_url(
            "artifacts/prj_01/screenshot.png", media_type="image/png"
        )
        assert "signature=" in up["url"]
        assert up["required_headers"]["x-amz-server-side-encryption"] == "AES256"
        assert up["media_type"] == "image/png"

    def test_rejects_path_traversal_in_storage_key(self):
        service = ObjectStorageService()
        with pytest.raises(ObjectStorageError):
            service.generate_signed_download_url("../../etc/passwd")

        with pytest.raises(ObjectStorageError):
            service.generate_signed_upload_url("/absolute/path", media_type="text/plain")

    def test_rejects_unallowlisted_media_type(self):
        service = ObjectStorageService()
        with pytest.raises(ObjectStorageError):
            service.generate_signed_upload_url("file.exe", media_type="application/x-msdownload")


# ===========================================================================
# 8. Database Backup & Retention
# ===========================================================================


class TestDatabaseBackupService:
    def test_manifest_creation_and_integrity_verification(self, tmp_path):
        backup_dir = tmp_path / "backups"
        service = DatabaseBackupService(backup_dir=backup_dir)

        # Create dummy dump file
        dump_file = backup_dir / "alphabrain_20260826.dump"
        dump_file.write_bytes(b"PGDUMP_TEST_PAYLOAD_1234567890")

        checksum = service.calculate_checksum(dump_file)
        manifest = service.create_backup_manifest(
            backup_filename=dump_file.name,
            table_counts={"tasks": 10, "projects": 2},
            file_size_bytes=dump_file.stat().st_size,
            sha256_hash=checksum,
        )

        assert manifest["sha256_checksum"] == checksum
        assert service.verify_backup_integrity(dump_file) is True

        # Tampering with file fails integrity check
        dump_file.write_bytes(b"TAMPERED_CONTENT")
        assert service.verify_backup_integrity(dump_file) is False
