"""
FastAPI application factory for DACA Operations Platform.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="DACA Operations Platform",
        description=(
            "Internal platform for managing Deposit Account Control Agreements "
            "between Rho, Webster Bank, Borrowers, and Lenders."
        ),
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS — allow the React frontend and local dev
    origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8080",
    ]
    if settings.app_env == "production":
        origins = ["https://daca-ops.rho.co"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
