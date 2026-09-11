"""
Auth Service
============
Password hashing, session token management, and current-user resolution.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import SESSION_COOKIE_NAME, SESSION_EXPIRE_DAYS
from models import CandidateProfile, EmployerProfile, User, UserRole, UserSession


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _new_token() -> str:
    return secrets.token_urlsafe(64)


def _expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRE_DAYS)


async def create_session(session: AsyncSession, user_id: int) -> str:
    """Create a new session row and return the token string."""
    token = _new_token()
    sess = UserSession(user_id=user_id, token=token, expires_at=_expiry())
    session.add(sess)
    await session.flush()
    return token


async def delete_session(session: AsyncSession, token: str) -> None:
    result = await session.execute(
        select(UserSession).where(UserSession.token == token)
    )
    row = result.scalar_one_or_none()
    if row:
        await session.delete(row)


async def get_user_by_token(session: AsyncSession, token: str) -> User | None:
    """Resolve a session token → User (returns None if expired or invalid)."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(UserSession).where(
            UserSession.token == token,
            UserSession.expires_at > now,
        )
    )
    sess = result.scalar_one_or_none()
    if sess is None:
        return None
    return await session.get(User, sess.user_id)


# ---------------------------------------------------------------------------
# Request helpers  (used by controllers)
# ---------------------------------------------------------------------------

def get_token_from_request(request: Any) -> str | None:
    """Extract session token from cookie."""
    return request.cookies.get(SESSION_COOKIE_NAME)


async def get_current_user(request: Any, db: AsyncSession) -> User | None:
    token = get_token_from_request(request)
    if not token:
        return None
    return await get_user_by_token(db, token)


async def require_user(request: Any, db: AsyncSession) -> User:
    """Return current user or raise 401."""
    from litestar.exceptions import NotAuthorizedException
    user = await get_current_user(request, db)
    if user is None:
        raise NotAuthorizedException(detail="Login required.")
    return user


async def require_candidate(request: Any, db: AsyncSession) -> tuple[User, CandidateProfile]:
    """Return (user, candidate_profile) or raise."""
    from litestar.exceptions import NotAuthorizedException, NotFoundException
    user = await require_user(request, db)
    if user.role != UserRole.CANDIDATE:
        raise NotAuthorizedException(detail="Candidate account required.")
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundException(detail="Candidate profile not found.")
    return user, profile


async def require_employer(request: Any, db: AsyncSession) -> tuple[User, EmployerProfile]:
    """Return (user, employer_profile) or raise."""
    from litestar.exceptions import NotAuthorizedException, NotFoundException
    user = await require_user(request, db)
    if user.role != UserRole.EMPLOYER:
        raise NotAuthorizedException(detail="Employer account required.")
    result = await db.execute(
        select(EmployerProfile).where(EmployerProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundException(detail="Employer profile not found.")
    return user, profile
