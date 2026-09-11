"""
Employer Controller
===================
GET  /employers/           — list employers (public JSON)
GET  /employers/{id:int}   — employer detail (JSON)
POST /employers/jobs       — create job post (API)
GET  /dashboard/employer   — employer dashboard (HTML)
GET  /employers/post-job   — post job ad form (HTML)
POST /employers/post-job   — save new job ad
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException
from litestar.params import Body
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Application, CandidateProfile, EmployerProfile,
    JobPost, NotificationType, User, UserRole,
)
from services.auth import get_current_user, require_employer
from services.notifications import count_unread, get_notifications
from services.ratings import get_employer_rating
from services.vector_search import search_candidates

logger = logging.getLogger(__name__)


@dataclass
class EmployerListItem:
    id: int
    company_name: str
    industry: str | None
    user_email: str
    rating_avg: float = 0.0
    rating_count: int = 0


@dataclass
class CreateJobPostRequest:
    title: str
    description: str
    employer_id: int
    skills_required: str | None = None
    experience_min: int = 0
    job_type: str | None = None
    work_mode: str | None = None
    location: str | None = None
    salary_range: str | None = None
    industry: str | None = None
    is_active: bool = True


@dataclass
class PostJobForm:
    title: str
    description: str
    skills_required: str | None = None
    experience_min: int = 0
    job_type: str | None = None
    work_mode: str | None = None
    location: str | None = None
    salary_range: str | None = None
    industry: str | None = None


class EmployerController(Controller):
    path = "/employers"

    @get("/", summary="List all employers")
    async def list_employers(
        self, request: Request, offset: int = 0, limit: int = 20,
    ) -> list[EmployerListItem]:
        limit = min(limit, 100)
        async with request.app.state.db_session() as db:
            rows = (await db.execute(
                select(EmployerProfile, User)
                .join(User, EmployerProfile.user_id == User.id)
                .order_by(EmployerProfile.id)
                .offset(offset).limit(limit)
            )).all()
            items = []
            for ep, user in rows:
                avg, cnt = await get_employer_rating(db, ep.id)
                items.append(EmployerListItem(
                    id=ep.id, company_name=ep.company_name,
                    industry=ep.industry, user_email=user.email,
                    rating_avg=avg, rating_count=cnt,
                ))
        return items

    @get("/{employer_id:int}", summary="Get employer detail")
    async def get_employer(self, request: Request, employer_id: int) -> EmployerListItem:
        async with request.app.state.db_session() as db:
            row = (await db.execute(
                select(EmployerProfile, User)
                .join(User, EmployerProfile.user_id == User.id)
                .where(EmployerProfile.id == employer_id)
            )).one_or_none()
            if not row:
                raise NotFoundException(detail=f"Employer {employer_id} not found.")
            ep, user = row
            avg, cnt = await get_employer_rating(db, ep.id)
        return EmployerListItem(
            id=ep.id, company_name=ep.company_name,
            industry=ep.industry, user_email=user.email,
            rating_avg=avg, rating_count=cnt,
        )

    @post("/jobs", summary="Create a job post (API)")
    async def create_job_post_api(
        self, request: Request, data: CreateJobPostRequest,
    ) -> dict:
        async with request.app.state.db_session() as db:
            emp = await db.get(EmployerProfile, data.employer_id)
            if not emp:
                raise NotFoundException(detail=f"Employer {data.employer_id} not found.")
            job = JobPost(
                employer_id=data.employer_id, title=data.title,
                description=data.description, skills_required=data.skills_required,
                experience_min=data.experience_min, job_type=data.job_type,
                work_mode=data.work_mode, location=data.location,
                salary_range=data.salary_range, industry=data.industry,
                is_active=data.is_active,
            )
            db.add(job)
            await db.flush()
            await db.commit()
        return {"id": job.id, "title": job.title, "created": True}

    @get("/post-job", include_in_schema=False)
    async def post_job_page(self, request: Request) -> Template:
        async with request.app.state.db_session() as db:
            user, emp = await require_employer(request, db)
        return Template("employer/post_job.html", context={
            "user": user, "employer": emp, "error": None,
        })

    @post("/post-job", include_in_schema=False)
    async def post_job(
        self, request: Request,
        data: PostJobForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:
        async with request.app.state.db_session() as db:
            user, emp = await require_employer(request, db)
            if not data.title or not data.description:
                return Template("employer/post_job.html", context={
                    "user": user, "employer": emp,
                    "error": "Title and description are required.",
                })
            job = JobPost(
                employer_id=emp.id, title=data.title,
                description=data.description,
                skills_required=data.skills_required,
                experience_min=data.experience_min or 0,
                job_type=data.job_type, work_mode=data.work_mode,
                location=data.location, salary_range=data.salary_range,
                industry=data.industry, is_active=True,
            )
            db.add(job)
            await db.commit()
        return Redirect(f"/jobs/{job.id}?posted=1")


# ── Employer Dashboard (HTML) ─────────────────────────────────────────────────

@get("/dashboard/employer", include_in_schema=False)
async def employer_dashboard(request: Request) -> Template | Redirect:
    async with request.app.state.db_session() as db:
        user = await get_current_user(request, db)
        if not user:
            return Redirect("/auth/login")
        if user.role != UserRole.EMPLOYER:
            return Redirect("/dashboard/candidate")

        emp = (await db.execute(
            select(EmployerProfile).where(EmployerProfile.user_id == user.id)
        )).scalar_one_or_none()

        # Recent job posts with applicant counts
        job_rows = (await db.execute(
            select(JobPost)
            .where(JobPost.employer_id == emp.id if emp else False)
            .where(JobPost.is_active.is_(True))
            .order_by(JobPost.created_at.desc())
            .limit(5)
        )).scalars().all() if emp else []

        job_stats = []
        for job in job_rows:
            cnt = len((await db.execute(
                select(Application).where(Application.job_id == job.id)
            )).scalars().all())
            job_stats.append({"job": job, "applicant_count": cnt})

        # Recent applicants across all jobs
        recent_apps = []
        if emp:
            rows = (await db.execute(
                select(Application, JobPost, CandidateProfile)
                .join(JobPost, Application.job_id == JobPost.id)
                .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                .where(JobPost.employer_id == emp.id)
                .order_by(Application.applied_at.desc())
                .limit(5)
            )).all()
            recent_apps = [{"app": a, "job": j, "candidate": c} for a, j, c in rows]

        notifs = await get_notifications(db, user.id, unread_only=False, limit=5)
        unread = await count_unread(db, user.id)
        avg, cnt = await get_employer_rating(db, emp.id) if emp else (0.0, 0)

    return Template("employer/dashboard.html", context={
        "user": user, "employer": emp,
        "job_stats": job_stats,
        "recent_apps": recent_apps,
        "notifications": notifs,
        "unread_count": unread,
        "rating_avg": avg, "rating_count": cnt,
    })
