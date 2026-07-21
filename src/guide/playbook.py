"""
Guided-expert playbook (R11) — walk an ops rep through a DACA, per Rho's SOP.

Source of truth: the Notion "Rho DACA Process" SOP
(https://app.notion.com/p/245db9eba4f0800c816ccb5a02133f81), harvested rather than
invented (handoff R11 discipline). Each lifecycle stage maps to the SOP's steps: who
owns it, the actions/checklist, the documents, who to contact, which email macro to
send, and the "definition of done" that gates the next stage. When the SOP changes,
update this module (cross-check with the daca-doc-currency skill) — do not free-text
process advice without the SOP behind it.

Constitutionally-human steps (CFO signature, compliance attestation, legal redline,
trigger/termination, the actual Webster send) are guide-and-gate — the tool surfaces
the step and drafts, a human executes.
"""

from __future__ import annotations
from src.register.lifecycle import LifecycleStage

SOP_URL = "https://app.notion.com/p/245db9eba4f0800c816ccb5a02133f81"
TYPEFORM_URL = "https://t7w5kbgrsc2.typeform.com/to/f5xT4WRX"
SENDSAFELY_URL = "https://rho.sendsafely.com/dropzone/daca"
DACA_DRIVE_URL = "https://drive.google.com/drive/folders/121c4-xohOHgK8J_-vX-I-Mfoc7nTR3mX"
JIRA_CREATE_URL = "https://rho.atlassian.net/servicedesk/customer/portal/9/group/27/create/11920"

# Per-stage guide. `action` is a hint the UI turns into a button (draft:<type>,
# create_ticket, advance, external link). `macro` names the draft_reply type to use.
PLAYBOOK: dict[str, dict] = {
    LifecycleStage.INQUIRY.value: {
        "phase": "1 · Initial request",
        "who": "DACA DRI / CS",
        "do": [
            "Reply to the client and introduce the DACA team (CC daca@rho.co).",
            "Send the DACA request application (Typeform) — always call it the “DACA request application”, never a “survey/questionnaire”.",
            "Note that Rho offers Springing DACAs only (no fully-blocked), on checking accounts only.",
            "Recommend a net-new DACA account rather than their primary account.",
            "If the requester is a prospect, confirm standard Rho onboarding is completed first.",
        ],
        "docs": ["DACA request application (Typeform)"],
        "contacts": ["Client / borrower"],
        "macro": "intro_kickoff",
        "links": [("DACA request application (Typeform)", TYPEFORM_URL)],
        "done": "Client has completed the DACA request application (Typeform).",
        "next": "application_received",
    },
    LifecycleStage.APPLICATION_RECEIVED.value: {
        "phase": "1 · Team assignment",
        "who": "DACA DRI",
        "do": [
            "Create the DACA Jira ticket and tag in the Fraud team (first status: Fraud Initial Review).",
            "Update the tracker (this register) with the new case + Jira key.",
        ],
        "docs": ["Completed Typeform"],
        "contacts": ["Fraud team"],
        "macro": None,
        "links": [("Create DACA ticket (Jira portal)", JIRA_CREATE_URL)],
        "done": "Jira ticket created and Fraud tagged.",
        "next": "fraud_review",
        "primary_action": "create_ticket",
    },
    LifecycleStage.FRAUD_REVIEW.value: {
        "phase": "1 · Fraud review",
        "who": "Fraud team (DRI waits)",
        "do": [
            "Fraud performs the initial client review and comments on the Jira ticket when approved.",
            "No DRI action until Fraud approves — watch the ticket.",
        ],
        "docs": [],
        "contacts": ["Fraud team"],
        "macro": None,
        "links": [],
        "done": "Fraud approves on the Jira ticket.",
        "next": "templates_sent",
    },
    LifecycleStage.TEMPLATES_SENT.value: {
        "phase": "1 · Initial client comms",
        "who": "DACA DRI",
        "do": [
            "Evaluate the client against the redline-request guidelines.",
            "Send the standard Springing DACA template (attach the doc) — Macro 1 if redline-eligible, Macro 2 if not.",
            "Update Jira status to “Templates/Agreements Sent”.",
            "If redlines are requested: open a separate Legal (LEGALHELP) ticket linked to the DACA ticket, set status “Legal Redline Review”, and require tracked-changes Word (no PDFs).",
        ],
        "docs": ["Springing DACA template", "Loan agreement (optional, recommended)"],
        "contacts": ["Client + lender", "Legal (Sam Davidson) if redlines"],
        "macro": "template_distribution",
        "links": [],
        "done": "All parties confirm alignment on the template (or redlines accepted by Legal).",
        "next": "compliance_review",
    },
    LifecycleStage.REDLINE_REVIEW.value: {
        "phase": "1 · Legal redline",
        "who": "Legal (Sam Davidson)",
        "do": [
            "Route the client’s tracked-changes redline to Legal on a separate LEGALHELP ticket linked to the DACA ticket.",
            "Redlines must be accepted by Legal (and Webster where needed) before moving on.",
            "Redlines are limited — accommodate only for VIP / high-value / at-risk-of-churn, subject to Legal + Webster.",
        ],
        "docs": ["Client redline (tracked-changes Word)"],
        "contacts": ["Legal (Sam Davidson)", "Webster (via DRI) if needed"],
        "macro": None,
        "links": [],
        "done": "Legal accepts the redlines (or the client accepts the standard template).",
        "next": "compliance_review",
    },
    LifecycleStage.COMPLIANCE_REVIEW.value: {
        "phase": "2–3 · Docs + compliance package",
        "who": "Compliance (Vladan) assembles · DACA DRI reviews",
        "do": [
            "Download the Typeform + loan agreement and file them in a new client folder in the DACA Google Drive.",
            "Attach the Typeform PDF to the Jira ticket, tag Compliance, set status “Pending Compliance Package Assembly”.",
            "Compliance assembles the package; the DACA DRI reviews it before Webster submission.",
            "Submit the compliance packet to Webster BaaS (webster_rho_daca@, kjamison@, shickey@, stoliveira@websterbank.com; cc Mike + Jeff).",
            "You may begin agreement prep in parallel — no need to wait on Compliance.",
        ],
        "docs": ["Typeform PDF", "Loan agreement", "Compliance package"],
        "contacts": ["Compliance (Vladan)", "Webster BaaS"],
        "macro": None,
        "links": [("DACA Google Drive", DACA_DRIVE_URL), ("Secure upload (SendSafely)", SENDSAFELY_URL)],
        "done": "Compliance package assembled, DRI-reviewed, and submitted to Webster.",
        "next": "docusign",
    },
    LifecycleStage.DOCUSIGN.value: {
        "phase": "4 · Agreement prep + execution",
        "who": "DACA DRI",
        "do": [
            "Fill the DACA template: date, Debtor + Lender names/addresses (pp. 12–13), and Schedule A account number.",
            "Send DocuSign in the exact signing order: 1) Borrower → 2) Lender → 3) Rho CFO (Mike Szarowicz) → 4) Webster (Melissa Santos). Include Exhibit A for Lender as optional.",
            "Email the DocuSign-Sent macro to client + lender (cc the lender from the Typeform).",
            "Update Jira status to “Docusign Sent”; on receipt, “Pending Final Setup”.",
        ],
        "docs": ["Filled DACA agreement", "DocuSign envelope"],
        "contacts": ["Client + lender", "Rho CFO (Mike Szarowicz)", "Webster (Melissa Santos)"],
        "macro": "docusign_sent",
        "links": [],
        "done": "DACA fully executed by all four parties (Webster last, 2–5 business days).",
        "next": "final_setup",
    },
    LifecycleStage.FINAL_SETUP.value: {
        "phase": "5 · Account setup",
        "who": "DACA DRI",
        "do": [
            "New account: create the DACA clearing account in RAP, grab the account number, enter it in Schedule A, and deactivate until DocuSign is executed — then reactivate.",
            "Existing account: open an ENG ticket to convert the deposit account to a clearing account after signing.",
        ],
        "docs": ["Executed DACA agreement"],
        "contacts": ["Banking / ENG"],
        "macro": None,
        "links": [],
        "done": "Clearing account active in RAP.",
        "next": "active",
    },
    LifecycleStage.ACTIVE.value: {
        "phase": "5 · Finalization + ongoing",
        "who": "DACA DRI",
        "do": [
            "Upload the executed agreement to the DACA Google Drive.",
            "Complete the DACA fields in Salesforce.",
            "Distribute the fully-executed agreement to all parties (execution-complete macro), then mark the Jira ticket Done.",
            "Include this DACA in the monthly Rho↔Webster report.",
        ],
        "docs": ["Fully-executed DACA"],
        "contacts": ["Client + lender", "Webster (monthly report)"],
        "macro": "execution_complete",
        "links": [("DACA Google Drive", DACA_DRIVE_URL)],
        "done": "DACA operational, all documents filed, Jira Done.",
        "next": None,
    },
}

# Off-pipeline stages get a short note rather than a step ladder.
OFF_NOTES = {
    LifecycleStage.TERMINATED.value: "Terminated. Termination has a 1-business-day verification SLA and a Legal (LEGALHELP) review — see the SOP.",
    LifecycleStage.CANCELED.value: "Canceled / stalled. If the client re-engages, resume from where they left off.",
    LifecycleStage.REJECTED.value: "Rejected (e.g. Fraud declined or Webster declined the account).",
    LifecycleStage.ON_HOLD.value: "On hold — capture the reason and the trigger to resume.",
    LifecycleStage.CLOSED_UNRECONCILED.value: "Closed in Jira but not confirmed executed — reconcile against Drive / Salesforce before treating as active.",
}


def guide_for(stage_value: str) -> dict | None:
    return PLAYBOOK.get(stage_value)


def off_note_for(stage_value: str) -> str | None:
    return OFF_NOTES.get(stage_value)
