"""
Auth Controller
===============
Routes
------
GET  /auth/register              — registration form
POST /auth/register              — create email account
GET  /auth/login                 — login form
POST /auth/login                 — authenticate
POST /auth/logout                — destroy session

GET  /auth/google                — redirect to Google consent screen
GET  /auth/google/callback       — Google returns here
GET  /auth/google/role           — role selection after Google signup
POST /auth/google/role           — save role, finish Google signup

GET  /auth/forgot-password       — forgot password form
POST /auth/forgot-password       — send reset email
GET  /auth/reset-password        — new password form (from email link)
POST /auth/reset-password        — save new password
"""

from __future__ import annotations

import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.params import Body
from litestar.response import Redirect, Template
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import (
    RESET_TOKEN_EXPIRE_HOURS, SESSION_COOKIE_NAME, SESSION_EXPIRE_DAYS,
)
from models import (
    CandidateProfile, EmployerProfile, NotificationType, User, UserRole,
)
from services.auth import create_session, hash_password, verify_password
from services.email import send_password_reset_email
from services.notifications import create_notification

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_SAFE_RE  = re.compile(r'[<>"\'\\;]')


def _clean(v: str | None, n: int = 500) -> str:
    return _SAFE_RE.sub("", (v or "").strip())[:n]


def _ok_email(e: str) -> bool:
    return bool(e) and len(e) <= 254 and bool(_EMAIL_RE.match(e))


def _set_session_cookie(response: Redirect | Template, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME, token,
        max_age=SESSION_EXPIRE_DAYS * 86400,
        httponly=True, samesite="lax",
    )


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


@dataclass
class ForgotPasswordForm:
    email: str


@dataclass
class ResetPasswordForm:
    token: str
    password: str
    confirm_password: str


@dataclass
class RoleSelectForm:
    role: str
    full_name: str | None = None
    company_name: str | None = None


# ── Helper: create profile after account creation ────────────────────────────

async def _create_profile(db: AsyncSession, user: User, role: UserRole,
                           full_name: str = "", company_name: str = "My Company",
                           profession: str | None = None, skills: str | None = None,
                           exp: int = 0, bio: str | None = None,
                           industry: str | None = None, location: str | None = None) -> None:
    if role == UserRole.CANDIDATE:
        db.add(CandidateProfile(
            user_id=user.id, full_name=full_name, profession=profession,
            skills=skills, experience_years=exp, bio=bio,
            is_searchable=True, is_open_to_work=True,
        ))
    else:
        db.add(EmployerProfile(
            user_id=user.id, company_name=company_name or "My Company",
            industry=industry, location=location,
        ))
    await create_notification(
        db, user.id, NotificationType.SYSTEM,
        title="Welcome to SmartRecruit!",
        body="Your account is ready. Complete your profile to get started.",
        link="/profile",
    )


# ── Controller ────────────────────────────────────────────────────────────────

class AuthController(Controller):
    path = "/auth"

    # ── Register ──────────────────────────────────────────────────────────────

    @get("/register", include_in_schema=False)
    async def register_page(self, request: Request) -> Template:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            async with request.app.state.db_session() as db:
                from services.auth import get_user_by_token
                if await get_user_by_token(db, token):
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
        self, request: Request,
        data: RegisterForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:
        role_str = _clean(data.role, 20).upper()

        def ctx(err: str) -> Template:
            return Template("auth/register.html", context={
                "error": err, "role": role_str,
                "prev_email": _clean(data.email, 254),
                "prev_full_name": _clean(data.full_name),
                "prev_profession": _clean(data.profession),
                "prev_skills": _clean(data.skills),
                "prev_company_name": _clean(data.company_name),
                "prev_industry": _clean(data.industry),
                "prev_location": _clean(data.location),
            })

        email = (data.email or "").strip().lower()
        if not _ok_email(email):
            return ctx("Please enter a valid email address.")
        if not data.password or len(data.password) < 8:
            return ctx("Password must be at least 8 characters.")
        if len(data.password) > 128:
            return ctx("Password must be less than 128 characters.")
        if data.password != data.confirm_password:
            return ctx("Passwords do not match.")

        try:
            role = UserRole(role_str)
        except ValueError:
            return ctx("Invalid role selected.")

        full_name    = _clean(data.full_name, 255)
        company_name = _clean(data.company_name, 255) or "My Company"

        if role == UserRole.CANDIDATE and not full_name:
            return ctx("Please enter your full name.")
        if role == UserRole.EMPLOYER and not company_name.strip():
            return ctx("Please enter your company name.")

        async with request.app.state.db_session() as db:
            if (await db.execute(select(User).where(User.email == email))).scalar_one_or_none():
                return ctx("That email is already registered. Please sign in.")

            user = User(
                email=email,
                password_hash=hash_password(data.password),
                role=role,
                auth_provider="email",
            )
            db.add(user)
            await db.flush()
            await _create_profile(
                db, user, role,
                full_name=full_name,
                company_name=company_name,
                profession=_clean(data.profession, 255),
                skills=_clean(data.skills, 1000),
                exp=max(0, min(int(data.experience_years or 0), 60)),
                bio=_clean(data.bio, 2000),
                industry=_clean(data.industry, 255),
                location=_clean(data.location, 255),
            )
            token = await create_session(db, user.id)
            await db.commit()

        redirect_url = "/dashboard/candidate" if role == UserRole.CANDIDATE else "/dashboard/employer"
        response = Redirect(redirect_url)
        _set_session_cookie(response, token)
        return response  # type: ignore[return-value]

    # ── Login ─────────────────────────────────────────────────────────────────

    @get("/login", include_in_schema=False)
    async def login_page(self, request: Request) -> Template:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            async with request.app.state.db_session() as db:
                from services.auth import get_user_by_token
                if await get_user_by_token(db, token):
                    return Redirect("/dashboard")  # type: ignore[return-value]
        next_url = _clean(request.query_params.get("next", "/dashboard"), 200)
        if not next_url.startswith("/"):
            next_url = "/dashboard"
        response = Template("auth/login.html", context={"error": None, "next": next_url})
        if token:
            response.delete_cookie(SESSION_COOKIE_NAME)
        return response

    @post("/login", include_in_schema=False)
    async def login(
        self, request: Request,
        data: LoginForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:
        email    = (data.email or "").strip().lower()
        password = data.password or ""
        next_url = _clean(data.next, 200)
        if not next_url.startswith("/"):
            next_url = "/dashboard"

        generic_err = "Invalid email or password."

        if not _ok_email(email) or not password or len(password) > 128:
            return Template("auth/login.html", context={"error": generic_err, "next": next_url})

        async with request.app.state.db_session() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if not user:
                return Template("auth/login.html", context={"error": generic_err, "next": next_url})

            # Google-only account — no password set
            if user.auth_provider == "google":
                return Template("auth/login.html", context={
                    "error": "This account uses Google sign-in. Please use the 'Continue with Google' button.",
                    "next": next_url,
                })

            if not verify_password(password, user.password_hash):
                return Template("auth/login.html", context={"error": generic_err, "next": next_url})

            if not user.is_active:
                return Template("auth/login.html", context={
                    "error": "Account is disabled. Contact support.", "next": next_url,
                })

            token = await create_session(db, user.id)
            await db.commit()

        redirect_url = (
            "/dashboard/candidate" if user.role == UserRole.CANDIDATE
            else "/dashboard/employer" if user.role == UserRole.EMPLOYER
            else "/dashboard"
        )
        response = Redirect(redirect_url)
        _set_session_cookie(response, token)
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

    # ── Google OAuth ──────────────────────────────────────────────────────────

    @get("/google", include_in_schema=False)
    async def google_redirect(self, request: Request) -> Redirect:
        """Redirect user to Google's consent screen."""
        from services.oauth import get_authorization_url
        try:
            url, state = get_authorization_url()
        except Exception as exc:
            logger.exception("Google OAuth redirect failed: %s", exc)
            return Redirect("/auth/login?error=google_not_configured")
        response = Redirect(url)
        response.set_cookie("oauth_state", state, max_age=600, httponly=True, samesite="lax")
        return response

    @get("/google/callback", include_in_schema=False)
    async def google_callback(self, request: Request) -> Redirect:
        """Google returns here after consent. Create or find the user account."""
        from services.oauth import exchange_code_for_user

        code     = request.query_params.get("code")
        state    = request.query_params.get("state", "")
        expected = request.cookies.get("oauth_state", "")
        error    = request.query_params.get("error")

        if error or not code:
            response = Redirect("/auth/login?error=google_cancelled")
            response.delete_cookie("oauth_state")
            return response

        user_info = await exchange_code_for_user(code, state, expected)
        if not user_info:
            response = Redirect("/auth/login?error=google_failed")
            response.delete_cookie("oauth_state")
            return response

        google_id = user_info.get("sub", "")
        email     = (user_info.get("email") or "").strip().lower()
        name      = user_info.get("name", "")

        if not email:
            response = Redirect("/auth/login?error=google_no_email")
            response.delete_cookie("oauth_state")
            return response

        async with request.app.state.db_session() as db:
            # Check if user already exists by google_id or email
            result = await db.execute(
                select(User).where(
                    (User.google_id == google_id) | (User.email == email)
                )
            )
            user = result.scalar_one_or_none()

            if user:
                # Existing user — update google_id if not set
                if not user.google_id:
                    user.google_id = google_id
                    user.auth_provider = "google"
                    db.add(user)

                if not user.is_active:
                    response = Redirect("/auth/login?error=account_disabled")
                    response.delete_cookie("oauth_state")
                    return response

                token = await create_session(db, user.id)
                await db.commit()

                redirect_url = (
                    "/dashboard/candidate" if user.role == UserRole.CANDIDATE
                    else "/dashboard/employer"
                )
                response = Redirect(redirect_url)
                _set_session_cookie(response, token)
                response.delete_cookie("oauth_state")
                return response

            else:
                # New Google user — need to pick a role first
                # Store google info in a short-lived cookie
                import json, base64
                info = base64.b64encode(
                    json.dumps({"google_id": google_id, "email": email, "name": name}).encode()
                ).decode()
                response = Redirect("/auth/google/role")
                response.set_cookie("google_pending", info, max_age=600, httponly=True, samesite="lax")
                response.delete_cookie("oauth_state")
                return response

    @get("/google/role", include_in_schema=False)
    async def google_role_page(self, request: Request) -> Template | Redirect:
        """Show role selection to new Google users."""
        pending = request.cookies.get("google_pending")
        if not pending:
            return Redirect("/auth/register")
        return Template("auth/role_select.html", context={"error": None})

    @post("/google/role", include_in_schema=False)
    async def google_role_submit(
        self, request: Request,
        data: RoleSelectForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:
        """Create the Google account with the chosen role."""
        import json, base64

        pending = request.cookies.get("google_pending")
        if not pending:
            return Redirect("/auth/register")

        try:
            info = json.loads(base64.b64decode(pending).decode())
        except Exception:
            return Redirect("/auth/register")

        role_str = _clean(data.role, 20).upper()
        try:
            role = UserRole(role_str)
        except ValueError:
            return Template("auth/role_select.html", context={"error": "Please choose a valid role."})

        google_id = info["google_id"]
        email     = info["email"]
        name      = _clean(data.full_name or info.get("name", ""), 255)
        company   = _clean(data.company_name or "My Company", 255)

        if role == UserRole.CANDIDATE and not name:
            return Template("auth/role_select.html", context={"error": "Please enter your full name."})
        if role == UserRole.EMPLOYER and not company.strip():
            return Template("auth/role_select.html", context={"error": "Please enter your company name."})

        async with request.app.state.db_session() as db:
            # Guard: check email not already taken
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                # Merge: attach google_id to existing account
                existing.google_id    = google_id
                existing.auth_provider = "google"
                db.add(existing)
                token = await create_session(db, existing.id)
                await db.commit()
                redirect_url = (
                    "/dashboard/candidate" if existing.role == UserRole.CANDIDATE
                    else "/dashboard/employer"
                )
                response = Redirect(redirect_url)
                _set_session_cookie(response, token)
                response.delete_cookie("google_pending")
                return response

            user = User(
                email=email,
                password_hash="",          # no password for Google accounts
                role=role,
                auth_provider="google",
                google_id=google_id,
            )
            db.add(user)
            await db.flush()
            await _create_profile(
                db, user, role,
                full_name=name, company_name=company,
            )
            token = await create_session(db, user.id)
            await db.commit()

        redirect_url = "/dashboard/candidate" if role == UserRole.CANDIDATE else "/dashboard/employer"
        response = Redirect(redirect_url)
        _set_session_cookie(response, token)
        response.delete_cookie("google_pending")
        return response  # type: ignore[return-value]

    # ── Forgot password ───────────────────────────────────────────────────────

    @get("/forgot-password", include_in_schema=False)
    async def forgot_password_page(self, request: Request) -> Template:
        error = request.query_params.get("error")
        msg   = {
            "google_cancelled":    "Google sign-in was cancelled.",
            "google_failed":       "Google sign-in failed. Please try again.",
            "google_no_email":     "Could not retrieve your email from Google.",
            "account_disabled":    "This account has been disabled.",
            "google_not_configured": "Google sign-in is not available right now.",
        }.get(error or "", None)
        return Template("auth/forgot_password.html", context={
            "error": None, "success": None, "google_error": msg,
        })

    @post("/forgot-password", include_in_schema=False)
    async def forgot_password(
        self, request: Request,
        data: ForgotPasswordForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template:
        email = (data.email or "").strip().lower()

        # Always show the same success message to prevent email enumeration
        success_msg = (
            "If that email is registered, a reset link has been sent. "
            "Check your inbox (and spam folder)."
        )

        if not _ok_email(email):
            return Template("auth/forgot_password.html", context={
                "error": "Please enter a valid email address.",
                "success": None, "google_error": None,
            })

        async with request.app.state.db_session() as db:
            result = await db.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if user and user.auth_provider == "google":
                # Google accounts can reset via Google — inform them
                return Template("auth/forgot_password.html", context={
                    "error": None,
                    "success": None,
                    "google_error": (
                        "Password reset is not available for Google sign-in accounts. "
                        "Use the 'Continue with Google' button to sign in, or reset your "
                        "password at myaccount.google.com."
                    ),
                })

            if user and user.is_active and user.auth_provider == "email":
                token = secrets.token_urlsafe(48)
                user.reset_token        = token
                user.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS)
                db.add(user)
                await db.commit()
                # Send email in background — don't block response
                import asyncio
                asyncio.create_task(
                    asyncio.to_thread(send_password_reset_email, email, token)
                )

        return Template("auth/forgot_password.html", context={
            "error": None, "success": success_msg, "google_error": None,
        })

    # ── Reset password ────────────────────────────────────────────────────────

    @get("/reset-password", include_in_schema=False)
    async def reset_password_page(self, request: Request) -> Template | Redirect:
        token = request.query_params.get("token", "")
        if not token:
            return Redirect("/auth/forgot-password")

        async with request.app.state.db_session() as db:
            result = await db.execute(
                select(User).where(User.reset_token == token)
            )
            user = result.scalar_one_or_none()

            if not user or not user.reset_token_expiry:
                return Template("auth/reset_password.html", context={
                    "token": "", "error": "This reset link is invalid or has already been used.",
                    "expired": True,
                })

            if user.reset_token_expiry < datetime.now(timezone.utc):
                return Template("auth/reset_password.html", context={
                    "token": "", "error": "This reset link has expired. Please request a new one.",
                    "expired": True,
                })

        return Template("auth/reset_password.html", context={
            "token": token, "error": None, "expired": False,
        })

    @post("/reset-password", include_in_schema=False)
    async def reset_password(
        self, request: Request,
        data: ResetPasswordForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Template | Redirect:
        token = _clean(data.token, 128)

        def err(msg: str) -> Template:
            return Template("auth/reset_password.html", context={
                "token": token, "error": msg, "expired": False,
            })

        if not token:
            return Redirect("/auth/forgot-password")
        if not data.password or len(data.password) < 8:
            return err("Password must be at least 8 characters.")
        if data.password != data.confirm_password:
            return err("Passwords do not match.")

        async with request.app.state.db_session() as db:
            result = await db.execute(select(User).where(User.reset_token == token))
            user = result.scalar_one_or_none()

            if not user or not user.reset_token_expiry:
                return err("This reset link is invalid.")
            if user.reset_token_expiry < datetime.now(timezone.utc):
                return err("This reset link has expired. Please request a new one.")

            user.password_hash     = hash_password(data.password)
            user.reset_token       = None
            user.reset_token_expiry = None
            db.add(user)
            await db.commit()

        return Redirect("/auth/login?reset=success")


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
