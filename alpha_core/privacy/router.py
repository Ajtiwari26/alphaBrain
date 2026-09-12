import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.connection import get_db_session
from alpha_core.privacy.engine import (
    DEFAULT_DATA_RETENTION_TTLS,
    ConsentManager,
    DataRetentionEngine,
    RTBFManager,
    TelephonyConsentValidator,
)
from alpha_core.privacy.models import (
    ConsentListResponse,
    ConsentRecordRequest,
    ConsentResponse,
    ConsentWithdrawalRequest,
    DataDeletionRequest,
    DataDeletionResponse,
    DataExportRequest,
    DataExportResponse,
    RetentionPolicyConfig,
    RetentionPruneRequest,
    RetentionPruneResponse,
    TelephonyValidationRequest,
    TelephonyValidationResponse,
)
from alpha_core.security import AuthPrincipal, PrincipalRole, require_api_principal

logger = logging.getLogger("alpha_core.privacy.router")

privacy_router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


def verify_privacy_subject_authorization(
    principal: AuthPrincipal,
    user_id: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    project_id: str | None = None,
) -> None:
    """
    Verify that the authenticated principal is authorized to access or modify subject data.
    - Founders, Admins, and Service principals have global privacy authorization.
    - Scoped Client and Worker principals are restricted strictly to their own identity (subject)
      or permitted project scope, preventing Insecure Direct Object Reference (IDOR) attacks.
    """
    if principal.role in (PrincipalRole.FOUNDER, PrincipalRole.ADMIN, PrincipalRole.SERVICE):
        return

    # Client/Worker identity verification
    if user_id and principal.subject == user_id:
        return
    if email and principal.subject == email:
        return

    # Project-level access check (if principal's project scope includes project_id)
    if project_id and principal.project_ids and project_id in principal.project_ids:
        # Permitted if accessing general project data without impersonating a foreign user
        if not user_id and not email:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: principal is not authorized to access or modify this subject's data",
    )


def verify_admin_authorization(principal: AuthPrincipal) -> None:
    """Enforce administrative role for global data retention lifecycle operations."""
    if principal.role not in (PrincipalRole.FOUNDER, PrincipalRole.ADMIN, PrincipalRole.SERVICE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: administrative role required for data retention management",
        )


# ---------------------------------------------------------------------------
# Consent Management Endpoints
# ---------------------------------------------------------------------------


@privacy_router.post(
    "/consent", response_model=ConsentResponse, status_code=status.HTTP_201_CREATED
)
async def record_consent(
    payload: ConsentRecordRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> ConsentResponse:
    """Record, update, or re-affirm consent."""
    if not payload.user_id and not payload.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of user_id or phone_number must be specified",
        )
    verify_privacy_subject_authorization(
        principal,
        user_id=payload.user_id,
        phone_number=payload.phone_number,
        project_id=payload.project_id,
    )
    resp = await ConsentManager.record_consent(session, payload)
    await session.commit()
    return resp


@privacy_router.post("/consent/withdraw", response_model=ConsentListResponse)
async def withdraw_consent_post(
    payload: ConsentWithdrawalRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> ConsentListResponse:
    """Withdraw/revoke consent for a subject."""
    if not payload.user_id and not payload.phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of user_id or phone_number must be specified",
        )
    verify_privacy_subject_authorization(
        principal,
        user_id=payload.user_id,
        phone_number=payload.phone_number,
        project_id=payload.project_id,
    )
    records = await ConsentManager.withdraw_consent(session, payload)
    await session.commit()
    return ConsentListResponse(consents=records, total=len(records))


@privacy_router.delete("/consent", response_model=ConsentListResponse)
async def withdraw_consent_delete(
    user_id: str | None = Query(None),
    phone_number: str | None = Query(None),
    project_id: str | None = Query(None),
    consent_type: str | None = Query(None),
    reason: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> ConsentListResponse:
    """Withdraw/revoke consent via DELETE request."""
    if not user_id and not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of user_id or phone_number must be specified",
        )
    verify_privacy_subject_authorization(
        principal,
        user_id=user_id,
        phone_number=phone_number,
        project_id=project_id,
    )
    payload = ConsentWithdrawalRequest(
        user_id=user_id,
        phone_number=phone_number,
        project_id=project_id,
        consent_type=consent_type,
        reason=reason,
    )
    records = await ConsentManager.withdraw_consent(session, payload)
    await session.commit()
    return ConsentListResponse(consents=records, total=len(records))


@privacy_router.get("/consent", response_model=ConsentListResponse)
async def list_consents(
    user_id: str | None = Query(None),
    phone_number: str | None = Query(None),
    project_id: str | None = Query(None),
    consent_type: str | None = Query(None),
    active_only: bool = Query(False),
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> ConsentListResponse:
    """List and filter consent records."""
    verify_privacy_subject_authorization(
        principal,
        user_id=user_id,
        phone_number=phone_number,
        project_id=project_id,
    )
    records = await ConsentManager.list_consents(
        session,
        user_id=user_id,
        phone_number=phone_number,
        project_id=project_id,
        consent_type=consent_type,
        active_only=active_only,
    )
    return ConsentListResponse(consents=records, total=len(records))


# ---------------------------------------------------------------------------
# Right-To-Be-Forgotten (RTBF) Export and Deletion Endpoints
# ---------------------------------------------------------------------------


@privacy_router.get("/export", response_model=DataExportResponse)
async def export_data_get(
    user_id: str | None = Query(None),
    phone_number: str | None = Query(None),
    email: str | None = Query(None),
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> DataExportResponse:
    """Export all stored subject data in machine-readable format."""
    if not any([user_id, phone_number, email]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one of user_id, phone_number, or email",
        )
    verify_privacy_subject_authorization(
        principal, user_id=user_id, email=email, phone_number=phone_number
    )
    return await RTBFManager.export_user_data(
        session, user_id=user_id, phone_number=phone_number, email=email
    )


@privacy_router.post("/export", response_model=DataExportResponse)
async def export_data_post(
    payload: DataExportRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> DataExportResponse:
    """Export all stored subject data in machine-readable format via POST."""
    if not any([payload.user_id, payload.phone_number, payload.email]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one of user_id, phone_number, or email",
        )
    verify_privacy_subject_authorization(
        principal,
        user_id=payload.user_id,
        email=payload.email,
        phone_number=payload.phone_number,
    )
    return await RTBFManager.export_user_data(
        session,
        user_id=payload.user_id,
        phone_number=payload.phone_number,
        email=payload.email,
    )


@privacy_router.post("/delete", response_model=DataDeletionResponse)
async def delete_data_post(
    payload: DataDeletionRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> DataDeletionResponse:
    """Erase and anonymize subject data pursuant to Right-To-Be-Forgotten."""
    if not any([payload.user_id, payload.phone_number, payload.email]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one of user_id, phone_number, or email",
        )
    verify_privacy_subject_authorization(
        principal,
        user_id=payload.user_id,
        email=payload.email,
        phone_number=payload.phone_number,
    )
    resp = await RTBFManager.delete_user_data(
        session,
        user_id=payload.user_id,
        phone_number=payload.phone_number,
        email=payload.email,
        reason=payload.reason,
    )
    await session.commit()
    return resp


@privacy_router.delete("/delete", response_model=DataDeletionResponse)
async def delete_data_delete(
    user_id: str | None = Query(None),
    phone_number: str | None = Query(None),
    email: str | None = Query(None),
    reason: str = Query("Right to be forgotten request"),
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> DataDeletionResponse:
    """Erase and anonymize subject data pursuant to Right-To-Be-Forgotten via DELETE."""
    if not any([user_id, phone_number, email]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must specify at least one of user_id, phone_number, or email",
        )
    verify_privacy_subject_authorization(
        principal, user_id=user_id, email=email, phone_number=phone_number
    )
    resp = await RTBFManager.delete_user_data(
        session,
        user_id=user_id,
        phone_number=phone_number,
        email=email,
        reason=reason,
    )
    await session.commit()
    return resp


# ---------------------------------------------------------------------------
# Retention Engine Endpoints
# ---------------------------------------------------------------------------


@privacy_router.get("/retention/policies", response_model=RetentionPolicyConfig)
async def get_retention_policies(
    principal: AuthPrincipal = Depends(require_api_principal),
) -> RetentionPolicyConfig:
    """Retrieve active data retention TTL policies by data class."""
    verify_admin_authorization(principal)
    return RetentionPolicyConfig(ttls_days=DEFAULT_DATA_RETENTION_TTLS)


@privacy_router.post("/retention/prune", response_model=RetentionPruneResponse)
async def prune_retention_records(
    payload: RetentionPruneRequest | None = None,
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> RetentionPruneResponse:
    """Execute automated retention lifecycle pruning by data class."""
    verify_admin_authorization(principal)
    req = payload or RetentionPruneRequest()
    resp = await DataRetentionEngine.prune_expired_records(
        session,
        custom_ttls=req.custom_ttls_days,
        dry_run=req.dry_run,
    )
    if not req.dry_run:
        await session.commit()
    return resp


# ---------------------------------------------------------------------------
# Telephony Consent & Disclosure Validation Endpoints
# ---------------------------------------------------------------------------


@privacy_router.post("/telephony/validate", response_model=TelephonyValidationResponse)
async def validate_telephony_post(
    payload: TelephonyValidationRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> TelephonyValidationResponse:
    """Validate whether an outbound or inbound call complies with consent and statutory disclosures."""
    verify_privacy_subject_authorization(
        principal,
        phone_number=payload.recipient_phone,
        project_id=payload.project_id,
    )
    return await TelephonyConsentValidator.validate_telephony_consent(
        session,
        recipient_phone=payload.recipient_phone,
        project_id=payload.project_id,
        require_recording_consent=payload.require_recording_consent,
        disclosure_acknowledged=payload.disclosure_acknowledged,
    )


@privacy_router.get("/telephony/validate", response_model=TelephonyValidationResponse)
async def validate_telephony_get(
    recipient_phone: str = Query(..., min_length=1),
    project_id: str | None = Query(None),
    require_recording_consent: bool = Query(True),
    disclosure_acknowledged: bool = Query(True),
    session: AsyncSession = Depends(get_db_session),
    principal: AuthPrincipal = Depends(require_api_principal),
) -> TelephonyValidationResponse:
    """Validate telephony consent via GET query parameters."""
    verify_privacy_subject_authorization(
        principal,
        phone_number=recipient_phone,
        project_id=project_id,
    )
    return await TelephonyConsentValidator.validate_telephony_consent(
        session,
        recipient_phone=recipient_phone,
        project_id=project_id,
        require_recording_consent=require_recording_consent,
        disclosure_acknowledged=disclosure_acknowledged,
    )
