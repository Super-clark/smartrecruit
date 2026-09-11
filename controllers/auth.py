"""
Auth Controller
===============
Registration, login, logout — all server-rendered via Jinja2.

Routes
------
GET  /register          — show registration form
POST /register          — create account + profile
GET  /login             — show login form
POST /login             — authenticate + set session cookie
POST /logout            — destroy session cookie
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from litestar import Controller, Request, get, post
from litestar.datastructures import UploadFile
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MAX_AVATAR_BYTES, SESSION_COOKIE_NAME, SESSION_EXPIRE_DAYS
from models import CandidateProfile, EmployerProfile, User, UserRole
from services.auth import create_session, hash_password, verify_password
from services.notifications import create_notification
from models import NotificationType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Form dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RegisterForm:
    email: str
    password: str
    confirm_password: str
    role: str                        # "CANDIDATE" or "EMPLOYER"
    # Candidate fields
    full_name: str | None = None
    profession: str | None = None
    skills: str | None = None
    experience_years: int = 0
    bio: str | None = None
    # Employer fields
    company_name: str | None = None
    industry: str | None = None
    description: str | None = None
    location: str | None = None


@dataclass
class LoginForm:
    email: str
    password: str
    next: str = "/"


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class AuthController(Controller):
    path = "/auth"

    # ── Registration ────────────────────────────────────────────────────────

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
        return Template("auth/register.html", context={"error": None, "role": role})

    @post("/register", include_in_schema=False)
    async def register(
        self,
        request: Request,
        data: RegisterForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:
        async with request.app.state.db_session() as db:  # type: AsyncSession
            # Validation
            if data.password != data.confirm_password:
                return Template("auth/register.html", context={
                    "error": "Passwords do not match.", "role": data.role,
                })
            if len(data.password) < 8:
                return Template("auth/register.html", context={
                    "error": "Password must be at least 8 characters.", "role": data.role,
                })

            existing = await db.execute(select(User).where(User.email == data.email))
            if existing.scalar_one_or_none():
                return Template("auth/register.html", context={
                    "error": "Email already registered.", "role": data.role,
                })

            try:
                role = UserRole(data.role.upper())
            except ValueError:
                return Template("auth/register.html", context={
                    "error": "Invalid role selected.", "role": data.role,
                })

            # Create user
            user = User(
                email=data.email,
                password_hash=hash_password(data.password),
                role=role,
            )
            db.add(user)
            await db.flush()

            # Create profile
            if role == UserRole.CANDIDATE:
                profile = CandidateProfile(
                    user_id=user.id,
                    full_name=data.full_name or "",
                    profession=data.profession,
                    skills=data.skills,
                    experience_years=data.experience_years or 0,
                    bio=data.bio,
                    is_searchable=True,
                    is_open_to_work=True,
                )
                db.add(profile)
            else:
                profile = EmployerProfile(
                    user_id=user.id,
                    company_name=data.company_name or "My Company",
                    industry=data.industry,
                    description=data.description,
                    location=data.location,
                )
                db.add(profile)

            await db.flush()

            # Welcome notification
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
            httponly=True,
            samesite="lax",
        )
        return response  # type: ignore[return-value]

    # ── Login ────────────────────────────────────────────────────────────────

    @get("/login", include_in_schema=False)
    async def login_page(self, request: Request) -> Template:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            # Validate the token against the DB before trusting it
            async with request.app.state.db_session() as db:
                from services.auth import get_user_by_token
                user = await get_user_by_token(db, token)
            if user:
                return Redirect("/dashboard")  # type: ignore[return-value]
            # Token is stale (e.g. DB was wiped) — clear it and show login
        next_url = request.query_params.get("next", "/dashboard")
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
        async with request.app.state.db_session() as db:  # type: AsyncSession
            result = await db.execute(select(User).where(User.email == data.email))
            user = result.scalar_one_or_none()

            if not user or not verify_password(data.password, user.password_hash):
                return Template("auth/login.html", context={
                    "error": "Invalid email or password.", "next": data.next,
                })

            if not user.is_active:
                return Template("auth/login.html", context={
                    "error": "Account is disabled. Contact support.", "next": data.next,
                })

            token = await create_session(db, user.id)
            await db.commit()

        if user.role == UserRole.CANDIDATE:
            redirect_url = "/dashboard/candidate"
        elif user.role == UserRole.EMPLOYER:
            redirect_url = "/dashboard/employer"
        else:
            redirect_url = "/admin"

        response = Redirect(redirect_url)
        response.set_cookie(
            SESSION_COOKIE_NAME, token,
            max_age=SESSION_EXPIRE_DAYS * 86400,
            httponly=True,
            samesite="lax",
        )
        return response  # type: ignore[return-value]

    # ── Logout ───────────────────────────────────────────────────────────────

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


# Redirect /dashboard → role-specific dashboard
@get("/dashboard", include_in_schema=False)
async def dashboard_redirect(request: Request) -> Redirect:
    from services.auth import get_current_user
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return Redirect("/auth/login")
    async with request.app.state.db_session() as db:
        user = await get_current_user(request, db)
    if user is None:
        return Redirect("/auth/login")
    if user.role == UserRole.CANDIDATE:
        return Redirect("/dashboard/candidate")
    if user.role == UserRole.EMPLOYER:
        return Redirect("/dashboard/employer")
    return Redirect("/")
