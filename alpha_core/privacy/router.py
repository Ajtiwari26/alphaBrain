import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.connection import get_db_session
from alpha_core.db.models import ConsentRecord, UserRecord
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


async def verify_privacy_subject_authorization(
    session: AsyncSession,
    principal: AuthPrincipal,
    user_id: str | None = None,
    email: str | None = None,
    phone_number: str | None = None,
    project_id: str | None = None,
) -> None:
    """
    Verify that the authenticated principal is authorized to access or modify subject data.
    - Founders, Admins, and Service principals have global privacy authorization.
    - Non-admin principals (Client / Worker) MUST be verified against ALL provided identifiers.
      Any provided identifier (user_id, email, phone_number) that cannot be confirmed as belonging
      to the authenticated user will result in immediate rejection (HTTP 403 Forbidden).
    """
    if principal.role in (PrincipalRole.FOUNDER, PrincipalRole.ADMIN, PrincipalRole.SERVICE):
        return

    # At least one subject identifier or valid project must be provided
    if not user_id and not email and not phone_number:
        if project_id and principal.project_ids and project_id in principal.project_ids:
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: no authorized subject identity anchor provided",
        )

    # Resolve authenticated principal's UserRecord if exists
    u_res = await session.execute(
        select(UserRecord).where(
            or_(UserRecord.id == principal.subject, UserRecord.email == principal.subject)
        )
    )
    auth_user = u_res.scalars().first()

    # 1. Verify user_id if provided
    if user_id:
        if user_id != principal.subject and (not auth_user or auth_user.id != user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: provided user_id does not match authenticated principal",
            )

    # 2. Verify email if provided
    if email:
        if email != principal.subject and (not auth_user or auth_user.email != email):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: provided email does not match authenticated principal",
            )

    # 3. Verify phone_number if provided
    if phone_number:
        if phone_number != principal.subject:
            # Check if this phone number is tied to the authenticated user's consents
            phone_found = False
            user_anchor_id = (
                auth_user.id
                if auth_user
                else (user_id if user_id == principal.subject else None)
            )
            if user_anchor_id:
                phone_q = select(ConsentRecord.id).where(
                    ConsentRecord.user_id == user_anchor_id,
                    ConsentRecord.phone_number == phone_number,
                )
                if (await session.execute(phone_q)).scalars().first():
                    phone_found = True

            if not phone_found:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: provided phone_number is not associated with authenticated principal",
                )

    # 4. Verify project_id if provided
    if project_id and principal.project_ids and project_id not in principal.project_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: principal is not authorized for the requested project",
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
    await verify_privacy_subject_authorization(
        session,
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
    await verify_privacy_subject_authorization(
        session,
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
    await verify_privacy_subject_authorization(
        session,
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
    await verify_privacy_subject_authorization(
        session,
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
    await verify_privacy_subject_authorization(
        session, principal, user_id=user_id, email=email, phone_number=phone_number
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
    await verify_privacy_subject_authorization(
        session,
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
    await verify_privacy_subject_authorization(
        session,
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
    await verify_privacy_subject_authorization(
        session, principal, user_id=user_id, email=email, phone_number=phone_number
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
    await verify_privacy_subject_authorization(
        session,
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
    await verify_privacy_subject_authorization(
        session,
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
