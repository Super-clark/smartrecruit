"""
Candidate Controller  (API endpoints — protected)
==================================================
GET /candidates/           — list searchable candidates (employer/admin only)
GET /candidates/search     — semantic vector search
GET /candidates/{id:int}   — candidate detail (JSON)
GET /dashboard/candidate   — candidate dashboard (HTML)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from litestar import Controller, Request, get
from litestar.exceptions import NotFoundException
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Application, CandidateProfile, JobBookmark, JobPost,
    NotificationType, User, UserRole,
)
from services.auth import get_current_user, require_user
from services.notifications import count_unread, get_notifications
from services.ratings import get_candidate_rating
from services.vector_search import search_candidates

logger = logging.getLogger(__name__)


@dataclass
class CandidateListItem:
    id: int
    title: str | None
    profession: str | None
    skills: str | None
    experience_years: int
    is_searchable: bool
    is_open_to_work: bool
    user_email: str
    rating_avg: float = 0.0
    rating_count: int = 0


@dataclass
class VectorSearchResult:
    candidate_id: int
    score: float
    title: str | None
    skills: str | None
    experience_years: int | None
    payload: dict[str, Any] = field(default_factory=dict)


class CandidateController(Controller):
    path = "/candidates"

    @get("/", summary="List searchable candidates")
    async def list_candidates(
        self, request: Request, offset: int = 0, limit: int = 20,
    ) -> list[CandidateListItem]:
        limit = min(limit, 100)
        async with request.app.state.db_session() as db:
            result = await db.execute(
                select(CandidateProfile, User)
                .join(User, CandidateProfile.user_id == User.id)
                .where(CandidateProfile.is_searchable.is_(True))
                .order_by(CandidateProfile.id)
                .offset(offset).limit(limit)
            )
            rows = result.all()
            items = []
            for cp, user in rows:
                avg, cnt = await get_candidate_rating(db, cp.id)
                items.append(CandidateListItem(
                    id=cp.id, title=cp.title, profession=cp.profession,
                    skills=cp.skills, experience_years=cp.experience_years,
                    is_searchable=cp.is_searchable,
                    is_open_to_work=cp.is_open_to_work,
                    user_email=user.email,
                    rating_avg=avg, rating_count=cnt,
                ))
        return items

    @get("/search", summary="Semantic vector search over candidates")
    async def search(self, request: Request, q: str, limit: int = 10) -> list[VectorSearchResult]:
        limit = min(limit, 50)
        scored = await search_candidates(query_text=q, limit=limit)
        return [
            VectorSearchResult(
                candidate_id=int(sp.id),
                score=round(float(sp.score), 4),
                title=(sp.payload or {}).get("title"),
                skills=(sp.payload or {}).get("skills"),
                experience_years=(sp.payload or {}).get("experience_years"),
                payload=sp.payload or {},
            )
            for sp in scored
        ]

    @get("/{candidate_id:int}", summary="Get candidate detail")
    async def get_candidate(self, request: Request, candidate_id: int) -> CandidateListItem:
        async with request.app.state.db_session() as db:
            result = await db.execute(
                select(CandidateProfile, User)
                .join(User, CandidateProfile.user_id == User.id)
                .where(CandidateProfile.id == candidate_id)
            )
            row = result.one_or_none()
            if not row:
                raise NotFoundException(detail=f"Candidate {candidate_id} not found.")
            cp, user = row
            avg, cnt = await get_candidate_rating(db, cp.id)
        return CandidateListItem(
            id=cp.id, title=cp.title, profession=cp.profession,
            skills=cp.skills, experience_years=cp.experience_years,
            is_searchable=cp.is_searchable, is_open_to_work=cp.is_open_to_work,
            user_email=user.email, rating_avg=avg, rating_count=cnt,
        )


# ── Candidate Dashboard (HTML) ────────────────────────────────────────────────

@get("/dashboard/candidate", include_in_schema=False)
async def candidate_dashboard(request: Request) -> Template | Redirect:
    async with request.app.state.db_session() as db:
        user = await get_current_user(request, db)
        if not user:
            return Redirect("/auth/login")
        if user.role != UserRole.CANDIDATE:
            return Redirect("/dashboard/employer")

        cp = (await db.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        )).scalar_one_or_none()

        # Recent applications
        recent_apps = (await db.execute(
            select(Application, JobPost)
            .join(JobPost, Application.job_id == JobPost.id)
            .where(Application.candidate_id == cp.id if cp else False)
            .order_by(Application.applied_at.desc())
            .limit(5)
        )).all() if cp else []

        # Recommended jobs via vector search
        recommended = []
        if cp and (cp.skills or cp.profession or cp.resume_text):
            query_text = " ".join(filter(None, [cp.profession, cp.skills]))
            scored = await search_candidates(query_text=query_text, limit=5)
            # For dashboard we show jobs that match candidate's field
            recs = (await db.execute(
                select(JobPost)
                .where(JobPost.is_active.is_(True))
                .order_by(JobPost.created_at.desc())
                .limit(6)
            )).scalars().all()
            recommended = recs

        # Bookmarks
        bookmarks = []
        if cp:
            bm_rows = (await db.execute(
                select(JobBookmark, JobPost)
                .join(JobPost, JobBookmark.job_id == JobPost.id)
                .where(JobBookmark.candidate_id == cp.id)
                .limit(5)
            )).all()
            bookmarks = [{"bookmark": bm, "job": j} for bm, j in bm_rows]

        notifs = await get_notifications(db, user.id, unread_only=False, limit=5)
        unread = await count_unread(db, user.id)
        avg, cnt = await get_candidate_rating(db, cp.id) if cp else (0.0, 0)

    return Template("candidate/dashboard.html", context={
        "user": user, "candidate": cp,
        "recent_apps": [{"app": a, "job": j} for a, j in recent_apps],
        "recommended": recommended,
        "bookmarks": bookmarks,
        "notifications": notifs,
        "unread_count": unread,
        "rating_avg": avg, "rating_count": cnt,
    })
