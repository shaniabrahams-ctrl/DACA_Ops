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

# Human labels + the one type email_drafter doesn't cover: a brand-new inquiry.
TYPES = [
    ("new_inquiry", "Welcome / new inquiry"),
    ("outstanding_items", "Request outstanding items"),
    ("status_update", "Status update"),
    ("follow_up", "Follow-up"),
]
_NEW_INQUIRY_INSTRUCTION = (
    "Write a warm first reply to a client who just asked to set up a DACA. Introduce "
    "yourself as their Rho DACA contact, then ask them to confirm: the borrower legal "
    "entity + Rho account(s) to cover; the lender/secured party (legal name + contact) "
    "and the account being controlled; and to upload the loan/security agreement via the "
    "secure link. Offer a call. Do not invent entity, lender, or account details."
)
SENDSAFELY = "https://rho.sendsafely.com/dropzone/daca"


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
    sign = f"\n\nBest,\n{rep_name}"
    if email_type == "new_inquiry":
        hint = f" (re: {ctx['note']})" if ctx["note"] else ""
        return (f"{hi}\n\nThanks for reaching out about setting up a Deposit Account Control "
                f"Agreement (DACA). I'll be your point of contact on the Rho DACA team and will "
                f"help move this forward.\n\nTo get started, could you confirm:\n"
                f"  1. The borrower legal entity name(s) and the Rho account(s) the DACA should cover.\n"
                f"  2. The lender / secured party (legal name and a contact){hint}.\n"
                f"  3. The loan or security agreement — you can upload it securely here: {SENDSAFELY}\n\n"
                f"Once we have these, we'll prepare the agreement for signature. Happy to hop on a "
                f"quick call if that's easier.{sign}")
    if email_type == "outstanding_items":
        na = f"\n  - {ctx['next_action']}" if ctx["next_action"] else ""
        return (f"{hi}\n\nA quick update on your DACA. To keep things moving we still need the "
                f"following from you:{na or ' (see below)'}\n\nPlease send anything sensitive via "
                f"{SENDSAFELY}. Let me know if any of this is unclear.{sign}")
    if email_type == "status_update":
        return (f"{hi}\n\nWanted to give you a quick status update on your DACA. It's currently at "
                f"the '{ctx['stage']}' stage and we're actively working it. I'll follow up as soon "
                f"as there's a next step for you.{sign}")
    # follow_up / default
    return (f"{hi}\n\nFollowing up on your DACA to make sure nothing is blocked on our side. "
            f"Let me know if you have any questions — happy to help.{sign}")


def _ai_polish(email_type: str, template: str, ctx: dict, rep_name: str) -> str | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        instr = (_NEW_INQUIRY_INSTRUCTION if email_type == "new_inquiry"
                 else EMAIL_TYPE_INSTRUCTIONS.get(email_type, EMAIL_TYPE_INSTRUCTIONS["follow_up"]))
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
