"""
Auth Controller — with full input validation and sanitization.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import SESSION_COOKIE_NAME, SESSION_EXPIRE_DAYS
from models import CandidateProfile, EmployerProfile, NotificationType, User, UserRole
from services.auth import create_session, hash_password, verify_password
from services.notifications import create_notification

logger = logging.getLogger(__name__)

# ── Validation helpers ────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_SAFE_TEXT_RE = re.compile(r'[<>"\'\\;]')   # characters we strip from free-text fields


def _clean(value: str | None, max_len: int = 500) -> str:
    """Strip dangerous characters and trim to max_len."""
    if not value:
        return ""
    cleaned = _SAFE_TEXT_RE.sub("", value.strip())
    return cleaned[:max_len]


def _validate_email(email: str) -> str | None:
    """Return error string or None if valid."""
    if not email or len(email) > 254:
        return "Please enter a valid email address."
    if not _EMAIL_RE.match(email.strip()):
        return "Please enter a valid email address."
    return None


def _validate_password(password: str) -> str | None:
    """Return error string or None if valid."""
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 128:
        return "Password must be less than 128 characters."
    return None


def _reg_context(error: str, role: str, data: "RegisterForm") -> dict:
    """Return template context preserving filled fields on validation error."""
    return {
        "error": error, "role": role,
        "prev_email": _clean(data.email, 254),
        "prev_full_name": _clean(data.full_name),
        "prev_profession": _clean(data.profession),
        "prev_skills": _clean(data.skills),
        "prev_company_name": _clean(data.company_name),
        "prev_industry": _clean(data.industry),
        "prev_location": _clean(data.location),
    }


# ── Form dataclasses ──────────────────────────────────────────────────────────

@dataclass
class RegisterForm:
    email: str
    password: str
    confirm_password: str
    role: str
    full_name: str | None = None
    profession: str | None = None
    skills: str | None = None
    experience_years: int = 0
    bio: str | None = None
    company_name: str | None = None
    industry: str | None = None
    description: str | None = None
    location: str | None = None


@dataclass
class LoginForm:
    email: str
    password: str
    next: str = "/dashboard"


# ── Controller ────────────────────────────────────────────────────────────────

class AuthController(Controller):
    path = "/auth"

    # ── Registration ─────────────────────────────────────────────────────────

    @get("/register", include_in_schema=False)
    async def register_page(self, request: Request) -> Template:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            async with request.app.state.db_session() as db:
                from services.auth import get_user_by_token
                user = await get_user_by_token(db, token)
            if user:
                return Redirect("/dashboard")  # type: ignore[return-value]
        role = request.query_params.get("role", "CANDIDATE")
        return Template("auth/register.html", context={
            "error": None, "role": role,
            "prev_email": "", "prev_full_name": "", "prev_profession": "",
            "prev_skills": "", "prev_company_name": "", "prev_industry": "",
            "prev_location": "",
        })

    @post("/register", include_in_schema=False)
    async def register(
        self,
        request: Request,
        data: RegisterForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:

        role_str = _clean(data.role, 20).upper()
        ctx = lambda err: Template("auth/register.html", context=_reg_context(err, role_str, data))

        # ── Email validation ──
        email = data.email.strip().lower() if data.email else ""
        email_err = _validate_email(email)
        if email_err:
            return ctx(email_err)

        # ── Password validation ──
        pwd_err = _validate_password(data.password or "")
        if pwd_err:
            return ctx(pwd_err)

        if data.password != data.confirm_password:
            return ctx("Passwords do not match.")

        # ── Role validation ──
        try:
            role = UserRole(role_str)
        except ValueError:
            return ctx("Invalid role selected.")

        # ── Sanitize free-text fields ──
        full_name    = _clean(data.full_name, 255)
        profession   = _clean(data.profession, 255)
        skills       = _clean(data.skills, 1000)
        bio          = _clean(data.bio, 2000)
        company_name = _clean(data.company_name, 255) or "My Company"
        industry     = _clean(data.industry, 255)
        description  = _clean(data.description, 2000)
        location     = _clean(data.location, 255)

        # ── Role-specific required field validation ──
        if role == UserRole.CANDIDATE and not full_name:
            return ctx("Please enter your full name.")
        if role == UserRole.EMPLOYER and not company_name.strip():
            return ctx("Please enter your company name.")

        async with request.app.state.db_session() as db:
            existing = await db.execute(select(User).where(User.email == email))
            if existing.scalar_one_or_none():
                return ctx("That email address is already registered. Please sign in.")

            user = User(
                email=email,
                password_hash=hash_password(data.password),
                role=role,
            )
            db.add(user)
            await db.flush()

            if role == UserRole.CANDIDATE:
                try:
                    exp = max(0, min(int(data.experience_years or 0), 60))
                except (ValueError, TypeError):
                    exp = 0
                profile = CandidateProfile(
                    user_id=user.id, full_name=full_name,
                    profession=profession, skills=skills,
                    experience_years=exp, bio=bio,
                    is_searchable=True, is_open_to_work=True,
                )
                db.add(profile)
            else:
                profile = EmployerProfile(
                    user_id=user.id, company_name=company_name,
                    industry=industry, description=description, location=location,
                )
                db.add(profile)

            await db.flush()
            await create_notification(
                db, user.id, NotificationType.SYSTEM,
                title="Welcome to SmartRecruit!",
                body="Your account is ready. Complete your profile to get started.",
                link="/profile",
            )
            token = await create_session(db, user.id)
            await db.commit()

        redirect_url = "/dashboard/candidate" if role == UserRole.CANDIDATE else "/dashboard/employer"
        response = Redirect(redirect_url)
        response.set_cookie(
            SESSION_COOKIE_NAME, token,
            max_age=SESSION_EXPIRE_DAYS * 86400,
            httponly=True, samesite="lax",
        )
        return response  # type: ignore[return-value]

    # ── Login ─────────────────────────────────────────────────────────────────

    @get("/login", include_in_schema=False)
    async def login_page(self, request: Request) -> Template:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            async with request.app.state.db_session() as db:
                from services.auth import get_user_by_token
                user = await get_user_by_token(db, token)
            if user:
                return Redirect("/dashboard")  # type: ignore[return-value]
        next_url = _clean(request.query_params.get("next", "/dashboard"), 200)
        # Only allow relative URLs to prevent open redirect
        if not next_url.startswith("/"):
            next_url = "/dashboard"
        response = Template("auth/login.html", context={"error": None, "next": next_url})
        if token:
            response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    @post("/login", include_in_schema=False)
    async def login(
        self,
        request: Request,
        data: LoginForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:

        # Sanitize inputs
        email = (data.email or "").strip().lower()
        password = data.password or ""
        next_url = _clean(data.next, 200)
        if not next_url.startswith("/"):
            next_url = "/dashboard"

        # Generic error — never reveal whether email exists
        generic_err = "Invalid email or password."

        # Basic format check before hitting DB
        if not email or not _EMAIL_RE.match(email):
            return Template("auth/login.html", context={
                "error": generic_err, "next": next_url,
            })

        if not password or len(password) > 128:
            return Template("auth/login.html", context={
                "error": generic_err, "next": next_url,
            })

        async with request.app.state.db_session() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user or not verify_password(password, user.password_hash):
                return Template("auth/login.html", context={
                    "error": generic_err, "next": next_url,
                })

            if not user.is_active:
                return Template("auth/login.html", context={
                    "error": "This account has been disabled. Please contact support.",
                    "next": next_url,
                })

            token = await create_session(db, user.id)
            await db.commit()

        if user.role == UserRole.CANDIDATE:
            redirect_url = "/dashboard/candidate"
        elif user.role == UserRole.EMPLOYER:
            redirect_url = "/dashboard/employer"
        else:
            redirect_url = "/dashboard"

        response = Redirect(redirect_url)
        response.set_cookie(
            SESSION_COOKIE_NAME, token,
            max_age=SESSION_EXPIRE_DAYS * 86400,
            httponly=True, samesite="lax",
        )
        return response  # type: ignore[return-value]

    # ── Logout ────────────────────────────────────────────────────────────────

    @post("/logout", include_in_schema=False)
    async def logout(self, request: Request) -> Redirect:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            async with request.app.state.db_session() as db:
                from services.auth import delete_session
                await delete_session(db, token)
                await db.commit()
        response = Redirect("/")
        response.delete_cookie(SESSION_COOKIE_NAME)
        return response


# ── /dashboard redirect ───────────────────────────────────────────────────────

@get("/dashboard", include_in_schema=False)
async def dashboard_redirect(request: Request) -> Redirect:
    from services.auth import get_current_user
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return Redirect("/auth/login")
    async with request.app.state.db_session() as db:
        user = await get_current_user(request, db)
    if user is None:
        r = Redirect("/auth/login")
        r.delete_cookie(SESSION_COOKIE_NAME)
        return r
    if user.role == UserRole.CANDIDATE:
        return Redirect("/dashboard/candidate")
    if user.role == UserRole.EMPLOYER:
        return Redirect("/dashboard/employer")
    return Redirect("/")
