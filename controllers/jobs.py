"""
Jobs Controller
===============
Routes
------
GET  /jobs                     — browse all active jobs (public)
GET  /jobs/{id:int}            — job detail (public)
POST /jobs/{id:int}/apply      — candidate applies
POST /jobs/{id:int}/bookmark   — candidate bookmarks
DELETE /jobs/{id:int}/bookmark — remove bookmark
POST /jobs/{id:int}/close      — employer closes job
GET  /jobs/my                  — employer's own job posts
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException, PermissionDeniedException
from litestar.params import Body
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import SESSION_COOKIE_NAME, DEFAULT_PAGE_SIZE
from models import (
    Application, ApplicationStatus, CandidateProfile,
    DirectOutreach, EmployerProfile, JobBookmark, JobPost,
    NotificationType, User, UserRole,
)
from services.auth import get_current_user, require_candidate, require_employer
from services.notifications import create_notification
from services.ratings import get_employer_rating

logger = logging.getLogger(__name__)


@dataclass
class ApplyForm:
    cover_letter: str | None = None


class JobsController(Controller):
    path = "/jobs"

    # ── Browse all jobs (public) ─────────────────────────────────────────────

    @get("/", include_in_schema=False)
    async def list_jobs(self, request: Request, page: int = 0, q: str = "") -> Template:
        async with request.app.state.db_session() as db:  # type: AsyncSession
            user = await get_current_user(request, db)

            query = (
                select(JobPost, EmployerProfile)
                .join(EmployerProfile, JobPost.employer_id == EmployerProfile.id)
                .where(JobPost.is_active.is_(True))
                .order_by(JobPost.created_at.desc())
            )
            if q:
                query = query.where(
                    JobPost.title.ilike(f"%{q}%") |
                    JobPost.description.ilike(f"%{q}%") |
                    JobPost.skills_required.ilike(f"%{q}%")
                )
            query = query.offset(page * DEFAULT_PAGE_SIZE).limit(DEFAULT_PAGE_SIZE)
            rows = (await db.execute(query)).all()

            # Bookmarks for current candidate
            bookmarked_ids: set[int] = set()
            applied_ids: set[int] = set()
            if user and user.role == UserRole.CANDIDATE:
                cp = (await db.execute(
                    select(CandidateProfile).where(CandidateProfile.user_id == user.id)
                )).scalar_one_or_none()
                if cp:
                    bm = (await db.execute(
                        select(JobBookmark.job_id).where(JobBookmark.candidate_id == cp.id)
                    )).scalars().all()
                    bookmarked_ids = set(bm)
                    ap = (await db.execute(
                        select(Application.job_id).where(Application.candidate_id == cp.id)
                    )).scalars().all()
                    applied_ids = set(ap)

            jobs = []
            for job, emp in rows:
                avg, cnt = await get_employer_rating(db, emp.id)
                jobs.append({
                    "job": job, "employer": emp,
                    "rating_avg": avg, "rating_count": cnt,
                    "bookmarked": job.id in bookmarked_ids,
                    "applied": job.id in applied_ids,
                })

        return Template("shared/jobs.html", context={
            "user": user, "jobs": jobs, "page": page,
            "q": q, "page_size": DEFAULT_PAGE_SIZE,
            "has_next": len(rows) == DEFAULT_PAGE_SIZE,
        })

    # ── Job detail ───────────────────────────────────────────────────────────

    @get("/{job_id:int}", include_in_schema=False)
    async def job_detail(self, request: Request, job_id: int) -> Template:
        async with request.app.state.db_session() as db:
            user = await get_current_user(request, db)
            job = await db.get(JobPost, job_id)
            if not job:
                raise NotFoundException(detail="Job not found.")

            employer = await db.get(EmployerProfile, job.employer_id)
            emp_user = await db.get(User, employer.user_id) if employer else None
            avg, cnt = await get_employer_rating(db, employer.id) if employer else (0.0, 0)

            bookmarked = False
            applied = False
            cp = None
            if user and user.role == UserRole.CANDIDATE:
                cp = (await db.execute(
                    select(CandidateProfile).where(CandidateProfile.user_id == user.id)
                )).scalar_one_or_none()
                if cp:
                    bm = (await db.execute(
                        select(JobBookmark).where(
                            JobBookmark.candidate_id == cp.id,
                            JobBookmark.job_id == job_id,
                        )
                    )).scalar_one_or_none()
                    bookmarked = bm is not None
                    ap = (await db.execute(
                        select(Application).where(
                            Application.candidate_id == cp.id,
                            Application.job_id == job_id,
                        )
                    )).scalar_one_or_none()
                    applied = ap is not None

        return Template("shared/job_detail.html", context={
            "user": user, "job": job, "employer": employer,
            "emp_user": emp_user, "rating_avg": avg, "rating_count": cnt,
            "bookmarked": bookmarked, "applied": applied,
        })

    # ── Apply ────────────────────────────────────────────────────────────────

    @post("/{job_id:int}/apply", include_in_schema=False)
    async def apply(
        self,
        request: Request,
        job_id: int,
        data: ApplyForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Redirect:
        async with request.app.state.db_session() as db:
            user, cp = await require_candidate(request, db)
            job = await db.get(JobPost, job_id)
            if not job or not job.is_active:
                raise NotFoundException(detail="Job not found or closed.")

            existing = (await db.execute(
                select(Application).where(
                    Application.candidate_id == cp.id,
                    Application.job_id == job_id,
                )
            )).scalar_one_or_none()
            if not existing:
                app = Application(
                    candidate_id=cp.id,
                    job_id=job_id,
                    cover_letter=data.cover_letter,
                    status=ApplicationStatus.APPLIED,
                )
                db.add(app)
                await db.flush()

                # Notify employer
                employer = await db.get(EmployerProfile, job.employer_id)
                if employer:
                    emp_user = await db.get(User, employer.user_id)
                    if emp_user:
                        await create_notification(
                            db, emp_user.id, NotificationType.APPLICATION,
                            title=f"New application for {job.title}",
                            body=f"{cp.full_name or user.email} applied for {job.title}.",
                            link=f"/applications/{app.id}",
                        )
            await db.commit()
        return Redirect(f"/jobs/{job_id}?applied=1")

    # ── Bookmark ─────────────────────────────────────────────────────────────

    @post("/{job_id:int}/bookmark", include_in_schema=False)
    async def bookmark(self, request: Request, job_id: int) -> Redirect:
        async with request.app.state.db_session() as db:
            user, cp = await require_candidate(request, db)
            existing = (await db.execute(
                select(JobBookmark).where(
                    JobBookmark.candidate_id == cp.id,
                    JobBookmark.job_id == job_id,
                )
            )).scalar_one_or_none()
            if not existing:
                db.add(JobBookmark(candidate_id=cp.id, job_id=job_id))
                await db.commit()
        return Redirect(f"/jobs/{job_id}")

    @post("/{job_id:int}/bookmark/remove", include_in_schema=False)
    async def remove_bookmark(self, request: Request, job_id: int) -> Redirect:
        async with request.app.state.db_session() as db:
            user, cp = await require_candidate(request, db)
            bm = (await db.execute(
                select(JobBookmark).where(
                    JobBookmark.candidate_id == cp.id,
                    JobBookmark.job_id == job_id,
                )
            )).scalar_one_or_none()
            if bm:
                await db.delete(bm)
                await db.commit()
        return Redirect(f"/jobs/{job_id}")

    # ── Close job (employer) ─────────────────────────────────────────────────

    @post("/{job_id:int}/close", include_in_schema=False)
    async def close_job(self, request: Request, job_id: int) -> Redirect:
        async with request.app.state.db_session() as db:
            user, emp = await require_employer(request, db)
            job = await db.get(JobPost, job_id)
            if not job or job.employer_id != emp.id:
                raise PermissionDeniedException(detail="Not your job post.")
            job.is_active = False
            db.add(job)
            await db.commit()
        return Redirect("/dashboard/employer")

    # ── Employer's job list ──────────────────────────────────────────────────

    @get("/my", include_in_schema=False)
    async def my_jobs(self, request: Request) -> Template:
        async with request.app.state.db_session() as db:
            user, emp = await require_employer(request, db)
            jobs = (await db.execute(
                select(JobPost)
                .where(JobPost.employer_id == emp.id)
                .order_by(JobPost.created_at.desc())
            )).scalars().all()

            # Application counts
            job_stats = []
            for job in jobs:
                cnt = len((await db.execute(
                    select(Application).where(Application.job_id == job.id)
                )).scalars().all())
                job_stats.append({"job": job, "applicant_count": cnt})

        return Template("employer/my_jobs.html", context={
            "user": user, "employer": emp, "job_stats": job_stats,
        })
