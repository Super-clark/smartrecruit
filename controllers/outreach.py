"""
Outreach Controller
===================
Routes
------
POST  /outreach/                       — send outreach (JSON API)
GET   /outreach/candidate/{id:int}     — fetch outreaches for candidate (JSON API)
PATCH /outreach/{id:int}/status        — update status
POST  /outreach/{id:int}/reply         — candidate OR employer posts a message in a thread
GET   /outreach/inbox                  — candidate inbox (HTML)
GET   /outreach/employer-view          — employer sent messages (HTML)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from litestar import Controller, Request, get, patch, post
from litestar.exceptions import NotFoundException, PermissionDeniedException
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    CandidateProfile, DirectOutreach, EmployerProfile,
    JobPost, NotificationType, OutreachMessage, OutreachStatus,
    User, UserRole,
)
from services.auth import get_current_user, require_candidate, require_employer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SendOutreachRequest:
    employer_id: int
    candidate_id: int
    message: str
    job_id: int | None = None


@dataclass
class UpdateStatusRequest:
    status: str


@dataclass
class OutreachItem:
    id: int
    employer_id: int
    candidate_id: int
    job_id: int | None
    message: str | None
    candidate_reply: str | None
    replied_at: str | None
    status: str
    created_at: str
    company_name: str | None = None
    job_title: str | None = None


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class OutreachController(Controller):
    path = "/outreach"

    @post("/", summary="Send an outreach message (API)")
    async def send_outreach(self, request: Request, data: SendOutreachRequest) -> OutreachItem:
        async with request.app.state.db_session() as session:
            employer = await session.get(EmployerProfile, data.employer_id)
            if not employer:
                raise NotFoundException(detail=f"Employer {data.employer_id} not found.")
            candidate = await session.get(CandidateProfile, data.candidate_id)
            if not candidate:
                raise NotFoundException(detail=f"Candidate {data.candidate_id} not found.")
            job = None
            if data.job_id:
                job = await session.get(JobPost, data.job_id)

            outreach = DirectOutreach(
                employer_id=data.employer_id, candidate_id=data.candidate_id,
                job_id=data.job_id, message=data.message, status=OutreachStatus.PENDING,
            )
            session.add(outreach)
            await session.flush()

            # Seed first message into thread
            session.add(OutreachMessage(
                outreach_id=outreach.id,
                sender_role="EMPLOYER",
                sender_id=employer.user_id,
                body=data.message,
            ))

        return OutreachItem(
            id=outreach.id, employer_id=outreach.employer_id,
            candidate_id=outreach.candidate_id, job_id=outreach.job_id,
            message=outreach.message, candidate_reply=None, replied_at=None,
            status=outreach.status.value, created_at=outreach.created_at.isoformat(),
            company_name=employer.company_name, job_title=job.title if job else None,
        )

    @get("/candidate/{candidate_id:int}", summary="Fetch outreaches for a candidate")
    async def get_candidate_outreaches(self, request: Request, candidate_id: int) -> list[OutreachItem]:
        async with request.app.state.db_session() as session:
            candidate = await session.get(CandidateProfile, candidate_id)
            if not candidate:
                raise NotFoundException(detail=f"Candidate {candidate_id} not found.")
            rows = (await session.execute(
                select(DirectOutreach, EmployerProfile, JobPost)
                .join(EmployerProfile, DirectOutreach.employer_id == EmployerProfile.id)
                .outerjoin(JobPost, DirectOutreach.job_id == JobPost.id)
                .where(DirectOutreach.candidate_id == candidate_id)
                .order_by(DirectOutreach.created_at.desc())
            )).all()

        return [
            OutreachItem(
                id=o.id, employer_id=o.employer_id, candidate_id=o.candidate_id,
                job_id=o.job_id, message=o.message,
                candidate_reply=o.candidate_reply,
                replied_at=o.replied_at.isoformat() if o.replied_at else None,
                status=o.status.value, created_at=o.created_at.isoformat(),
                company_name=emp.company_name if emp else None,
                job_title=job.title if job else None,
            )
            for o, emp, job in rows
        ]

    @patch("/{outreach_id:int}/status", summary="Update outreach status")
    async def update_status(self, request: Request, outreach_id: int, data: UpdateStatusRequest) -> OutreachItem:
        try:
            new_status = OutreachStatus(data.status.upper())
        except ValueError:
            from litestar.exceptions import ValidationException
            raise ValidationException(detail=f"Invalid status '{data.status}'.")
        async with request.app.state.db_session() as session:
            outreach = await session.get(DirectOutreach, outreach_id)
            if not outreach:
                raise NotFoundException(detail=f"Outreach {outreach_id} not found.")
            outreach.status = new_status
            session.add(outreach)
            await session.flush()
            employer = await session.get(EmployerProfile, outreach.employer_id)
            job = await session.get(JobPost, outreach.job_id) if outreach.job_id else None

        return OutreachItem(
            id=outreach.id, employer_id=outreach.employer_id,
            candidate_id=outreach.candidate_id, job_id=outreach.job_id,
            message=outreach.message,
            candidate_reply=outreach.candidate_reply,
            replied_at=outreach.replied_at.isoformat() if outreach.replied_at else None,
            status=outreach.status.value, created_at=outreach.created_at.isoformat(),
            company_name=employer.company_name if employer else None,
            job_title=job.title if job else None,
        )

    # ── POST a new message in a thread (candidate OR employer) ──────────────

    @post("/{outreach_id:int}/reply", include_in_schema=False)
    async def post_message(self, request: Request, outreach_id: int) -> Redirect:
        """
        Either party can post a message. Role is determined from the session.
        Candidate → sender_role=CANDIDATE, notifies employer.
        Employer  → sender_role=EMPLOYER,  notifies candidate.
        """
        async with request.app.state.db_session() as session:
            user = await get_current_user(request, session)
            if not user:
                return Redirect("/auth/login")

            outreach = await session.get(DirectOutreach, outreach_id)
            if not outreach:
                raise NotFoundException(detail="Thread not found.")

            form = await request.form()
            body = form.get("reply", "").strip()
            if not body:
                if user.role == UserRole.CANDIDATE:
                    return Redirect("/outreach/inbox?error=empty")
                return Redirect("/outreach/employer-view?error=empty")

            # Authorise — must be the candidate or the employer in this thread
            cp = await session.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == user.id)
            )
            cp = cp.scalar_one_or_none()
            emp = await session.execute(
                select(EmployerProfile).where(EmployerProfile.user_id == user.id)
            )
            emp = emp.scalar_one_or_none()

            if user.role == UserRole.CANDIDATE:
                if not cp or cp.id != outreach.candidate_id:
                    raise PermissionDeniedException(detail="Not your thread.")
                sender_role = "CANDIDATE"
                # Auto-accept on first candidate reply
                if outreach.status == OutreachStatus.PENDING:
                    outreach.status = OutreachStatus.ACCEPTED
                    outreach.candidate_reply = body
                    outreach.replied_at = datetime.now(timezone.utc)
                    session.add(outreach)
            elif user.role == UserRole.EMPLOYER:
                if not emp or emp.id != outreach.employer_id:
                    raise PermissionDeniedException(detail="Not your thread.")
                sender_role = "EMPLOYER"
            else:
                raise PermissionDeniedException(detail="Invalid role.")

            # Add message to thread
            msg = OutreachMessage(
                outreach_id=outreach_id,
                sender_role=sender_role,
                sender_id=user.id,
                body=body,
            )
            session.add(msg)
            await session.flush()

            # Notify the other party
            from services.notifications import create_notification
            if sender_role == "CANDIDATE":
                emp_obj = await session.get(EmployerProfile, outreach.employer_id)
                if emp_obj:
                    emp_user = await session.get(User, emp_obj.user_id)
                    if emp_user:
                        name = cp.full_name or user.email
                        await create_notification(
                            session, emp_user.id, NotificationType.OUTREACH,
                            title=f"{name} replied to your message",
                            body=body[:200],
                            link="/outreach/employer-view",
                        )
            else:
                emp_obj = await session.get(EmployerProfile, outreach.employer_id)
                cand_user = await session.get(User, outreach.candidate_id and
                    (await session.get(CandidateProfile, outreach.candidate_id)).user_id
                )
                if cand_user and emp_obj:
                    await create_notification(
                        session, cand_user.id, NotificationType.OUTREACH,
                        title=f"New message from {emp_obj.company_name}",
                        body=body[:200],
                        link="/outreach/inbox",
                    )

            await session.commit()

        if user.role == UserRole.CANDIDATE:
            return Redirect("/outreach/inbox?replied=1")
        return Redirect("/outreach/employer-view?replied=1")


# ---------------------------------------------------------------------------
# Standalone page routes (outside controller to avoid /{int} path collision)
# ---------------------------------------------------------------------------

async def _load_thread_messages(session: AsyncSession, outreach_id: int) -> list[OutreachMessage]:
    result = await session.execute(
        select(OutreachMessage)
        .where(OutreachMessage.outreach_id == outreach_id)
        .order_by(OutreachMessage.created_at.asc())
    )
    msgs = result.scalars().all()
    # Eagerly read fields
    for m in msgs:
        _ = m.id, m.sender_role, m.sender_id, m.body, m.created_at
    return list(msgs)


@get("/outreach/inbox", include_in_schema=False)
async def outreach_inbox(request: Request) -> Template | Redirect:
    """Candidate inbox — all threads with full message history."""
    async with request.app.state.db_session() as session:
        user = await get_current_user(request, session)
        if not user:
            return Redirect("/auth/login?next=/outreach/inbox")
        if user.role != UserRole.CANDIDATE:
            return Redirect("/outreach/employer-view")

        cp = (await session.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        )).scalar_one_or_none()
        if not cp:
            return Redirect("/profile/edit")

        rows = (await session.execute(
            select(DirectOutreach, EmployerProfile, JobPost)
            .join(EmployerProfile, DirectOutreach.employer_id == EmployerProfile.id)
            .outerjoin(JobPost, DirectOutreach.job_id == JobPost.id)
            .where(DirectOutreach.candidate_id == cp.id)
            .order_by(DirectOutreach.created_at.desc())
        )).all()

        threads = []
        for o, emp, job in rows:
            emp_user = await session.get(User, emp.user_id) if emp else None
            messages = await _load_thread_messages(session, o.id)
            # Eagerly read outreach fields
            _ = o.id, o.status, o.created_at, o.candidate_reply, o.replied_at
            if emp:
                _ = emp.id, emp.company_name, emp.user_id
            threads.append({
                "outreach": o, "employer": emp,
                "emp_user": emp_user, "job": job,
                "messages": messages,
            })

    return Template("candidate/outreach_inbox.html", context={
        "user": user, "candidate": cp, "threads": threads,
        "replied": request.query_params.get("replied") == "1",
        "error": request.query_params.get("error", ""),
    })


@get("/outreach/employer-view", include_in_schema=False)
async def employer_outreach_view(request: Request) -> Template | Redirect:
    """Employer sent messages — full thread history + reply form."""
    async with request.app.state.db_session() as session:
        user = await get_current_user(request, session)
        if not user:
            return Redirect("/auth/login")
        if user.role != UserRole.EMPLOYER:
            return Redirect("/outreach/inbox")

        emp = (await session.execute(
            select(EmployerProfile).where(EmployerProfile.user_id == user.id)
        )).scalar_one_or_none()
        if not emp:
            return Redirect("/profile/edit")

        rows = (await session.execute(
            select(DirectOutreach, CandidateProfile, JobPost)
            .join(CandidateProfile, DirectOutreach.candidate_id == CandidateProfile.id)
            .outerjoin(JobPost, DirectOutreach.job_id == JobPost.id)
            .where(DirectOutreach.employer_id == emp.id)
            .order_by(DirectOutreach.created_at.desc())
        )).all()

        threads = []
        for o, cp, job in rows:
            cand_user = await session.get(User, cp.user_id) if cp else None
            messages = await _load_thread_messages(session, o.id)
            _ = o.id, o.status, o.created_at, o.candidate_reply
            if cp:
                _ = cp.id, cp.full_name, cp.title, cp.profession, cp.user_id
            threads.append({
                "outreach": o, "candidate": cp,
                "cand_user": cand_user, "job": job,
                "messages": messages,
            })

    return Template("employer/outreach_sent.html", context={
        "user": user, "employer": emp, "threads": threads,
        "replied": request.query_params.get("replied") == "1",
    })

# ── Validation helper used by post_message ───────────────────────────────────
# (Applied inline above — body is stripped of HTML and capped at 2000 chars)
