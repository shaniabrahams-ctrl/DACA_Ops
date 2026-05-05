"""
Webster Report Service — generates PDF and Excel monthly reports for Webster Bank.

Report content: all active (non-cancelled/terminated) DACA requests with summary stats.
PDF uses WeasyPrint with Rho branding (blue #1F3864).
Excel uses openpyxl with styled header row.
"""
import logging
from datetime import date, datetime, timezone
from io import BytesIO

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daca_request import DacaRequest, DacaRequestStatus
from app.models.borrower import Borrower
from app.models.lender import Lender
from app.models.account import Account
from app.models.agreement import Agreement

logger = logging.getLogger(__name__)

# Statuses considered "active" (everything except cancelled/terminated)
_EXCLUDED_STATUSES = [DacaRequestStatus.CANCELLED, DacaRequestStatus.TERMINATED]


async def _fetch_report_rows(db: AsyncSession) -> list[dict]:
    """Fetch all active DACA requests with joined borrower/lender/account/agreement data."""
    result = await db.execute(
        select(DacaRequest)
        .where(DacaRequest.status.not_in(_EXCLUDED_STATUSES))
        .order_by(DacaRequest.created_at.desc())
    )
    requests = list(result.scalars().all())

    rows: list[dict] = []
    for req in requests:
        borrower_name = ""
        rho_id = ""
        lender_name = ""
        account_number = ""
        agreement_date = ""
        completion_date = ""

        if req.borrower_id:
            borrower = await db.get(Borrower, req.borrower_id)
            if borrower:
                borrower_name = borrower.legal_name or ""
                rho_id = borrower.rho_id or ""

        if req.lender_id:
            lender = await db.get(Lender, req.lender_id)
            if lender:
                lender_name = lender.institution_name or ""

        # Get primary account (first account linked to this request)
        acct_result = await db.execute(
            select(Account).where(Account.daca_request_id == req.id).limit(1)
        )
        account = acct_result.scalar_one_or_none()
        if account and account.account_number_encrypted:
            # Show last 4 digits only for security
            account_number = f"****{account.account_number_encrypted[-4:]}"

        # Get agreement dates
        agr_result = await db.execute(
            select(Agreement).where(Agreement.daca_request_id == req.id).limit(1)
        )
        agreement = agr_result.scalar_one_or_none()
        if agreement:
            if agreement.effective_date:
                agreement_date = agreement.effective_date.strftime("%Y-%m-%d")
            if agreement.signing_status == "COMPLETED" and agreement.webster_signed_at:
                completion_date = agreement.webster_signed_at.strftime("%Y-%m-%d")

        rows.append({
            "rho_id": rho_id,
            "business_name": borrower_name,
            "status": req.status or "",
            "lender": lender_name,
            "account_number": account_number,
            "initial_inquiry_date": req.created_at.strftime("%Y-%m-%d") if req.created_at else "",
            "agreement_date": agreement_date,
            "completion_date": completion_date,
            "jira_ticket": req.jira_ticket_key or "",
            "note": "",
        })

    return rows


def _compute_summary(rows: list[dict], report_month: str) -> dict:
    """Compute summary statistics for the report."""
    today = date.today()
    first_of_month = today.replace(day=1)

    total_active = len(rows)
    new_this_month = 0
    completed_this_month = 0
    pending_webster = 0

    for row in rows:
        # New this month: initial inquiry date is in the current month
        if row["initial_inquiry_date"]:
            try:
                inquiry_dt = datetime.strptime(row["initial_inquiry_date"], "%Y-%m-%d").date()
                if inquiry_dt >= first_of_month:
                    new_this_month += 1
            except ValueError:
                pass

        # Completed this month
        if row["completion_date"]:
            try:
                comp_dt = datetime.strptime(row["completion_date"], "%Y-%m-%d").date()
                if comp_dt >= first_of_month:
                    completed_this_month += 1
            except ValueError:
                pass

        # Pending Webster review
        if row["status"] == DacaRequestStatus.PRE_WEBSTER_REVIEW:
            pending_webster += 1

    return {
        "total_active": total_active,
        "new_this_month": new_this_month,
        "completed_this_month": completed_this_month,
        "pending_webster_review": pending_webster,
        "report_month": report_month,
    }


_REPORT_HEADERS = [
    "Rho ID", "Business Name", "Status", "Lender", "Account #",
    "Initial Inquiry Date", "Agreement Date", "Completion Date",
    "Jira Ticket", "Note",
]

_ROW_KEYS = [
    "rho_id", "business_name", "status", "lender", "account_number",
    "initial_inquiry_date", "agreement_date", "completion_date",
    "jira_ticket", "note",
]


async def generate_excel(db: AsyncSession) -> bytes:
    """Generate an Excel workbook with the monthly Webster Bank report."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    today = date.today()
    report_month = f"{today.strftime('%B')} {today.year}"

    rows = await _fetch_report_rows(db)
    summary = _compute_summary(rows, report_month)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"DACA Report {report_month}"

    header_fill = PatternFill("solid", fgColor="1F3864")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    title_font = Font(bold=True, size=14, color="1F3864")
    summary_label_font = Font(bold=True, size=11)
    summary_value_font = Font(size=11)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Title
    ws.merge_cells("A1:J1")
    title_cell = ws.cell(row=1, column=1, value=f"Webster Bank — DACA Monthly Report — {report_month}")
    title_cell.font = title_font
    title_cell.alignment = Alignment(horizontal="center")

    # Summary section
    summary_labels = [
        ("Total Active DACAs:", summary["total_active"]),
        ("New This Month:", summary["new_this_month"]),
        ("Completed This Month:", summary["completed_this_month"]),
        ("Pending Webster Review:", summary["pending_webster_review"]),
    ]
    for i, (label, value) in enumerate(summary_labels):
        row_num = 3 + i
        ws.cell(row=row_num, column=1, value=label).font = summary_label_font
        ws.cell(row=row_num, column=2, value=value).font = summary_value_font

    # Header row (row 8, leaving a gap after summary)
    header_row = 8
    for col, header in enumerate(_REPORT_HEADERS, 1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    # Data rows
    for row_idx, row_data in enumerate(rows, header_row + 1):
        for col_idx, key in enumerate(_ROW_KEYS, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=row_data[key])
            cell.border = thin_border

    # Auto-fit column widths (approximate)
    for col_idx, header in enumerate(_REPORT_HEADERS, 1):
        max_len = len(header)
        for row_data in rows:
            val = str(row_data[_ROW_KEYS[col_idx - 1]])
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = min(max_len + 4, 40)

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


async def generate_pdf(db: AsyncSession) -> bytes:
    """Generate a PDF report with the monthly Webster Bank data using WeasyPrint."""
    from weasyprint import HTML

    today = date.today()
    report_month = f"{today.strftime('%B')} {today.year}"

    rows = await _fetch_report_rows(db)
    summary = _compute_summary(rows, report_month)

    # Build HTML table rows
    table_rows_html = ""
    for row_data in rows:
        cells = "".join(f"<td>{row_data[key]}</td>" for key in _ROW_KEYS)
        table_rows_html += f"<tr>{cells}</tr>\n"

    if not rows:
        table_rows_html = (
            f'<tr><td colspan="{len(_REPORT_HEADERS)}" '
            f'style="text-align:center;padding:20px;">No active DACA requests.</td></tr>'
        )

    header_cells = "".join(f"<th>{h}</th>" for h in _REPORT_HEADERS)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{
        size: landscape;
        margin: 0.5in;
    }}
    body {{
        font-family: Arial, Helvetica, sans-serif;
        font-size: 10px;
        color: #333;
        margin: 0;
        padding: 0;
    }}
    .header {{
        background-color: #1F3864;
        color: white;
        padding: 20px 30px;
        margin-bottom: 20px;
    }}
    .header h1 {{
        margin: 0;
        font-size: 20px;
        font-weight: 700;
    }}
    .header .subtitle {{
        margin-top: 4px;
        font-size: 12px;
        opacity: 0.85;
    }}
    .branding {{
        font-size: 11px;
        opacity: 0.7;
        margin-top: 2px;
    }}
    .summary {{
        display: flex;
        margin: 0 10px 20px 10px;
    }}
    .summary-box {{
        background: #f0f4fa;
        border-left: 4px solid #1F3864;
        padding: 10px 18px;
        margin-right: 16px;
        min-width: 160px;
    }}
    .summary-box .label {{
        font-size: 9px;
        text-transform: uppercase;
        color: #666;
        margin-bottom: 2px;
    }}
    .summary-box .value {{
        font-size: 20px;
        font-weight: 700;
        color: #1F3864;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 0 10px;
    }}
    th {{
        background-color: #1F3864;
        color: white;
        padding: 8px 6px;
        text-align: left;
        font-size: 9px;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }}
    td {{
        padding: 6px;
        border-bottom: 1px solid #ddd;
        font-size: 9px;
    }}
    tr:nth-child(even) {{
        background-color: #f9fafe;
    }}
    .footer {{
        margin-top: 20px;
        padding: 10px;
        font-size: 8px;
        color: #999;
        text-align: center;
    }}
</style>
</head>
<body>
    <div class="header">
        <div class="branding">Rho</div>
        <h1>Webster Bank &mdash; DACA Monthly Report &mdash; {report_month}</h1>
        <div class="subtitle">Generated {today.strftime('%B %d, %Y')}</div>
    </div>

    <div class="summary">
        <div class="summary-box">
            <div class="label">Total Active DACAs</div>
            <div class="value">{summary['total_active']}</div>
        </div>
        <div class="summary-box">
            <div class="label">New This Month</div>
            <div class="value">{summary['new_this_month']}</div>
        </div>
        <div class="summary-box">
            <div class="label">Completed This Month</div>
            <div class="value">{summary['completed_this_month']}</div>
        </div>
        <div class="summary-box">
            <div class="label">Pending Webster Review</div>
            <div class="value">{summary['pending_webster_review']}</div>
        </div>
    </div>

    <table>
        <thead>
            <tr>{header_cells}</tr>
        </thead>
        <tbody>
            {table_rows_html}
        </tbody>
    </table>

    <div class="footer">
        Confidential &mdash; Prepared by Rho for Webster Bank &mdash; {report_month}
    </div>
</body>
</html>"""

    html_doc = HTML(string=html_content)
    return html_doc.write_pdf()
