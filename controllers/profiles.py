"""
Profiles Controller
===================
Public social-media-style profile views + editable own profile pages.
Also handles avatar/CV upload and profile picture serving.

Routes
------
GET  /profile                        — redirect to own profile
GET  /profile/candidate/{id:int}     — public candidate profile
GET  /profile/employer/{id:int}      — public employer profile
GET  /profile/edit                   — edit own profile (GET)
POST /profile/edit                   — save own profile (POST)
GET  /profile/avatar/{user_id:int}   — serve avatar image
GET  /profile/cv/{candidate_id:int}  — download CV
POST /profile/outreach               — employer sends outreach from profile page
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException, PermissionDeniedException
from litestar.response import Redirect, Response, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MAX_AVATAR_BYTES, MAX_CV_BYTES, SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)
from models import (
    CandidateProfile, DirectOutreach, EmployerProfile, JobPost,
    NotificationType, OutreachStatus, User, UserRole,
)
from services.auth import get_current_user, require_user
from services.notifications import create_notification
from services.ratings import (
    get_candidate_rating, get_employer_rating,
    get_ratings_for_candidate, get_ratings_for_employer,
)

logger = logging.getLogger(__name__)


@dataclass
class CandidateProfileForm:
    full_name: str | None = None
    age: int | None = None
    birthday: str | None = None
    phone: str | None = None
    location: str | None = None
    bio: str | None = None
    title: str | None = None
    profession: str | None = None
    skills: str | None = None
    life_skills: str | None = None
    experience_years: int = 0
    education: str | None = None
    certifications: str | None = None
    languages: str | None = None
    expected_salary: str | None = None
    job_type_pref: str | None = None
    linkedin_url: str | None = None
    portfolio_url: str | None = None
    resume_text: str | None = None
    is_searchable: bool = True
    is_open_to_work: bool = True


@dataclass
class EmployerProfileForm:
    company_name: str = "My Company"
    industry: str | None = None
    company_size: str | None = None
    founded_year: int | None = None
    website: str | None = None
    description: str | None = None
    work_environment: str | None = None
    benefits: str | None = None
    work_mode: str | None = None
    location: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    linkedin_url: str | None = None


@dataclass
class OutreachForm:
    # Kept for reference — form is now parsed manually in send_outreach
    pass


class ProfilesController(Controller):
    path = "/profile"

    # ── Redirect own profile ─────────────────────────────────────────────────

    @get("/", include_in_schema=False)
    async def profile_redirect(self, request: Request) -> Redirect:
        async with request.app.state.db_session() as db:
            user = await get_current_user(request, db)
        if not user:
            return Redirect("/auth/login")
        if user.role == UserRole.CANDIDATE:
            async with request.app.state.db_session() as db:
                cp = (await db.execute(
                    select(CandidateProfile).where(CandidateProfile.user_id == user.id)
                )).scalar_one_or_none()
            return Redirect(f"/profile/candidate/{cp.id}" if cp else "/profile/edit")
        else:
            async with request.app.state.db_session() as db:
                ep = (await db.execute(
                    select(EmployerProfile).where(EmployerProfile.user_id == user.id)
                )).scalar_one_or_none()
            return Redirect(f"/profile/employer/{ep.id}" if ep else "/profile/edit")

    # ── Public candidate profile ─────────────────────────────────────────────

    @get("/candidate/{candidate_id:int}", include_in_schema=False)
    async def candidate_profile(self, request: Request, candidate_id: int) -> Template:
        try:
            async with request.app.state.db_session() as db:
                current_user = await get_current_user(request, db)
                cp = await db.get(CandidateProfile, candidate_id)
                if not cp:
                    raise NotFoundException(detail="Candidate not found.")
                cand_user = await db.get(User, cp.user_id)
                avg, cnt = await get_candidate_rating(db, candidate_id)
                reviews = await get_ratings_for_candidate(db, candidate_id, limit=10)

                # Eagerly read all fields needed by the template before session closes
                _ = cp.full_name, cp.title, cp.profession, cp.skills, cp.life_skills
                _ = cp.bio, cp.education, cp.certifications, cp.location
                _ = cp.experience_years, cp.expected_salary, cp.languages
                _ = cp.linkedin_url, cp.portfolio_url, cp.is_open_to_work
                _ = cp.is_searchable, cp.updated_at
                has_cv     = cp.cv_data is not None
                has_avatar = cp.avatar_data is not None

                review_data = [
                    {"score": r.score, "review": r.review, "created_at": r.created_at}
                    for r in reviews
                ]

                existing_outreach = None
                emp_profile = None
                if current_user and current_user.role == UserRole.EMPLOYER:
                    emp_profile = (await db.execute(
                        select(EmployerProfile).where(EmployerProfile.user_id == current_user.id)
                    )).scalar_one_or_none()
                    if emp_profile:
                        existing_outreach = (await db.execute(
                            select(DirectOutreach).where(
                                DirectOutreach.employer_id == emp_profile.id,
                                DirectOutreach.candidate_id == candidate_id,
                            ).limit(1)
                        )).scalar_one_or_none()
                        if existing_outreach:
                            _ = existing_outreach.id, existing_outreach.message
                            _ = existing_outreach.candidate_reply, existing_outreach.status
                        _ = emp_profile.id, emp_profile.company_name

                is_own = bool(current_user and current_user.id == cp.user_id)

            return Template("shared/profile_view.html", context={
                "user": current_user, "profile_type": "candidate",
                "candidate": cp, "profile_user": cand_user,
                "rating_avg": avg, "rating_count": cnt, "reviews": review_data,
                "existing_outreach": existing_outreach,
                "employer": emp_profile, "is_own": is_own,
                "has_avatar": has_avatar, "has_cv": has_cv,
            })
        except NotFoundException:
            raise
        except Exception as exc:
            logger.exception("candidate_profile error for id=%s: %s", candidate_id, exc)
            raise

    # ── Public employer profile ──────────────────────────────────────────────

    @get("/employer/{employer_id:int}", include_in_schema=False)
    async def employer_profile(self, request: Request, employer_id: int) -> Template:
        async with request.app.state.db_session() as db:
            current_user = await get_current_user(request, db)
            ep = await db.get(EmployerProfile, employer_id)
            if not ep:
                raise NotFoundException(detail="Employer not found.")
            emp_user = await db.get(User, ep.user_id)
            avg, cnt = await get_employer_rating(db, employer_id)
            reviews = await get_ratings_for_employer(db, employer_id, limit=10)

            # Eagerly read all fields
            _ = ep.company_name, ep.industry, ep.company_size, ep.description
            _ = ep.work_environment, ep.benefits, ep.work_mode, ep.location
            _ = ep.website, ep.founded_year, ep.linkedin_url
            _ = ep.contact_name, ep.contact_phone
            has_logo = ep.logo_data is not None

            review_data = [
                {"score": r.score, "review": r.review, "created_at": r.created_at}
                for r in reviews
            ]

            from models import JobPost as _JP
            job_rows = (await db.execute(
                select(_JP)
                .where(_JP.employer_id == employer_id)
                .where(_JP.is_active.is_(True))
                .order_by(_JP.created_at.desc())
                .limit(6)
            )).scalars().all()

            # Eagerly read job fields
            jobs = []
            for j in job_rows:
                _ = j.id, j.title, j.location, j.salary_range, j.work_mode
                jobs.append(j)

            is_own = current_user and current_user.id == ep.user_id

        return Template("shared/profile_view.html", context={
            "user": current_user, "profile_type": "employer",
            "employer": ep, "profile_user": emp_user,
            "rating_avg": avg, "rating_count": cnt, "reviews": review_data,
            "jobs": jobs, "is_own": is_own, "has_logo": has_logo,
        })

    # ── Edit own profile ─────────────────────────────────────────────────────

    @get("/edit", include_in_schema=False)
    async def edit_profile_page(self, request: Request) -> Template:
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)
            if user.role == UserRole.CANDIDATE:
                cp = (await db.execute(
                    select(CandidateProfile).where(CandidateProfile.user_id == user.id)
                )).scalar_one_or_none()
                return Template("candidate/profile.html", context={
                    "user": user, "profile": cp, "error": None, "success": None,
                })
            else:
                ep = (await db.execute(
                    select(EmployerProfile).where(EmployerProfile.user_id == user.id)
                )).scalar_one_or_none()
                return Template("employer/profile.html", context={
                    "user": user, "profile": ep, "error": None, "success": None,
                })

    @post("/edit", include_in_schema=False)
    async def save_profile(self, request: Request) -> Template | Redirect:
        form = await request.form()
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)

            if user.role == UserRole.CANDIDATE:
                cp = (await db.execute(
                    select(CandidateProfile).where(CandidateProfile.user_id == user.id)
                )).scalar_one_or_none()
                if not cp:
                    raise NotFoundException(detail="Profile not found.")

                cp.full_name       = form.get("full_name") or cp.full_name
                cp.age             = int(form.get("age") or 0) or cp.age
                cp.birthday        = form.get("birthday") or cp.birthday
                cp.phone           = form.get("phone") or cp.phone
                cp.location        = form.get("location") or cp.location
                cp.bio             = form.get("bio") or cp.bio
                cp.title           = form.get("title") or cp.title
                cp.profession      = form.get("profession") or cp.profession
                cp.skills          = form.get("skills") or cp.skills
                cp.life_skills     = form.get("life_skills") or cp.life_skills
                cp.experience_years = int(form.get("experience_years") or 0)
                cp.education       = form.get("education") or cp.education
                cp.certifications  = form.get("certifications") or cp.certifications
                cp.languages       = form.get("languages") or cp.languages
                cp.expected_salary = form.get("expected_salary") or cp.expected_salary
                cp.job_type_pref   = form.get("job_type_pref") or cp.job_type_pref
                cp.linkedin_url    = form.get("linkedin_url") or cp.linkedin_url
                cp.portfolio_url   = form.get("portfolio_url") or cp.portfolio_url
                cp.resume_text     = form.get("resume_text") or cp.resume_text
                cp.is_searchable   = form.get("is_searchable") == "on"
                cp.is_open_to_work = form.get("is_open_to_work") == "on"

                # Avatar upload
                avatar_file = form.get("avatar")
                if avatar_file and hasattr(avatar_file, "read"):
                    data = await avatar_file.read()
                    if len(data) > MAX_AVATAR_BYTES:
                        return Template("candidate/profile.html", context={
                            "user": user, "profile": cp,
                            "error": "Avatar must be under 2 MB.", "success": None,
                        })
                    if data:
                        cp.avatar_data = data
                        cp.avatar_mime = avatar_file.content_type or "image/jpeg"

                # CV upload
                cv_file = form.get("cv")
                if cv_file and hasattr(cv_file, "read"):
                    cv_data = await cv_file.read()
                    if len(cv_data) > MAX_CV_BYTES:
                        return Template("candidate/profile.html", context={
                            "user": user, "profile": cp,
                            "error": "CV must be under 10 MB.", "success": None,
                        })
                    if cv_data:
                        cp.cv_data     = cv_data
                        cp.cv_filename = cv_file.filename or "cv.pdf"
                        cp.cv_mime     = cv_file.content_type or "application/pdf"

                db.add(cp)
                await db.commit()

                # Re-index vector
                from services.vector_search import upsert_candidate_vector
                parts = filter(None, [cp.title, cp.profession, cp.skills, cp.resume_text])
                await upsert_candidate_vector(
                    cp.id, " ".join(parts),
                    payload={
                        "candidate_id": cp.id, "title": cp.title,
                        "skills": cp.skills, "experience_years": cp.experience_years,
                    }
                )

                return Template("candidate/profile.html", context={
                    "user": user, "profile": cp,
                    "error": None, "success": "Profile saved successfully!",
                })

            else:  # EMPLOYER
                ep = (await db.execute(
                    select(EmployerProfile).where(EmployerProfile.user_id == user.id)
                )).scalar_one_or_none()
                if not ep:
                    raise NotFoundException(detail="Profile not found.")

                ep.company_name     = form.get("company_name") or ep.company_name
                ep.industry         = form.get("industry") or ep.industry
                ep.company_size     = form.get("company_size") or ep.company_size
                ep.founded_year     = int(form.get("founded_year") or 0) or ep.founded_year
                ep.website          = form.get("website") or ep.website
                ep.description      = form.get("description") or ep.description
                ep.work_environment = form.get("work_environment") or ep.work_environment
                ep.benefits         = form.get("benefits") or ep.benefits
                ep.work_mode        = form.get("work_mode") or ep.work_mode
                ep.location         = form.get("location") or ep.location
                ep.contact_name     = form.get("contact_name") or ep.contact_name
                ep.contact_phone    = form.get("contact_phone") or ep.contact_phone
                ep.linkedin_url     = form.get("linkedin_url") or ep.linkedin_url

                # Logo upload
                logo_file = form.get("logo")
                if logo_file and hasattr(logo_file, "read"):
                    logo_data = await logo_file.read()
                    if len(logo_data) > MAX_AVATAR_BYTES:
                        return Template("employer/profile.html", context={
                            "user": user, "profile": ep,
                            "error": "Logo must be under 2 MB.", "success": None,
                        })
                    if logo_data:
                        ep.logo_data = logo_data
                        ep.logo_mime = logo_file.content_type or "image/jpeg"

                db.add(ep)
                await db.commit()

                return Template("employer/profile.html", context={
                    "user": user, "profile": ep,
                    "error": None, "success": "Profile saved successfully!",
                })

    # ── Serve avatar image ───────────────────────────────────────────────────

    @get("/avatar/{user_id:int}", include_in_schema=False)
    async def serve_avatar(self, request: Request, user_id: int) -> Response:
        async with request.app.state.db_session() as db:
            cp = (await db.execute(
                select(CandidateProfile).where(CandidateProfile.user_id == user_id)
            )).scalar_one_or_none()
            if cp and cp.avatar_data:
                return Response(
                    content=cp.avatar_data,
                    media_type=cp.avatar_mime or "image/jpeg",
                )
            # Try employer logo
            ep = (await db.execute(
                select(EmployerProfile).where(EmployerProfile.user_id == user_id)
            )).scalar_one_or_none()
            if ep and ep.logo_data:
                return Response(
                    content=ep.logo_data,
                    media_type=ep.logo_mime or "image/jpeg",
                )
        # Return a generic placeholder SVG
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><circle cx="40" cy="40" r="40" fill="#4c1d95"/><text x="40" y="55" text-anchor="middle" fill="white" font-size="36" font-family="Arial">?</text></svg>'
        return Response(content=svg, media_type="image/svg+xml")

    # ── Download CV ──────────────────────────────────────────────────────────

    @get("/cv/{candidate_id:int}", include_in_schema=False)
    async def download_cv(self, request: Request, candidate_id: int) -> Response:
        async with request.app.state.db_session() as db:
            await require_user(request, db)
            cp = await db.get(CandidateProfile, candidate_id)
            if not cp or not cp.cv_data:
                raise NotFoundException(detail="CV not available.")
        return Response(
            content=cp.cv_data,
            media_type=cp.cv_mime or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{cp.cv_filename or "cv.pdf"}"'},
        )

    # ── Send outreach from profile page ─────────────────────────────────────

    @post("/outreach", include_in_schema=False)
    async def send_outreach(
        self,
        request: Request,
    ) -> Redirect:
        """
        Send an outreach message from employer to candidate.
        Reads form data manually to handle optional integer fields safely.
        """
        async with request.app.state.db_session() as db:
            from services.auth import require_employer as _re
            user, emp = await _re(request, db)

            form = await request.form()
            message = form.get("message", "").strip()

            # Parse candidate_id — required
            try:
                candidate_id = int(form.get("candidate_id", ""))
            except (ValueError, TypeError):
                raise NotFoundException(detail="Invalid candidate ID.")

            # Parse job_id — optional
            job_id_raw = form.get("job_id", "")
            try:
                job_id: int | None = int(job_id_raw) if job_id_raw and str(job_id_raw).strip() not in ("", "None", "null") else None
            except (ValueError, TypeError):
                job_id = None

            cp = await db.get(CandidateProfile, candidate_id)
            if not cp:
                raise NotFoundException(detail="Candidate not found.")

            if not message:
                raise NotFoundException(detail="Message cannot be empty.")

            # Allow multiple messages — each creates a new outreach record
            outreach = DirectOutreach(
                employer_id=emp.id,
                candidate_id=candidate_id,
                job_id=job_id,
                message=message,
                status=OutreachStatus.PENDING,
            )
            db.add(outreach)
            await db.flush()

            cand_user = await db.get(User, cp.user_id)
            if cand_user:
                await create_notification(
                    db, cand_user.id, NotificationType.OUTREACH,
                    title=f"New message from {emp.company_name}",
                    body=message[:200],
                    link="/outreach/inbox",
                )
            await db.commit()

        # Redirect back to where we came from
        referrer = request.headers.get("referer", "")
        if "applications/employer" in referrer or "applicants" in referrer:
            return Redirect("/applications/employer")
        return Redirect(f"/profile/candidate/{candidate_id}?contacted=1")
