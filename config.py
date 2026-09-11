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
# File uploads (stored in DB; this controls max sizes in bytes)
# ---------------------------------------------------------------------------
MAX_AVATAR_BYTES: int = 2 * 1024 * 1024    # 2 MB
MAX_CV_BYTES: int     = 10 * 1024 * 1024   # 10 MB

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
DEFAULT_PAGE_SIZE: int = 12

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
SERVER_HOST: str = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8000"))
RELOAD: bool     = os.getenv("RELOAD", "true").lower() == "true"
