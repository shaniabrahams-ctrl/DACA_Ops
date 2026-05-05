"""
Integration Celery tasks — Typeform sync, Ops Manual sync, Webster report generation.
"""
import asyncio
import logging
from datetime import datetime, timezone, date

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="app.tasks.integration_tasks.sync_typeform_responses")
def sync_typeform_responses():
    """
    Poll the Typeform Google Sheet for new responses (every 10 minutes).
    For each new response, create a DacaRequest + Borrower + Lender.
    """
    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.integrations.google_sheets import get_typeform_responses_since
        from app.models.typeform_submission import TypeformSubmission
        from app.models.borrower import Borrower
        from app.models.lender import Lender
        from app.services import daca_request_service
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            # Get last processed token
            last_result = await db.execute(
                select(TypeformSubmission)
                .order_by(TypeformSubmission.submitted_at.desc())
                .limit(1)
            )
            last = last_result.scalar_one_or_none()
            last_token = last.token if last else None

            responses = await get_typeform_responses_since(last_token)

            created = 0
            for row in responses:
                token = row.get("Token", "")
                if not token:
                    continue

                # Check if already processed
                existing = await db.execute(
                    select(TypeformSubmission).where(TypeformSubmission.token == token)
                )
                if existing.scalar_one_or_none():
                    continue

                # Create TypeformSubmission record
                submission = TypeformSubmission(
                    token=token,
                    lender_legal_name=row.get("Lender Legal Name", ""),
                    lender_business_address=row.get("Lender Business Address"),
                    lender_rep_count=int(row.get("How many lender reps", "1") or 1),
                    lender_rep_1_name=row.get("Lender Rep 1 Name"),
                    lender_rep_1_phone=row.get("Lender Rep 1 Phone"),
                    lender_rep_1_email=row.get("Lender Rep 1 Email"),
                    lender_rep_2_name=row.get("Lender Rep 2 Name"),
                    lender_rep_2_phone=row.get("Lender Rep 2 Phone"),
                    lender_rep_2_email=row.get("Lender Rep 2 Email"),
                    lender_rep_3_name=row.get("Lender Rep 3 Name"),
                    lender_rep_3_phone=row.get("Lender Rep 3 Phone"),
                    lender_rep_3_email=row.get("Lender Rep 3 Email"),
                    borrower_has_rho_account=row.get("Does borrower have a Rho account", "").lower() in ("yes", "true"),
                    borrower_legal_name=row.get("Borrower Legal Name", ""),
                    borrower_business_address=row.get("Borrower Business Address"),
                    borrower_contact_name=row.get("Borrower Contact Name"),
                    borrower_contact_email=row.get("Borrower Contact Email"),
                    loan_agreement_url=row.get("Loan Agreement URL"),
                    referral_source=row.get("Referral Source"),
                    government_receivables_involved=row.get("Government receivables involved", "").lower() in ("yes", "true"),
                    multiple_accounts_involved=row.get("Multiple accounts", "").lower() in ("yes", "true"),
                    preferred_transfer_method=row.get("Preferred transfer method"),
                    additional_info=row.get("Additional info"),
                    submitted_at=datetime.now(timezone.utc),
                )
                db.add(submission)
                await db.flush()

                # Create Lender record
                reps = []
                for i in range(1, 4):
                    name = row.get(f"Lender Rep {i} Name")
                    if name:
                        reps.append({
                            "name": name,
                            "phone": row.get(f"Lender Rep {i} Phone"),
                            "email": row.get(f"Lender Rep {i} Email"),
                        })

                lender = Lender(
                    institution_name=submission.lender_legal_name or "Unknown",
                    business_address=submission.lender_business_address,
                    rep_count=submission.lender_rep_count or 1,
                    representatives=reps or None,
                    primary_contact_email=reps[0]["email"] if reps else None,
                    primary_contact_phone=reps[0]["phone"] if reps else None,
                )
                db.add(lender)
                await db.flush()

                # Create Borrower record
                borrower = Borrower(
                    legal_name=submission.borrower_legal_name or "Unknown",
                    address={"raw": submission.borrower_business_address} if submission.borrower_business_address else None,
                    primary_contact_name=submission.borrower_contact_name,
                    primary_contact_email=submission.borrower_contact_email,
                    has_rho_account=submission.borrower_has_rho_account or False,
                )
                db.add(borrower)
                await db.flush()

                # Create DACA Request
                daca_req = await daca_request_service.create(
                    db,
                    actor_id="system:typeform_sync",
                    borrower_id=borrower.id,
                    lender_id=lender.id,
                    source_channel="TYPEFORM",
                    source_reference=token,
                    typeform_token=token,
                )

                # Link submission to request
                submission.daca_request_id = daca_req.id
                await db.flush()

                created += 1

            await db.commit()
            return {"new_submissions": created}

    return _run_async(_run())


@celery_app.task(name="app.tasks.integration_tasks.sync_ops_manual")
def sync_ops_manual():
    """
    Check Drive folder for new/updated Operations Manual files (runs weekly on Monday).
    Updates OpsManualVersion table — sets is_current=True for newest file.
    """
    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.integrations.google_drive import list_folder_files
        from app.models.ops_manual_version import OpsManualVersion
        from app.config import settings
        from sqlalchemy import select, update

        async with AsyncSessionLocal() as db:
            files = await list_folder_files(settings.drive_ops_manual_folder_id)
            if not files:
                return {"synced": 0}

            # Sort by modifiedTime descending — newest first
            newest = files[0]

            # Check if already tracked
            existing = await db.execute(
                select(OpsManualVersion).where(
                    OpsManualVersion.drive_file_id == newest["id"]
                )
            )
            if existing.scalar_one_or_none():
                return {"synced": 0, "note": "Already up to date"}

            # Mark all existing as not current
            await db.execute(
                update(OpsManualVersion).values(is_current=False)
            )

            # Create new version record
            version = OpsManualVersion(
                drive_file_id=newest["id"],
                drive_folder_id=settings.drive_ops_manual_folder_id,
                drive_file_name=newest["name"],
                version_label=newest["name"],
                fetched_at=datetime.now(timezone.utc),
                is_current=True,
            )
            db.add(version)
            await db.commit()
            return {"synced": 1, "version": newest["name"]}

    return _run_async(_run())


@celery_app.task(name="app.tasks.integration_tasks.generate_monthly_webster_report")
def generate_monthly_webster_report():
    """
    Generate monthly Webster Bank PDF + Excel report.
    Runs on the 1st of each month at 8AM ET.
    Reports are UPLOADED to Drive and a HumanReviewItem is created for approval
    before sending. Emails are NEVER auto-sent.
    """
    async def _run():
        from app.db.session import AsyncSessionLocal
        from app.services import human_review_service
        from app.services.webster_report_service import generate_excel, generate_pdf
        from app.integrations.google_drive import upload_file
        from app.config import settings
        from uuid import uuid4

        today = date.today()
        report_month = f"{today.strftime('%B')} {today.year}"

        async with AsyncSessionLocal() as db:
            # Generate both report formats via the service
            excel_bytes = await generate_excel(db)
            pdf_bytes = await generate_pdf(db)

            # Upload Excel to Drive
            excel_name = f"Webster DACA Report — {report_month}.xlsx"
            excel_drive_result = await upload_file(
                file_content=excel_bytes,
                file_name=excel_name,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                folder_id=settings.drive_webster_reports_folder_id,
            )

            # Upload PDF to Drive
            pdf_name = f"Webster DACA Report — {report_month}.pdf"
            pdf_drive_result = await upload_file(
                file_content=pdf_bytes,
                file_name=pdf_name,
                mime_type="application/pdf",
                folder_id=settings.drive_webster_reports_folder_id,
            )

            # Create human review item — operator must approve before emailing to Webster
            # Need a daca_request_id for the review item; use first active request or a system UUID
            from app.models.daca_request import DacaRequest, DacaRequestStatus
            from sqlalchemy import select

            result = await db.execute(
                select(DacaRequest.id)
                .where(DacaRequest.status.not_in([DacaRequestStatus.CANCELLED, DacaRequestStatus.TERMINATED]))
                .limit(1)
            )
            first_req = result.scalar_one_or_none()

            await human_review_service.create_review_item(
                db,
                daca_request_id=first_req if first_req else uuid4(),
                stage="MONTHLY_REPORT",
                review_type="QA_CHECK",
                payload={
                    "report_month": report_month,
                    "excel_drive_file_id": excel_drive_result.get("id"),
                    "excel_drive_url": excel_drive_result.get("webViewLink"),
                    "pdf_drive_file_id": pdf_drive_result.get("id"),
                    "pdf_drive_url": pdf_drive_result.get("webViewLink"),
                    "recipients": settings.webster_report_recipient_list,
                    "cc": settings.webster_report_cc_list,
                },
                agent_recommendation=f"Monthly Webster report generated for {report_month} (PDF + Excel). Review and approve to send.",
                agent_name="MonthlyReportTask",
            )

            await db.commit()
            return {
                "report_month": report_month,
                "excel_drive_url": excel_drive_result.get("webViewLink"),
                "pdf_drive_url": pdf_drive_result.get("webViewLink"),
            }

    return _run_async(_run())
