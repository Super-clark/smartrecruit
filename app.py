"""
Application Entry Point — SmartRecruit Platform
================================================
    python3 app.py
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from litestar import Litestar, Request, get
from litestar.config.cors import CORSConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.exceptions import NotFoundException, NotAuthorizedException
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin, RapidocRenderPlugin
from litestar.response import Redirect, Response, Template
from litestar.template import TemplateConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DATABASE_URL, RELOAD, SERVER_HOST, SERVER_PORT, SESSION_COOKIE_NAME
from controllers.auth import AuthController, dashboard_redirect
from controllers.candidates import CandidateController, candidate_dashboard
from controllers.employers import EmployerController, employer_dashboard
from controllers.jobs import JobsController
from controllers.applications import ApplicationsController
from controllers.notifications import NotificationsController
from controllers.ratings import RatingsController
from controllers.profiles import ProfilesController
from controllers.outreach import OutreachController, outreach_inbox, employer_outreach_view
from models import Base
from services.vector_search import ensure_collection

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_engine = create_async_engine(
    DATABASE_URL, echo=False, pool_size=10, max_overflow=20, pool_pre_ping=True,
)
_SessionFactory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with _SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def on_startup(app: Litestar) -> None:
    logger.info("Starting SmartRecruit…")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL tables ready.")
    try:
        await ensure_collection()
        logger.info("Qdrant collection ready.")
    except Exception as exc:
        logger.warning("Qdrant not reachable: %s", exc)
    app.state.db_session = db_session
    logger.info("Startup complete → http://%s:%s", SERVER_HOST, SERVER_PORT)


async def on_shutdown(app: Litestar) -> None:
    await _engine.dispose()
    logger.info("Shutdown complete.")


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def not_found_handler(request: Request, exc: NotFoundException) -> Response:
    """Return a plain 404 HTML page. Must be sync — Litestar calls it directly."""
    from litestar.response import Response as LitestarResponse
    html = f"""<!DOCTYPE html>
<html lang="en" style="background:#080f0f">
<head><meta charset="UTF-8"/><title>404 — SmartRecruit</title>
<script src="https://cdn.tailwindcss.com"></script></head>
<body style="background:#080f0f;color:#cbd5e1;min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;font-family:sans-serif">
  <div>
    <p style="font-size:5rem;font-weight:900;color:#14b8a6;text-shadow:0 0 60px rgba(20,184,166,.3);line-height:1">404</p>
    <h1 style="font-size:1.5rem;font-weight:700;color:#fff;margin:.75rem 0 .5rem">Page not found</h1>
    <p style="color:#475569;font-family:monospace;font-size:.85rem;margin-bottom:.5rem">{request.url.path}</p>
    <p style="color:#334155;font-size:.875rem;margin-bottom:2rem">{exc.detail or ''}</p>
    <a href="/" style="background:#14b8a6;color:#fff;padding:.6rem 1.75rem;border-radius:.5rem;font-weight:600;text-decoration:none;font-size:.9rem">← Back to Home</a>
  </div>
</body></html>"""
    return LitestarResponse(content=html.encode(), status_code=404, media_type="text/html")


def unauthorized_handler(request: Request, exc: NotAuthorizedException) -> Redirect:
    return Redirect(f"/auth/login?next={request.url.path}")


# ---------------------------------------------------------------------------
# Favicon (prevents 404 error loop in browser)
# ---------------------------------------------------------------------------

@get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    # Minimal teal SVG favicon
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><circle cx="16" cy="16" r="16" fill="#14b8a6"/><text x="16" y="22" text-anchor="middle" fill="white" font-size="18" font-family="Arial" font-weight="bold">S</text></svg>'
    return Response(content=svg, media_type="image/svg+xml")


# ---------------------------------------------------------------------------
# Landing & utility routes
# ---------------------------------------------------------------------------

@get("/", include_in_schema=False)
async def landing(request: Request) -> Template:    from services.auth import get_current_user
    from sqlalchemy import select
    from models import JobPost, EmployerProfile, CandidateProfile
    async with request.app.state.db_session() as db:
        user = await get_current_user(request, db)
        # Latest 6 active jobs for landing page preview
        jobs = (await db.execute(
            select(JobPost, EmployerProfile)
            .join(EmployerProfile, JobPost.employer_id == EmployerProfile.id)
            .where(JobPost.is_active.is_(True))
            .order_by(JobPost.created_at.desc())
            .limit(6)
        )).all()
        job_previews = [{"job": j, "employer": e} for j, e in jobs]

        total_candidates = len((await db.execute(
            select(CandidateProfile).where(CandidateProfile.is_searchable.is_(True))
        )).scalars().all())
        total_jobs = len((await db.execute(
            select(JobPost).where(JobPost.is_active.is_(True))
        )).scalars().all())
        total_employers = len((await db.execute(
            select(EmployerProfile)
        )).scalars().all())

    return Template("landing.html", context={
        "user": user,
        "job_previews": job_previews,
        "total_candidates": total_candidates,
        "total_jobs": total_jobs,
        "total_employers": total_employers,
    })


@get("/privacy", include_in_schema=False)
async def privacy_page(request: Request) -> Template:
    """Public privacy policy page."""
    from services.auth import get_current_user
    async with request.app.state.db_session() as db:
        user = await get_current_user(request, db)
    return Template("privacy.html", context={"user": user})


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> Litestar:
    base_dir = Path(__file__).parent

    return Litestar(
        route_handlers=[
            # Public
            landing,
            privacy_page,
            favicon,
            dashboard_redirect,
            # Auth
            AuthController,
            # Dashboards
            candidate_dashboard,
            employer_dashboard,
            # Feature controllers
            CandidateController,
            EmployerController,
            JobsController,
            ApplicationsController,
            NotificationsController,
            RatingsController,
            ProfilesController,
            OutreachController,
            outreach_inbox,
            employer_outreach_view,
        ],
        on_startup=[on_startup],
        on_shutdown=[on_shutdown],
        cors_config=CORSConfig(
            allow_origins=["*"],
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        ),
        openapi_config=OpenAPIConfig(
            title="SmartRecruit API",
            version="2.0.0",
            description="Smart recruitment platform. Candidate search at /candidates/search?q=...",
            render_plugins=[
                SwaggerRenderPlugin(path="/schema/swagger"),
                RapidocRenderPlugin(path="/schema/rapidoc"),
            ],
        ),
        template_config=TemplateConfig(
            directory=base_dir / "templates",
            engine=JinjaTemplateEngine,
        ),
        exception_handlers={
            NotFoundException: not_found_handler,          # type: ignore[dict-item]
            NotAuthorizedException: unauthorized_handler,  # type: ignore[dict-item]
        },
        logging_config=None,
    )


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    )
    uvicorn.run("app:app", host=SERVER_HOST, port=SERVER_PORT, reload=RELOAD, log_level="info")
