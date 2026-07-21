"""
Monthly Rho<>Webster DACAs report (R7) — the standing external obligation.

Every month Rho sends Webster Bank's BaaS team a list of the Active and In-progress
Rho<>Webster DACAs (the end-of-April 2026 report went out May 7). This module
generates that list — deterministically, from the case register — as the two
attachments Webster expects (an XLSX and a PDF) plus the covering email draft.

GROUNDING (daca-ops-tool SKILL.md §5): the report reproduces the "Rho<>Webster
DACAs List" sub-table in the DACA Summary sheet exactly:
    columns  #  ·  Rho ID (= Business ID)  ·  Business Name  ·  Status  ·  DACA Completion
    statuses Active / Blocked / In progress   (Canceled/Rejected/Terminated excluded)
where "Blocked" is an Active case whose funds are lender-controlled (a fully-blocked
DACA), and "In progress" is any case still moving through the pipeline.

DISCIPLINE:
  - No inference. Status comes from the register's typed lifecycle_stage +
    control_state; the completion date comes from the stored completion_date.
    A case that is Active in the register but carries no completion_date is shown
    Active with a BLANK completion cell (faithful to the register) — it is never
    back-filled with a guessed date.
  - Human gate. This module DRAFTS. It returns an email draft (recipients, subject,
    body) and writes the two files to a scratch path for review. It never sends —
    the Webster send is external-to-bank, the hardest gate in the whole tool.
  - View, don't store (daca-data-security skill). The generated files contain entity
    names (CONFIDENTIAL) and are written to a caller-supplied temp/scratch directory,
    never into git. The register is the only durable store.

The as-of date drives the report label, the filenames (month-end), and a completion
cutoff: a case whose completion_date is AFTER the as-of date was not yet a completed
Webster DACA as of that date, so it is excluded from that month's list (a factual
date comparison, not an inference about its historical stage).
"""

from __future__ import annotations
import calendar
from datetime import date, datetime
from typing import Optional

from src.register.db import Register, Case
from src.register.lifecycle import LifecycleStage, ControlState

# ── Reportable set (SKILL.md §5 + handoff) ────────────────────────────────────
# Active is bank-facing "Active"/"Blocked"; the in-flight stages are "In progress".
# Everything else (canceled, rejected, terminated, closed_unreconciled, on_hold,
# inquiry) is excluded from the bank list.
_ACTIVE_STAGES = {LifecycleStage.ACTIVE.value}
_INFLIGHT_STAGES = {
    LifecycleStage.APPLICATION_RECEIVED.value,
    LifecycleStage.FRAUD_REVIEW.value,
    LifecycleStage.TEMPLATES_SENT.value,
    LifecycleStage.REDLINE_REVIEW.value,
    LifecycleStage.COMPLIANCE_REVIEW.value,
    LifecycleStage.DOCUSIGN.value,
    LifecycleStage.FINAL_SETUP.value,
}
_REPORTABLE = _ACTIVE_STAGES | _INFLIGHT_STAGES

# ── Recipients (SKILL.md §5) — confirm the live distribution before any real send ─
WEBSTER_TO = [
    "stoliveira@websterbank.com",   # Sttefany Oliveira
    "shickey@websterbank.com",      # Sarah Hickey
    "kjamison@websterbank.com",     # Kevin Jamison
]
WEBSTER_CC = ["daca@rho.co"]

_MONTHS = ["", "January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _as_date(s: str | date) -> date:
    if isinstance(s, date):
        return s
    return date.fromisoformat(str(s)[:10])


def month_end(d: str | date) -> date:
    """Last calendar day of the month containing d."""
    d = _as_date(d)
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, last)


def month_year_label(d: str | date) -> str:
    """'April 2026' for the subject/body."""
    d = _as_date(d)
    return f"{_MONTHS[d.month]} {d.year}"


def bank_status(case: Case) -> str:
    """Map the register's two typed dimensions onto Webster's status vocabulary."""
    if case.lifecycle_stage in _ACTIVE_STAGES:
        if case.control_state == ControlState.LENDER_CONTROLLED.value:
            return "Blocked"        # fully-blocked DACA — funds lender-controlled
        return "Active"
    return "In progress"            # any in-flight pipeline stage


def select_cases(reg: Register, as_of: str | date) -> list[dict]:
    """
    Return the ordered rows for the Webster list as of `as_of`.

    Each row: {seq, rho_id, business_name, status, completion, case_id, flags}.
    Ordering mirrors the sheet sub-table: completed rows first, ascending by
    completion date; in-progress rows (no completion) last; ties broken by name.
    `seq` (the "#") is assigned after ordering.
    """
    as_of_d = month_end(as_of)
    rows: list[dict] = []
    for c in reg.all_cases():
        if c.lifecycle_stage not in _REPORTABLE:
            continue
        comp = c.completion_date
        # A DACA completed after the as-of month wasn't a completed Webster DACA yet.
        if comp and _as_date(comp) > as_of_d:
            # If it is still genuinely in-flight it would already be excluded above;
            # an Active case dated in the future relative to as_of is simply not yet
            # reportable for this month.
            continue
        rows.append({
            "case_id": c.case_id,
            "rho_id": c.business_id or c.case_id,
            "business_name": c.entity_legal_name,
            "status": bank_status(c),
            "completion": comp or "",
            "flags": list(c.flags or []),
        })

    rows.sort(key=lambda r: (r["completion"] or "9999-99-99", r["business_name"].lower()))
    for i, r in enumerate(rows, 1):
        r["seq"] = i
    return rows


def fmt_completion(iso: str) -> str:
    """'2023-09-13' -> 'Sep/13/2023' to match the sheet's display style. Blank stays blank."""
    if not iso:
        return ""
    try:
        d = _as_date(iso)
    except ValueError:
        return iso
    return f"{_MONTHS[d.month][:3]}/{d.day}/{d.year}"


REPORT_TITLE = "Rho<>Webster DACAs List"
COLUMNS = ["#", "Rho ID", "Business Name", "Status", "DACA Completion"]


def report_basename(as_of: str | date) -> str:
    """'Rho<>Webster DACAs List - 2026-04-30' (month-end date), per §5."""
    return f"{REPORT_TITLE} - {month_end(as_of).isoformat()}"


def _row_cells(r: dict) -> list:
    return [r["seq"], r["rho_id"], r["business_name"], r["status"], fmt_completion(r["completion"])]


def render_xlsx(rows: list[dict], path: str, as_of: str | date) -> str:
    """Write the list as an .xlsx. Plain single sheet matching the bank format."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Webster DACAs"

    thin = Side(style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Title + as-of banner (mirrors the sheet's "Rho<>Webster DACAs List / As of <date>")
    ws.append([REPORT_TITLE])
    ws.append([f"As of {fmt_completion(month_end(as_of).isoformat())}"])
    ws.append([])
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"].font = Font(italic=True, color="666666")

    header_row_idx = ws.max_row + 1
    ws.append(COLUMNS)
    for col in range(1, len(COLUMNS) + 1):
        cell = ws.cell(row=header_row_idx, column=col)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="0E1111")
        cell.alignment = Alignment(horizontal="left")
        cell.border = border

    for r in rows:
        ws.append(_row_cells(r))
        for col in range(1, len(COLUMNS) + 1):
            ws.cell(row=ws.max_row, column=col).border = border

    widths = [5, 10, 48, 14, 16]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[chr(64 + i)].width = w

    wb.save(path)
    return path


def render_pdf(rows: list[dict], path: str, as_of: str | date) -> str:
    """Write the list as a plain tabular PDF (ReportLab), matching the prior report's look."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("t", parent=styles["Title"], fontSize=15,
                                 alignment=0, spaceAfter=2)
    sub_style = ParagraphStyle("s", parent=styles["Normal"], fontSize=9,
                               textColor=colors.HexColor("#666666"), spaceAfter=10)
    cell_style = ParagraphStyle("c", parent=styles["Normal"], fontSize=8.5, leading=11)
    head_style = ParagraphStyle("h", parent=styles["Normal"], fontSize=8.5,
                                leading=11, textColor=colors.white, fontName="Helvetica-Bold")

    doc = SimpleDocTemplate(path, pagesize=letter,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.7 * inch,
                            title=report_basename(as_of))

    data = [[Paragraph(h, head_style) for h in COLUMNS]]
    for r in rows:
        cells = _row_cells(r)
        data.append([Paragraph(str(cells[0]), cell_style),
                     Paragraph(str(cells[1]), cell_style),
                     Paragraph(str(cells[2]), cell_style),
                     Paragraph(str(cells[3]), cell_style),
                     Paragraph(str(cells[4]), cell_style)])

    table = Table(data, colWidths=[0.4 * inch, 0.85 * inch, 3.7 * inch, 0.95 * inch, 1.2 * inch],
                  repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0E1111")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D9D9D9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F8F8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))

    story = [
        Paragraph(REPORT_TITLE, title_style),
        Paragraph(f"As of {fmt_completion(month_end(as_of).isoformat())}", sub_style),
        table,
    ]
    doc.build(story)
    return path


def draft_email(as_of: str | date, sender_name: str = "", sender_title: str = "") -> dict:
    """
    Build the covering email draft per SKILL.md §5. Returns a dict; DOES NOT SEND.
    Attachments are named by report_basename(as_of).
    """
    my = month_year_label(as_of)
    base = report_basename(as_of)
    sig = "\n\nRegards,"
    if sender_name:
        sig += f"\n{sender_name}"
    if sender_title:
        sig += f"\n{sender_title}"
    body = (
        "Hi Webster Team:\n\n"
        f"Please find attached the revised list of Active and In-progress Rho<>Webster "
        f"DACAs as of the end of {my}. Please let me know if you have any "
        f"questions/comments regarding this list."
        f"{sig}"
    )
    return {
        "to": list(WEBSTER_TO),
        "cc": list(WEBSTER_CC),
        "subject": f"Monthly Rho<>Webster DACAs List: end of {my}",
        "body": body,
        "attachments": [f"{base}.pdf", f"{base}.xlsx"],
        "notice": "DRAFT — external-to-bank send is a hard human gate. Review, then send manually.",
    }


def generate(reg: Register, as_of: str | date, out_dir: str,
             now_iso: Optional[str] = None, log_events: bool = True) -> dict:
    """
    Full R7 artifact bundle: select rows, render both files into out_dir, build the
    email draft, and (optionally) append a `report_generated` receipt event per case.

    Returns {as_of, month_year, rows, xlsx_path, pdf_path, email, flagged}.
    """
    import os
    as_of_d = month_end(as_of)
    rows = select_cases(reg, as_of_d)
    base = report_basename(as_of_d)
    xlsx_path = os.path.join(out_dir, f"{base}.xlsx")
    pdf_path = os.path.join(out_dir, f"{base}.pdf")
    os.makedirs(out_dir, exist_ok=True)

    render_xlsx(rows, xlsx_path, as_of_d)
    render_pdf(rows, pdf_path, as_of_d)
    email = draft_email(as_of_d)

    if log_events and now_iso:
        for r in rows:
            reg.append_event(
                r["case_id"], now_iso, "report:webster_monthly", "report_generated",
                field="webster_monthly", new_value=f"{base} [{r['status']}]",
                evidence_link="report:webster_monthly",
                idempotency_key=f"webrpt:{r['case_id']}:{as_of_d.isoformat()}")

    flagged = [r for r in rows if r["flags"]]
    return {
        "as_of": as_of_d.isoformat(),
        "month_year": month_year_label(as_of_d),
        "rows": rows,
        "xlsx_path": xlsx_path,
        "pdf_path": pdf_path,
        "email": email,
        "flagged": flagged,
    }
