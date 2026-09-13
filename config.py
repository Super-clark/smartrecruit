"""
Central configuration — SmartRecruit Platform.
"""

from __future__ import annotations
import os
import secrets
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:123321123@localhost:5432/recruitment_db",
)

# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------
QDRANT_HOST: str       = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT: int       = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "candidates")

# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------
EMBEDDING_DIM: int   = 384
EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
SESSION_SECRET: str        = os.getenv("SESSION_SECRET", secrets.token_hex(32))
SESSION_COOKIE_NAME: str   = "sr_session"
SESSION_EXPIRE_DAYS: int   = int(os.getenv("SESSION_EXPIRE_DAYS", "30"))

# ---------------------------------------------------------------------------
# File uploads
# ---------------------------------------------------------------------------
MAX_AVATAR_BYTES: int = 2 * 1024 * 1024    # 2 MB
MAX_CV_BYTES: int     = 10 * 1024 * 1024   # 10 MB

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE: int = 12

# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID: str     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI: str  = os.getenv(
    "GOOGLE_REDIRECT_URI",
    "http://127.0.0.1:8000/auth/google/callback",
)

# ---------------------------------------------------------------------------
# Email (Gmail SMTP — for password reset)
# ---------------------------------------------------------------------------
SMTP_EMAIL: str    = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST: str     = "smtp.gmail.com"
SMTP_PORT: int     = 587

# Base URL used in reset email links
APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://127.0.0.1:8000")

# Reset token expiry in hours
RESET_TOKEN_EXPIRE_HOURS: int = 1

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
SERVER_HOST: str = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
RELOAD: bool     = os.getenv("RELOAD", "true").lower() == "true"
