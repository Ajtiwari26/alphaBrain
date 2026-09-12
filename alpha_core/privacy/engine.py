import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.models import (
    AuditEventRecord,
    CallJobRecord,
    CallStatusRecord,
    ConsentRecord,
    MeetingParticipantRecord,
    TaskCheckpointRecord,
    TranscriptSegmentRecord,
    UserRecord,
    WorkerHealthRecord,
    utc_now,
)
from alpha_core.privacy.enums import ConsentType, DataClass
from alpha_core.privacy.models import (
    ConsentRecordRequest,
    ConsentResponse,
    ConsentWithdrawalRequest,
    DataDeletionResponse,
    DataExportResponse,
    RetentionPruneResponse,
    TelephonyValidationResponse,
)

logger = logging.getLogger("alpha_core.privacy")

# Default Retention TTLs (in days) by data class
DEFAULT_DATA_RETENTION_TTLS: dict[str, int] = {
    DataClass.WORKER_HEALTH.value: 7,
    DataClass.TASK_CHECKPOINTS.value: 14,
    DataClass.TRANSCRIPTS.value: 30,
    DataClass.MEETING_EVENTS.value: 30,
    DataClass.CALL_RECORDS.value: 90,
    DataClass.REVOKED_CONSENTS.value: 180,
}


def _record_to_consent_response(rec: ConsentRecord) -> ConsentResponse:
    return ConsentResponse(
        id=rec.id,
        user_id=rec.user_id,
        phone_number=rec.phone_number,
        project_id=rec.project_id,
        org_id=rec.org_id,
        consent_type=rec.consent_type,
        granted=rec.granted,
        ip_address=rec.ip_address,
        user_agent=rec.user_agent,
        recorded_at=rec.recorded_at,
        revoked_at=rec.revoked_at,
        metadata=rec.metadata_json or {},
    )


class ConsentManager:
    """Manages consent lifecycles: recording, updating, withdrawal, and queries."""

    @staticmethod
    async def record_consent(
        session: AsyncSession, request: ConsentRecordRequest
    ) -> ConsentResponse:
        consent_type_val = (
            request.consent_type.value
            if isinstance(request.consent_type, ConsentType)
            else str(request.consent_type)
        )

        query = select(ConsentRecord).where(ConsentRecord.consent_type == consent_type_val)
        if request.user_id:
            query = query.where(ConsentRecord.user_id == request.user_id)
        if request.phone_number:
            query = query.where(ConsentRecord.phone_number == request.phone_number)
        if request.project_id:
            query = query.where(ConsentRecord.project_id == request.project_id)

        result = await session.execute(query)
        existing = result.scalars().first()

        now = utc_now()
        if existing:
            existing.granted = request.granted
            if request.granted:
                existing.revoked_at = None
            else:
                existing.revoked_at = now
            if request.ip_address:
                existing.ip_address = request.ip_address
            if request.user_agent:
                existing.user_agent = request.user_agent
            if request.metadata:
                existing.metadata_json = {**(existing.metadata_json or {}), **request.metadata}
            existing.recorded_at = now
            await session.flush()
            return _record_to_consent_response(existing)

        new_consent = ConsentRecord(
            id=f"cst_{uuid.uuid4().hex[:16]}",
            org_id=request.org_id,
            project_id=request.project_id,
            user_id=request.user_id,
            phone_number=request.phone_number,
            consent_type=consent_type_val,
            granted=request.granted,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
            recorded_at=now,
            revoked_at=None if request.granted else now,
            metadata_json=request.metadata or {},
        )
        session.add(new_consent)
        await session.flush()
        return _record_to_consent_response(new_consent)

    @staticmethod
    async def withdraw_consent(
        session: AsyncSession, request: ConsentWithdrawalRequest
    ) -> list[ConsentResponse]:
        query = select(ConsentRecord).where(ConsentRecord.granted.is_(True))

        conditions = []
        if request.user_id:
            conditions.append(ConsentRecord.user_id == request.user_id)
        if request.phone_number:
            conditions.append(ConsentRecord.phone_number == request.phone_number)
        if not conditions:
            raise ValueError("Must provide user_id or phone_number to withdraw consent")

        query = query.where(or_(*conditions))

        if request.project_id:
            query = query.where(ConsentRecord.project_id == request.project_id)

        if request.consent_type:
            c_val = (
                request.consent_type.value
                if isinstance(request.consent_type, ConsentType)
                else str(request.consent_type)
            )
            query = query.where(ConsentRecord.consent_type == c_val)

        result = await session.execute(query)
        records = result.scalars().all()

        now = utc_now()
        withdrawn = []
        for rec in records:
            rec.granted = False
            rec.revoked_at = now
            meta = rec.metadata_json or {}
            if request.reason:
                meta["withdrawal_reason"] = request.reason
            rec.metadata_json = meta
            withdrawn.append(_record_to_consent_response(rec))

        await session.flush()
        return withdrawn

    @staticmethod
    async def list_consents(
        session: AsyncSession,
        user_id: str | None = None,
        phone_number: str | None = None,
        project_id: str | None = None,
        consent_type: str | None = None,
        active_only: bool = False,
    ) -> list[ConsentResponse]:
        query = select(ConsentRecord)
        if user_id:
            query = query.where(ConsentRecord.user_id == user_id)
        if phone_number:
            query = query.where(ConsentRecord.phone_number == phone_number)
        if project_id:
            query = query.where(ConsentRecord.project_id == project_id)
        if consent_type:
            query = query.where(ConsentRecord.consent_type == consent_type)
        if active_only:
            query = query.where(ConsentRecord.granted.is_(True), ConsentRecord.revoked_at.is_(None))

        query = query.order_by(ConsentRecord.recorded_at.desc())
        result = await session.execute(query)
        records = result.scalars().all()
        return [_record_to_consent_response(r) for r in records]

    @staticmethod
    async def has_active_consent(
        session: AsyncSession,
        consent_type: str,
        user_id: str | None = None,
        phone_number: str | None = None,
        project_id: str | None = None,
    ) -> bool:
        query = select(ConsentRecord).where(
            ConsentRecord.consent_type == consent_type,
            ConsentRecord.granted.is_(True),
            ConsentRecord.revoked_at.is_(None),
        )
        conditions = []
        if user_id:
            conditions.append(ConsentRecord.user_id == user_id)
        if phone_number:
            conditions.append(ConsentRecord.phone_number == phone_number)
        if not conditions:
            return False

        query = query.where(or_(*conditions))
        if project_id:
            query = query.where(
                or_(ConsentRecord.project_id == project_id, ConsentRecord.project_id.is_(None))
            )

        result = await session.execute(query)
        return result.scalars().first() is not None


class RTBFManager:
    """Right-To-Be-Forgotten: exports personal data and handles cascading erasure/anonymization."""

    @staticmethod
    async def export_user_data(
        session: AsyncSession,
        user_id: str | None = None,
        phone_number: str | None = None,
        email: str | None = None,
    ) -> DataExportResponse:
        subject_id = user_id or phone_number or email or "unknown"
        now = utc_now()

        # 1. User profile
        user_profile = None
        user_record = None
        if user_id or email:
            u_query = select(UserRecord)
            if user_id and email:
                u_query = u_query.where(or_(UserRecord.id == user_id, UserRecord.email == email))
            elif user_id:
                u_query = u_query.where(UserRecord.id == user_id)
            else:
                u_query = u_query.where(UserRecord.email == email)
            u_res = await session.execute(u_query)
            user_record = u_res.scalars().first()
            if user_record:
                user_profile = {
                    "id": user_record.id,
                    "name": user_record.name,
                    "email": user_record.email,
                    "role": user_record.role,
                    "created_at": user_record.created_at.isoformat()
                    if user_record.created_at
                    else None,
                    "is_active": user_record.is_active,
                }

        # 2. Consents
        c_conditions = []
        if user_id:
            c_conditions.append(ConsentRecord.user_id == user_id)
        if user_record:
            c_conditions.append(ConsentRecord.user_id == user_record.id)
        if phone_number:
            c_conditions.append(ConsentRecord.phone_number == phone_number)

        consents_data: list[dict[str, Any]] = []
        if c_conditions:
            c_res = await session.execute(select(ConsentRecord).where(or_(*c_conditions)))
            for c in c_res.scalars().all():
                consents_data.append(
                    {
                        "id": c.id,
                        "consent_type": c.consent_type,
                        "granted": c.granted,
                        "recorded_at": c.recorded_at.isoformat() if c.recorded_at else None,
                        "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
                        "metadata": c.metadata_json or {},
                    }
                )

        # 3. Call Jobs
        call_jobs_data: list[dict[str, Any]] = []
        call_conditions = []
        if phone_number:
            call_conditions.append(CallJobRecord.recipient_phone == phone_number)
        if user_record:
            call_conditions.append(CallJobRecord.recipient_name == user_record.name)

        if call_conditions:
            call_res = await session.execute(select(CallJobRecord).where(or_(*call_conditions)))
            for cj in call_res.scalars().all():
                call_jobs_data.append(
                    {
                        "id": cj.id,
                        "purpose": cj.purpose,
                        "recipient_phone": cj.recipient_phone,
                        "recipient_name": cj.recipient_name,
                        "status": cj.status,
                        "duration_seconds": cj.duration_seconds,
                    }
                )

        # 4. Meeting Participations & Transcript Segments
        meeting_parts_data: list[dict[str, Any]] = []
        transcripts_data: list[dict[str, Any]] = []
        part_conditions = []
        if user_id:
            part_conditions.append(MeetingParticipantRecord.identity == user_id)
        if user_record:
            part_conditions.append(MeetingParticipantRecord.identity == user_record.email)
            part_conditions.append(MeetingParticipantRecord.name == user_record.name)

        if part_conditions:
            part_res = await session.execute(
                select(MeetingParticipantRecord).where(or_(*part_conditions))
            )
            for mp in part_res.scalars().all():
                meeting_parts_data.append(
                    {
                        "id": mp.id,
                        "meeting_id": mp.meeting_id,
                        "identity": mp.identity,
                        "name": mp.name,
                        "role": mp.role,
                        "joined_at": mp.joined_at.isoformat() if mp.joined_at else None,
                    }
                )

            # Transcripts spoken by user
            tr_conditions = []
            if user_id:
                tr_conditions.append(TranscriptSegmentRecord.speaker_identity == user_id)
            if user_record:
                tr_conditions.append(TranscriptSegmentRecord.speaker_identity == user_record.email)
                tr_conditions.append(TranscriptSegmentRecord.speaker_name == user_record.name)

            if tr_conditions:
                tr_res = await session.execute(
                    select(TranscriptSegmentRecord).where(or_(*tr_conditions))
                )
                for tr in tr_res.scalars().all():
                    transcripts_data.append(
                        {
                            "id": tr.id,
                            "meeting_id": tr.meeting_id,
                            "speaker_name": tr.speaker_name,
                            "text": tr.text,
                            "timestamp": tr.timestamp.isoformat() if tr.timestamp else None,
                        }
                    )

        # 5. Audit summary (subject related actions)
        audit_summary = []
        audit_conditions = []
        if user_id:
            audit_conditions.append(AuditEventRecord.actor == user_id)
        if user_record:
            audit_conditions.append(AuditEventRecord.actor == user_record.email)

        if audit_conditions:
            aud_res = await session.execute(
                select(AuditEventRecord).where(or_(*audit_conditions)).limit(50)
            )
            for a in aud_res.scalars().all():
                audit_summary.append(
                    {
                        "id": a.id,
                        "event_type": a.event_type,
                        "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                    }
                )

        return DataExportResponse(
            export_id=f"exp_{uuid.uuid4().hex[:16]}",
            subject_id=subject_id,
            exported_at=now,
            user_profile=user_profile,
            consents=consents_data,
            call_jobs=call_jobs_data,
            meeting_participations=meeting_parts_data,
            transcript_segments=transcripts_data,
            audit_summary=audit_summary,
        )

    @staticmethod
    async def delete_user_data(
        session: AsyncSession,
        user_id: str | None = None,
        phone_number: str | None = None,
        email: str | None = None,
        reason: str = "Right to be forgotten request",
    ) -> DataDeletionResponse:
        subject_id = user_id or phone_number or email or "unknown"
        now = utc_now()
        counts: dict[str, int] = {
            "users_anonymized": 0,
            "consents_revoked": 0,
            "call_jobs_redacted": 0,
            "transcripts_redacted": 0,
            "meeting_participants_redacted": 0,
        }

        user_record = None
        if user_id or email:
            u_query = select(UserRecord)
            if user_id and email:
                u_query = u_query.where(or_(UserRecord.id == user_id, UserRecord.email == email))
            elif user_id:
                u_query = u_query.where(UserRecord.id == user_id)
            else:
                u_query = u_query.where(UserRecord.email == email)
            u_res = await session.execute(u_query)
            user_record = u_res.scalars().first()

        # 1. Anonymize user record
        if user_record:
            user_record.name = "[REDACTED]"
            user_record.email = f"anonymized_{uuid.uuid4().hex[:8]}@deleted.local"
            user_record.is_active = False
            user_record.deleted_at = now
            counts["users_anonymized"] += 1

        # 2. Revoke and scrub consents
        c_conditions = []
        if user_id:
            c_conditions.append(ConsentRecord.user_id == user_id)
        if user_record:
            c_conditions.append(ConsentRecord.user_id == user_record.id)
        if phone_number:
            c_conditions.append(ConsentRecord.phone_number == phone_number)

        if c_conditions:
            c_res = await session.execute(select(ConsentRecord).where(or_(*c_conditions)))
            for c in c_res.scalars().all():
                c.granted = False
                c.revoked_at = now
                c.ip_address = "0.0.0.0"
                c.user_agent = "[REDACTED]"
                c.metadata_json = {"erasure_reason": reason, "erased_at": now.isoformat()}
                counts["consents_revoked"] += 1

        # 3. Redact Call Jobs
        call_conditions = []
        if phone_number:
            call_conditions.append(CallJobRecord.recipient_phone == phone_number)
        if user_record:
            call_conditions.append(CallJobRecord.recipient_name == user_record.name)

        if call_conditions:
            call_res = await session.execute(select(CallJobRecord).where(or_(*call_conditions)))
            for cj in call_res.scalars().all():
                cj.recipient_phone = "[REDACTED]"
                cj.recipient_name = "[REDACTED]"
                cj.script_facts_json = {}
                counts["call_jobs_redacted"] += 1

        # 4. Meeting participants and transcripts
        part_conditions = []
        if user_id:
            part_conditions.append(MeetingParticipantRecord.identity == user_id)
        if user_record:
            part_conditions.append(MeetingParticipantRecord.identity == user_record.email)

        if part_conditions:
            part_res = await session.execute(
                select(MeetingParticipantRecord).where(or_(*part_conditions))
            )
            for mp in part_res.scalars().all():
                mp.name = "[REDACTED]"
                mp.identity = f"redacted_{uuid.uuid4().hex[:8]}"
                counts["meeting_participants_redacted"] += 1

        tr_conditions = []
        if user_id:
            tr_conditions.append(TranscriptSegmentRecord.speaker_identity == user_id)
        if user_record:
            tr_conditions.append(TranscriptSegmentRecord.speaker_identity == user_record.email)

        if tr_conditions:
            tr_res = await session.execute(
                select(TranscriptSegmentRecord).where(or_(*tr_conditions))
            )
            for tr in tr_res.scalars().all():
                tr.speaker_name = "[REDACTED]"
                tr.text = "[REDACTED PURSUANT TO DATA PRIVACY RTBF REQUEST]"
                counts["transcripts_redacted"] += 1

        # 5. Immutable compliance audit record
        audit_id = f"aud_{uuid.uuid4().hex[:16]}"
        audit_event = AuditEventRecord(
            id=audit_id,
            event_type="privacy.rtbf_deletion",
            actor="privacy_compliance_engine",
            actor_role="compliance",
            details_json={
                "subject_id": subject_id,
                "reason": reason,
                "records_affected": counts,
                "completed_at": now.isoformat(),
            },
            timestamp=now,
        )
        session.add(audit_event)
        await session.flush()

        return DataDeletionResponse(
            deletion_id=f"del_{uuid.uuid4().hex[:16]}",
            subject_id=subject_id,
            status="completed",
            deleted_at=now,
            records_affected=counts,
            audit_event_id=audit_id,
        )


class DataRetentionEngine:
    """Automates retention lifecycle by pruning expired records across data classes based on configurable TTLs."""

    @staticmethod
    async def prune_expired_records(
        session: AsyncSession,
        custom_ttls: dict[str, int] | None = None,
        cutoff_reference: datetime | None = None,
        dry_run: bool = False,
    ) -> RetentionPruneResponse:
        now = cutoff_reference or utc_now()
        effective_ttls = {**DEFAULT_DATA_RETENTION_TTLS, **(custom_ttls or {})}

        counts: dict[str, int] = {}
        cutoffs: dict[str, str] = {}

        # 1. Worker Health History
        wh_ttl = effective_ttls.get(DataClass.WORKER_HEALTH.value, 7)
        wh_cutoff = now - timedelta(days=wh_ttl)
        cutoffs[DataClass.WORKER_HEALTH.value] = wh_cutoff.isoformat()
        wh_stmt = select(func.count(WorkerHealthRecord.id)).where(
            WorkerHealthRecord.reported_at < wh_cutoff
        )
        wh_count = (await session.execute(wh_stmt)).scalar() or 0
        if not dry_run and wh_count > 0:
            await session.execute(
                delete(WorkerHealthRecord).where(WorkerHealthRecord.reported_at < wh_cutoff)
            )
        counts[DataClass.WORKER_HEALTH.value] = wh_count

        # 2. Task Checkpoints
        chk_ttl = effective_ttls.get(DataClass.TASK_CHECKPOINTS.value, 14)
        chk_cutoff = now - timedelta(days=chk_ttl)
        cutoffs[DataClass.TASK_CHECKPOINTS.value] = chk_cutoff.isoformat()
        chk_stmt = select(func.count(TaskCheckpointRecord.id)).where(
            TaskCheckpointRecord.created_at < chk_cutoff
        )
        chk_count = (await session.execute(chk_stmt)).scalar() or 0
        if not dry_run and chk_count > 0:
            await session.execute(
                delete(TaskCheckpointRecord).where(TaskCheckpointRecord.created_at < chk_cutoff)
            )
        counts[DataClass.TASK_CHECKPOINTS.value] = chk_count

        # 3. Transcripts
        tr_ttl = effective_ttls.get(DataClass.TRANSCRIPTS.value, 30)
        tr_cutoff = now - timedelta(days=tr_ttl)
        cutoffs[DataClass.TRANSCRIPTS.value] = tr_cutoff.isoformat()
        tr_stmt = select(func.count(TranscriptSegmentRecord.id)).where(
            TranscriptSegmentRecord.timestamp < tr_cutoff
        )
        tr_count = (await session.execute(tr_stmt)).scalar() or 0
        if not dry_run and tr_count > 0:
            await session.execute(
                delete(TranscriptSegmentRecord).where(TranscriptSegmentRecord.timestamp < tr_cutoff)
            )
        counts[DataClass.TRANSCRIPTS.value] = tr_count

        # 4. Call Records
        call_ttl = effective_ttls.get(DataClass.CALL_RECORDS.value, 90)
        call_cutoff = now - timedelta(days=call_ttl)
        cutoffs[DataClass.CALL_RECORDS.value] = call_cutoff.isoformat()
        # Find call job IDs to prune
        expired_calls_q = select(CallJobRecord.id).where(
            CallJobRecord.created_at < call_cutoff,
            CallJobRecord.status.in_(["completed", "failed", "cancelled"]),
        )
        # Check call_status history first to avoid FK constraint errors
        expired_call_ids = (await session.execute(expired_calls_q)).scalars().all()
        call_count = len(expired_call_ids)
        if not dry_run and call_count > 0:
            # Delete call status entries first
            await session.execute(
                delete(CallStatusRecord).where(CallStatusRecord.call_job_id.in_(expired_call_ids))
            )
            await session.execute(
                delete(CallJobRecord).where(CallJobRecord.id.in_(expired_call_ids))
            )
        counts[DataClass.CALL_RECORDS.value] = call_count

        # 5. Revoked Consents older than TTL
        cst_ttl = effective_ttls.get(DataClass.REVOKED_CONSENTS.value, 180)
        cst_cutoff = now - timedelta(days=cst_ttl)
        cutoffs[DataClass.REVOKED_CONSENTS.value] = cst_cutoff.isoformat()
        cst_stmt = select(func.count(ConsentRecord.id)).where(
            ConsentRecord.revoked_at.is_not(None),
            ConsentRecord.revoked_at < cst_cutoff,
        )
        cst_count = (await session.execute(cst_stmt)).scalar() or 0
        if not dry_run and cst_count > 0:
            await session.execute(
                delete(ConsentRecord).where(
                    ConsentRecord.revoked_at.is_not(None),
                    ConsentRecord.revoked_at < cst_cutoff,
                )
            )
        counts[DataClass.REVOKED_CONSENTS.value] = cst_count

        total_pruned = sum(counts.values())
        if not dry_run:
            await session.flush()

        return RetentionPruneResponse(
            pruned_counts=counts,
            total_pruned=total_pruned,
            executed_at=now,
            dry_run=dry_run,
            cutoffs=cutoffs,
        )


class TelephonyConsentValidator:
    """Enforces TCPA and statutory AI disclosure & consent compliance for voice calls."""

    @staticmethod
    async def validate_telephony_consent(
        session: AsyncSession,
        recipient_phone: str,
        project_id: str | None = None,
        require_recording_consent: bool = True,
        disclosure_acknowledged: bool = True,
    ) -> TelephonyValidationResponse:
        phone_clean = recipient_phone.strip()
        if not phone_clean:
            return TelephonyValidationResponse(
                allowed=False,
                recipient_phone=recipient_phone,
                disclosure_verified=False,
                rejection_reason="Recipient phone number cannot be empty",
            )

        # 1. Statutory AI voice disclosure requirement
        if not disclosure_acknowledged:
            return TelephonyValidationResponse(
                allowed=False,
                recipient_phone=phone_clean,
                disclosure_verified=False,
                rejection_reason="Statutory AI voice and call recording disclosure was not acknowledged",
            )

        # 2. Check for active telephonic_outreach consent
        outreach_q = select(ConsentRecord).where(
            ConsentRecord.phone_number == phone_clean,
            ConsentRecord.consent_type == ConsentType.TELEPHONIC_OUTREACH.value,
        )
        if project_id:
            outreach_q = outreach_q.where(
                or_(ConsentRecord.project_id == project_id, ConsentRecord.project_id.is_(None))
            )
        outreach_q = outreach_q.order_by(ConsentRecord.recorded_at.desc())

        res = await session.execute(outreach_q)
        outreach_consent = res.scalars().first()

        if not outreach_consent or not outreach_consent.granted or outreach_consent.revoked_at:
            revocation_note = (
                f" (revoked at {outreach_consent.revoked_at.isoformat()})"
                if outreach_consent and outreach_consent.revoked_at
                else ""
            )
            return TelephonyValidationResponse(
                allowed=False,
                recipient_phone=phone_clean,
                disclosure_verified=disclosure_acknowledged,
                rejection_reason=f"No active telephonic outreach consent on file for {phone_clean}{revocation_note}",
            )

        # 3. Check for voice recording consent if required
        if require_recording_consent:
            recording_q = select(ConsentRecord).where(
                ConsentRecord.phone_number == phone_clean,
                ConsentRecord.consent_type == ConsentType.VOICE_RECORDING.value,
            )
            if project_id:
                recording_q = recording_q.where(
                    or_(ConsentRecord.project_id == project_id, ConsentRecord.project_id.is_(None))
                )
            recording_q = recording_q.order_by(ConsentRecord.recorded_at.desc())

            r_res = await session.execute(recording_q)
            rec_consent = r_res.scalars().first()

            if not rec_consent or not rec_consent.granted or rec_consent.revoked_at:
                return TelephonyValidationResponse(
                    allowed=False,
                    recipient_phone=phone_clean,
                    disclosure_verified=disclosure_acknowledged,
                    rejection_reason=f"Voice recording consent missing or revoked for {phone_clean}",
                )

        return TelephonyValidationResponse(
            allowed=True,
            recipient_phone=phone_clean,
            consent_id=outreach_consent.id,
            disclosure_verified=True,
            rejection_reason=None,
        )
