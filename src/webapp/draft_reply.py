"""
Draft a client-facing reply for a case, in the app.

Two modes, same output shape, so the flow works today and gets better with a key:
  - Template (always available): fills a per-type template with the case's own fields —
    a real, sendable starting draft, no external calls.
  - AI-polished (when ANTHROPIC_API_KEY is set): rewrites the template into natural prose
    using the same drafting rules as src/agents/email_drafter (grounded, plain-text,
    rep's name as sign-off, no invented facts).

HUMAN GATE (repo-wide): this only DRAFTS. The rep reviews/edits and sends via the case's
comms channel — nothing here contacts a client. No case content is persisted here.
"""

from __future__ import annotations
import os

from src.agents.email_drafter import DRAFTING_SYSTEM_BASE, EMAIL_TYPE_INSTRUCTIONS

# Draft types mirror the SOP's email macros (Notion "Rho DACA Process"), so a drafted
# reply matches the approved wording. Plus two generic helpers (status / follow-up).
TYPES = [
    ("intro_kickoff", "Intro / kick-off (send application)"),
    ("template_distribution", "Send Springing DACA template"),
    ("docusign_sent", "DocuSign sent"),
    ("execution_complete", "Fully executed — distribute"),
    ("status_update", "Status update"),
    ("follow_up", "Follow-up"),
]
_INSTRUCTIONS = {  # SOP intent per type, for the AI-polish pass
    "intro_kickoff": ("Warm first reply: introduce yourself as the client's Rho DACA contact, note "
                      "Rho offers Springing DACAs only (checking accounts only), send the DACA "
                      "request application (Typeform) link, and say the standard template follows "
                      "after initial review. Recommend a net-new DACA account. Don't invent details."),
    "template_distribution": ("Send the standard Springing DACA template for the client and lender to "
                              "review; note redlines are typically not accepted; next step is DocuSign "
                              "once all parties align."),
    "docusign_sent": ("Tell client + lender the DACA was sent via DocuSign (Rho Client Service, "
                      "contracts@docusign.rho.co), signing order Borrower → Lender → Rho → Webster, "
                      "Webster countersigns in 2–5 business days, then we distribute the executed copy."),
    "execution_complete": ("Confirm the DACA is fully signed by all parties; attach the executed copy; "
                           "note the client retains control unless a trigger event occurs."),
}
SENDSAFELY = "https://rho.sendsafely.com/dropzone/daca"
TYPEFORM = "https://t7w5kbgrsc2.typeform.com/to/f5xT4WRX"


def _first_name(person: str, email: str) -> str:
    if person:
        return person.split()[0].strip("(),")
    if email:
        return email.split("@")[0].split(".")[0].capitalize()
    return "there"


def _context(case, parties, last_note: str) -> dict:
    contact = next((p for p in parties if p.get("role") == "borrower_contact"), None)
    person = (contact or {}).get("person") or ""
    email = (contact or {}).get("email") or ""
    return {"entity": case.entity_legal_name, "stage": case.lifecycle_stage,
            "lender": case.lender_name or "", "next_action": case.next_action or "",
            "contact_first": _first_name(person, email), "note": last_note or ""}


def _template(email_type: str, ctx: dict, rep_name: str) -> str:
    hi = f"Hi {ctx['contact_first']},"
    hello = f"Hello {ctx['contact_first']},"
    best = f"\n\nBest,\n{rep_name}"
    sincerely = f"\n\nSincerely,\n{rep_name}"
    entity = ctx["entity"]
    if email_type == "intro_kickoff":  # SOP: DACA Intro / Process Kick-off
        return (f"{hi}\n\nIt's a pleasure to meet you! I'm {rep_name} on the Rho DACA team, and I'll "
                f"be assisting you with getting your DACA set up.\n\nPlease note that Rho supports "
                f"Springing DACAs only and does not offer fully blocked DACA products.\n\nTo begin, "
                f"please complete our DACA request application: {TYPEFORM}. This lets us collect "
                f"preliminary details and your lender's contact information.\n\nFollowing our initial "
                f"review, we'll share Rho's standard Springing DACA template for you and your lender "
                f"to review as the next step. We'd also recommend using a net-new account for the "
                f"DACA rather than your primary account.\n\nPlease don't hesitate to reach out with "
                f"any questions.{sincerely}")
    if email_type == "template_distribution":  # SOP Macro 1
        return (f"{hi}\n\nThank you for your patience while our team reviewed your request.\n\nI've "
                f"attached our Springing DACA template for you and your lender to review. As a "
                f"heads-up, we typically don't accept redlines or edits to this standard template. "
                f"Once everyone has reviewed it and is comfortable with the terms, we can move things "
                f"along.\n\nAfter we receive confirmation that all parties are aligned, we'll send the "
                f"agreement via DocuSign for execution. Once it's signed, we'll set up the account.\n\n"
                f"If any questions come up, feel free to reach out.{best}")
    if email_type == "docusign_sent":  # SOP DocuSign Sent macro
        return (f"{hello}\n\nThe DACA agreement has been sent via DocuSign from Rho Client Service "
                f"(contracts@docusign.rho.co). It will first route to the Borrower for signature, then "
                f"automatically to the Lender. Following the lender's signature, the agreement is "
                f"countersigned by Rho and then by our banking partner, Webster Bank — Webster is the "
                f"final signer, with a standard countersign time of 2–5 business days once received.\n\n"
                f"As soon as the fully executed agreement is back, we'll distribute it to all parties "
                f"and confirm the DACA account is operational.\n\nPlease let me know if you have any "
                f"questions.{sincerely}")
    if email_type == "execution_complete":  # SOP final distribution macro
        return (f"{hello}\n\nWe're pleased to confirm that the Deposit Account Control Agreement (DACA) "
                f"for {entity} has been fully signed by all parties. Attached is a copy of the fully "
                f"signed agreement for your records.\n\nThe DACA is now in effect with respect to the "
                f"account(s) identified in Schedule A. Unless and until a trigger event occurs pursuant "
                f"to the agreement, {entity} will continue to retain control of the account(s).\n\nThank "
                f"you for your cooperation throughout this process — please reach out to daca@rho.co "
                f"with any further questions.{sincerely}")
    if email_type == "status_update":
        return (f"{hi}\n\nA quick status update on your DACA: it's currently at the '{ctx['stage']}' "
                f"stage and we're actively working it. I'll follow up as soon as there's a next step "
                f"for you.{best}")
    return (f"{hi}\n\nFollowing up on your DACA to make sure nothing is blocked on our side. Let me "
            f"know if you have any questions — happy to help.{best}")


def _ai_polish(email_type: str, template: str, ctx: dict, rep_name: str) -> str | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        instr = _INSTRUCTIONS.get(email_type) or EMAIL_TYPE_INSTRUCTIONS.get(
            email_type, "Write a brief, professional follow-up grounded in the case.")
        user = (f"Case: {ctx['entity']} · stage {ctx['stage']}"
                + (f" · lender {ctx['lender']}" if ctx['lender'] else "")
                + (f"\nInbound from client: {ctx['note']}" if ctx['note'] else "")
                + f"\n\nTask: {instr}\nSign off as {rep_name}."
                + f"\n\nHere is a starting draft to improve (keep it grounded, plain text):\n{template}")
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model="claude-sonnet-5", max_tokens=900,
            system=DRAFTING_SYSTEM_BASE,
            messages=[{"role": "user", "content": user}])
        return resp.content[0].text.strip()
    except Exception:
        return None  # fall back to the template; never break the page


def draft_reply(case, parties: list[dict], last_note: str, email_type: str,
                rep_name: str = "Shani") -> dict:
    ctx = _context(case, parties, last_note)
    template = _template(email_type, ctx, rep_name)
    ai = _ai_polish(email_type, template, ctx, rep_name)
    return {"text": ai or template, "ai": ai is not None, "email_type": email_type}
