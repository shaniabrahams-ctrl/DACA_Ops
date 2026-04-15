"""
Top-level API router — aggregates all v1 routes.
"""
from fastapi import APIRouter

from app.api.v1 import (
    health,
    daca_requests,
    borrowers,
    lenders,
    agreements,
    compliance,
    accounts,
    trigger_events,
    audit,
    human_review,
    oversight,
    reports,
    email_threads,
    email_drafts,
    documents,
)

api_router = APIRouter()

api_router.include_router(health.router, prefix="/v1", tags=["Health"])
api_router.include_router(daca_requests.router, prefix="/v1/daca-requests", tags=["DACA Requests"])
api_router.include_router(borrowers.router, prefix="/v1/borrowers", tags=["Borrowers"])
api_router.include_router(lenders.router, prefix="/v1/lenders", tags=["Lenders"])
api_router.include_router(agreements.router, prefix="/v1/agreements", tags=["Agreements"])
api_router.include_router(compliance.router, prefix="/v1/compliance", tags=["Compliance"])
api_router.include_router(accounts.router, prefix="/v1/accounts", tags=["Accounts"])
api_router.include_router(trigger_events.router, prefix="/v1/trigger-events", tags=["Trigger Events"])
api_router.include_router(audit.router, prefix="/v1/audit", tags=["Audit"])
api_router.include_router(human_review.router, prefix="/v1/reviews", tags=["Human Review"])
api_router.include_router(oversight.router, prefix="/v1/oversight", tags=["Oversight"])
api_router.include_router(reports.router, prefix="/v1/reports", tags=["Reports"])
api_router.include_router(email_threads.router, prefix="/v1/email-threads", tags=["Email Threads"])
api_router.include_router(email_drafts.router, prefix="/v1/email-drafts", tags=["Email Drafts"])
api_router.include_router(documents.router, prefix="/v1/documents", tags=["Documents"])
