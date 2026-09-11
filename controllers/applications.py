"""
Applications Controller
=======================
Routes
------
GET  /applications                  — candidate: my applications
GET  /applications/employer         — employer: all applicants across jobs
GET  /applications/{id:int}         — detail view
POST /applications/{id:int}/status  — employer updates pipeline status
POST /applications/{id:int}/withdraw — candidate withdraws
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException, PermissionDeniedException
from litestar.params import Body
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Application, ApplicationStatus, CandidateProfile,
    EmployerProfile, JobPost, NotificationType, User,
)
from services.auth import get_current_user, require_candidate, require_employer
from services.notifications import create_notification

logger = logging.getLogger(__name__)

PIPELINE = [
    ApplicationStatus.APPLIED,
    ApplicationStatus.SCREENING,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.TEST,
    ApplicationStatus.OFFER,
    ApplicationStatus.ONBOARDED,
]


@dataclass
class StatusUpdateForm:
    status: str
    note: str | None = None


class ApplicationsController(Controller):
    path = "/applications"

    # ── Candidate: my applications ───────────────────────────────────────────

    @get("/", include_in_schema=False)
    async def my_applications(self, request: Request) -> Template:
        async with request.app.state.db_session() as db:
            user, cp = await require_candidate(request, db)
            rows = (await db.execute(
                select(Application, JobPost, EmployerProfile)
                .join(JobPost, Application.job_id == JobPost.id)
                .join(EmployerProfile, JobPost.employer_id == EmployerProfile.id)
                .where(Application.candidate_id == cp.id)
                .order_by(Application.applied_at.desc())
            )).all()

            apps = [
                {"app": a, "job": j, "employer": e}
                for a, j, e in rows
            ]
        return Template("candidate/applications.html", context={
            "user": user, "candidate": cp, "apps": apps, "pipeline": PIPELINE,
        })

    # ── Employer: all applicants ─────────────────────────────────────────────

    @get("/employer", include_in_schema=False)
    async def employer_applicants(
        self, request: Request, job_id: int | None = None
    ) -> Template:
        async with request.app.state.db_session() as db:
            user, emp = await require_employer(request, db)

            q = (
                select(Application, JobPost, CandidateProfile, User)
                .join(JobPost, Application.job_id == JobPost.id)
                .join(CandidateProfile, Application.candidate_id == CandidateProfile.id)
                .join(User, CandidateProfile.user_id == User.id)
                .where(JobPost.employer_id == emp.id)
                .order_by(Application.applied_at.desc())
            )
            if job_id:
                q = q.where(Application.job_id == job_id)

            rows = (await db.execute(q)).all()
            apps = [
                {"app": a, "job": j, "candidate": c, "cand_user": u}
                for a, j, c, u in rows
            ]

            # Job filter options
            jobs = (await db.execute(
                select(JobPost).where(JobPost.employer_id == emp.id)
            )).scalars().all()

        return Template("employer/applicants.html", context={
            "user": user, "employer": emp, "apps": apps,
            "jobs": jobs, "selected_job_id": job_id, "pipeline": PIPELINE,
        })

    # ── Detail ───────────────────────────────────────────────────────────────

    @get("/{app_id:int}", include_in_schema=False)
    async def application_detail(self, request: Request, app_id: int) -> Template:
        async with request.app.state.db_session() as db:
            current_user = await get_current_user(request, db)
            if not current_user:
                return Redirect("/auth/login")  # type: ignore[return-value]

            app = await db.get(Application, app_id)
            if not app:
                raise NotFoundException(detail="Application not found.")

            job      = await db.get(JobPost, app.job_id)
            employer = await db.get(EmployerProfile, job.employer_id) if job else None
            cp       = await db.get(CandidateProfile, app.candidate_id)
            cand_user = await db.get(User, cp.user_id) if cp else None

        return Template("shared/application_detail.html", context={
            "user": current_user, "app": app, "job": job,
            "employer": employer, "candidate": cp,
            "cand_user": cand_user, "pipeline": PIPELINE,
        })

    # ── Employer: update status ──────────────────────────────────────────────

    @post("/{app_id:int}/status", include_in_schema=False)
    async def update_status(
        self,
        request: Request,
        app_id: int,
        data: StatusUpdateForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Redirect:
        async with request.app.state.db_session() as db:
            user, emp = await require_employer(request, db)
            app = await db.get(Application, app_id)
            if not app:
                raise NotFoundException(detail="Application not found.")

            job = await db.get(JobPost, app.job_id)
            if not job or job.employer_id != emp.id:
                raise PermissionDeniedException(detail="Not your applicant.")

            try:
                app.status = ApplicationStatus(data.status.upper())
            except ValueError:
                raise PermissionDeniedException(detail="Invalid status.")

            if data.note:
                app.employer_note = data.note
            db.add(app)

            # Notify candidate
            cp = await db.get(CandidateProfile, app.candidate_id)
            if cp:
                cand_user = await db.get(User, cp.user_id)
                if cand_user:
                    await create_notification(
                        db, cand_user.id, NotificationType.STATUS_CHANGE,
                        title=f"Application update: {job.title}",
                        body=f"Your application status changed to {app.status.value}.",
                        link=f"/applications/{app.id}",
                    )
            await db.commit()
        return Redirect(f"/applications/employer?job_id={job.id}")

    # ── Candidate: withdraw ──────────────────────────────────────────────────

    @post("/{app_id:int}/withdraw", include_in_schema=False)
    async def withdraw(self, request: Request, app_id: int) -> Redirect:
        async with request.app.state.db_session() as db:
            user, cp = await require_candidate(request, db)
            app = await db.get(Application, app_id)
            if not app or app.candidate_id != cp.id:
                raise PermissionDeniedException(detail="Not your application.")
            app.status = ApplicationStatus.WITHDRAWN
            db.add(app)
            await db.commit()
        return Redirect("/applications")
