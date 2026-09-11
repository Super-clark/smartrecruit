"""
SQLAlchemy ORM models — SmartRecruit Platform (full schema).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Index, Integer, LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    CANDIDATE = "CANDIDATE"
    EMPLOYER  = "EMPLOYER"
    ADMIN     = "ADMIN"

class OutreachStatus(str, enum.Enum):
    PENDING  = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"

class ApplicationStatus(str, enum.Enum):
    APPLIED     = "APPLIED"
    SCREENING   = "SCREENING"
    INTERVIEW   = "INTERVIEW"
    TEST        = "TEST"
    OFFER       = "OFFER"
    ONBOARDED   = "ONBOARDED"
    REJECTED    = "REJECTED"
    WITHDRAWN   = "WITHDRAWN"

class NotificationType(str, enum.Enum):
    OUTREACH          = "OUTREACH"
    APPLICATION       = "APPLICATION"
    JOB_MATCH         = "JOB_MATCH"
    STATUS_CHANGE     = "STATUS_CHANGE"
    RATING            = "RATING"
    SYSTEM            = "SYSTEM"

class JobType(str, enum.Enum):
    FULL_TIME  = "FULL_TIME"
    PART_TIME  = "PART_TIME"
    CONTRACT   = "CONTRACT"
    FREELANCE  = "FREELANCE"
    INTERNSHIP = "INTERNSHIP"
    REMOTE     = "REMOTE"

class WorkMode(str, enum.Enum):
    ONSITE  = "ONSITE"
    REMOTE  = "REMOTE"
    HYBRID  = "HYBRID"

class RatingTarget(str, enum.Enum):
    CANDIDATE = "CANDIDATE"
    EMPLOYER  = "EMPLOYER"


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id            : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    email         : Mapped[str]      = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash : Mapped[str]      = mapped_column(String(255), nullable=False)
    role          : Mapped[UserRole] = mapped_column(Enum(UserRole, name="userrole"), nullable=False)
    is_active     : Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at    : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    candidate_profile : Mapped["CandidateProfile | None"] = relationship("CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    employer_profile  : Mapped["EmployerProfile | None"]  = relationship("EmployerProfile",  back_populates="user", uselist=False, cascade="all, delete-orphan")
    sessions          : Mapped[list["UserSession"]]       = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    notifications     : Mapped[list["Notification"]]      = relationship("Notification", back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Sessions (cookie-based auth)
# ---------------------------------------------------------------------------

class UserSession(Base):
    __tablename__ = "user_sessions"

    id         : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id    : Mapped[int]      = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token      : Mapped[str]      = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user : Mapped["User"] = relationship("User", back_populates="sessions")


# ---------------------------------------------------------------------------
# Candidate Profile
# ---------------------------------------------------------------------------

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_candidate_user"),)

    id               : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id          : Mapped[int]        = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Personal info
    full_name        : Mapped[str | None] = mapped_column(String(255))
    age              : Mapped[int | None] = mapped_column(Integer)
    birthday         : Mapped[str | None] = mapped_column(String(20))   # ISO date string
    phone            : Mapped[str | None] = mapped_column(String(50))
    location         : Mapped[str | None] = mapped_column(String(255))
    bio              : Mapped[str | None] = mapped_column(Text)
    avatar_data      : Mapped[bytes | None] = mapped_column(LargeBinary)   # profile picture
    avatar_mime      : Mapped[str | None]   = mapped_column(String(50))    # e.g. image/jpeg

    # Professional info
    title            : Mapped[str | None] = mapped_column(String(255))
    profession       : Mapped[str | None] = mapped_column(String(255))
    skills           : Mapped[str | None] = mapped_column(Text)            # comma-separated
    life_skills      : Mapped[str | None] = mapped_column(Text)            # e.g. leadership, teamwork
    experience_years : Mapped[int]        = mapped_column(Integer, default=0)
    education        : Mapped[str | None] = mapped_column(Text)
    certifications   : Mapped[str | None] = mapped_column(Text)
    languages        : Mapped[str | None] = mapped_column(String(255))
    expected_salary  : Mapped[str | None] = mapped_column(String(100))
    job_type_pref    : Mapped[str | None] = mapped_column(String(100))     # full-time, remote, etc.
    linkedin_url     : Mapped[str | None] = mapped_column(String(500))
    portfolio_url    : Mapped[str | None] = mapped_column(String(500))

    # CV stored as binary in DB
    cv_data          : Mapped[bytes | None] = mapped_column(LargeBinary)
    cv_filename      : Mapped[str | None]   = mapped_column(String(255))
    cv_mime          : Mapped[str | None]   = mapped_column(String(100))

    resume_text      : Mapped[str | None] = mapped_column(Text)            # plain text for embeddings
    is_searchable    : Mapped[bool]       = mapped_column(Boolean, default=True)
    is_open_to_work  : Mapped[bool]       = mapped_column(Boolean, default=True)
    updated_at       : Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user              : Mapped["User"]               = relationship("User", back_populates="candidate_profile")
    applications      : Mapped[list["Application"]]  = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")
    outreaches        : Mapped[list["DirectOutreach"]] = relationship("DirectOutreach", back_populates="candidate", cascade="all, delete-orphan")
    bookmarks         : Mapped[list["JobBookmark"]]  = relationship("JobBookmark", back_populates="candidate", cascade="all, delete-orphan")
    ratings_received  : Mapped[list["Rating"]]       = relationship("Rating", foreign_keys="Rating.target_candidate_id", back_populates="target_candidate", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Employer Profile
# ---------------------------------------------------------------------------

class EmployerProfile(Base):
    __tablename__ = "employer_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_employer_user"),)

    id               : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id          : Mapped[int]        = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)

    # Company info
    company_name     : Mapped[str]        = mapped_column(String(255), nullable=False, default="My Company")
    industry         : Mapped[str | None] = mapped_column(String(255))
    company_size     : Mapped[str | None] = mapped_column(String(100))   # e.g. "10-50 employees"
    founded_year     : Mapped[int | None] = mapped_column(Integer)
    website          : Mapped[str | None] = mapped_column(String(500))
    description      : Mapped[str | None] = mapped_column(Text)
    work_environment : Mapped[str | None] = mapped_column(Text)           # culture, perks, etc.
    benefits         : Mapped[str | None] = mapped_column(Text)
    work_mode        : Mapped[str | None] = mapped_column(String(50))     # onsite/remote/hybrid
    location         : Mapped[str | None] = mapped_column(String(255))
    logo_data        : Mapped[bytes | None] = mapped_column(LargeBinary)
    logo_mime        : Mapped[str | None]   = mapped_column(String(50))

    # Personal contact (for solo employers without company)
    contact_name     : Mapped[str | None] = mapped_column(String(255))
    contact_phone    : Mapped[str | None] = mapped_column(String(50))
    linkedin_url     : Mapped[str | None] = mapped_column(String(500))

    updated_at       : Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user             : Mapped["User"]                = relationship("User", back_populates="employer_profile")
    job_posts        : Mapped[list["JobPost"]]        = relationship("JobPost", back_populates="employer", cascade="all, delete-orphan")
    outreaches_sent  : Mapped[list["DirectOutreach"]] = relationship("DirectOutreach", back_populates="employer", cascade="all, delete-orphan")
    ratings_received : Mapped[list["Rating"]]         = relationship("Rating", foreign_keys="Rating.target_employer_id", back_populates="target_employer", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Job Posts
# ---------------------------------------------------------------------------

class JobPost(Base):
    __tablename__ = "job_posts"
    __table_args__ = (Index("ix_job_posts_employer_id", "employer_id"),)

    id               : Mapped[int]        = mapped_column(Integer, primary_key=True, autoincrement=True)
    employer_id      : Mapped[int]        = mapped_column(Integer, ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    title            : Mapped[str]        = mapped_column(String(255), nullable=False)
    description      : Mapped[str]        = mapped_column(Text, nullable=False)
    skills_required  : Mapped[str | None] = mapped_column(Text)
    experience_min   : Mapped[int]        = mapped_column(Integer, default=0)
    job_type         : Mapped[str | None] = mapped_column(String(50))    # full-time, part-time etc.
    work_mode        : Mapped[str | None] = mapped_column(String(50))    # onsite/remote/hybrid
    location         : Mapped[str | None] = mapped_column(String(255))
    salary_range     : Mapped[str | None] = mapped_column(String(100))
    industry         : Mapped[str | None] = mapped_column(String(255))
    is_active        : Mapped[bool]       = mapped_column(Boolean, default=True)
    expires_at       : Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at       : Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    employer      : Mapped["EmployerProfile"]    = relationship("EmployerProfile", back_populates="job_posts")
    applications  : Mapped[list["Application"]]  = relationship("Application", back_populates="job", cascade="all, delete-orphan")
    outreaches    : Mapped[list["DirectOutreach"]] = relationship("DirectOutreach", back_populates="job", cascade="all, delete-orphan")
    bookmarks     : Mapped[list["JobBookmark"]]  = relationship("JobBookmark", back_populates="job", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Applications  (candidate → job)
# ---------------------------------------------------------------------------

class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application"),
        Index("ix_application_job_id", "job_id"),
        Index("ix_application_candidate_id", "candidate_id"),
    )

    id           : Mapped[int]               = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id : Mapped[int]               = mapped_column(Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    job_id       : Mapped[int]               = mapped_column(Integer, ForeignKey("job_posts.id", ondelete="CASCADE"), nullable=False)
    cover_letter : Mapped[str | None]        = mapped_column(Text)
    status       : Mapped[ApplicationStatus] = mapped_column(Enum(ApplicationStatus, name="applicationstatus"), default=ApplicationStatus.APPLIED, nullable=False)
    employer_note: Mapped[str | None]        = mapped_column(Text)
    applied_at   : Mapped[datetime]          = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at   : Mapped[datetime]          = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    candidate : Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="applications")
    job       : Mapped["JobPost"]          = relationship("JobPost", back_populates="applications")


# ---------------------------------------------------------------------------
# Direct Outreach  (employer → candidate)
# ---------------------------------------------------------------------------

class DirectOutreach(Base):
    __tablename__ = "direct_outreaches"
    __table_args__ = (
        Index("ix_outreach_employer_id", "employer_id"),
        Index("ix_outreach_candidate_id", "candidate_id"),
    )

    id           : Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    employer_id  : Mapped[int]             = mapped_column(Integer, ForeignKey("employer_profiles.id", ondelete="CASCADE"), nullable=False)
    candidate_id : Mapped[int]             = mapped_column(Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    job_id       : Mapped[int | None]      = mapped_column(Integer, ForeignKey("job_posts.id", ondelete="SET NULL"))
    message      : Mapped[str | None]      = mapped_column(Text)
    candidate_reply : Mapped[str | None]   = mapped_column(Text)           # candidate's reply
    replied_at   : Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status       : Mapped[OutreachStatus]  = mapped_column(Enum(OutreachStatus, name="outreachstatus"), default=OutreachStatus.PENDING, nullable=False)
    created_at   : Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    employer  : Mapped["EmployerProfile"]  = relationship("EmployerProfile", back_populates="outreaches_sent")
    candidate : Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="outreaches")
    job       : Mapped["JobPost | None"]   = relationship("JobPost", back_populates="outreaches")


# ---------------------------------------------------------------------------
# Job Bookmarks  (candidate saves a job)
# ---------------------------------------------------------------------------

class JobBookmark(Base):
    __tablename__ = "job_bookmarks"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_bookmark"),)

    id           : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    candidate_id : Mapped[int]      = mapped_column(Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"), nullable=False)
    job_id       : Mapped[int]      = mapped_column(Integer, ForeignKey("job_posts.id", ondelete="CASCADE"), nullable=False)
    created_at   : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    candidate : Mapped["CandidateProfile"] = relationship("CandidateProfile", back_populates="bookmarks")
    job       : Mapped["JobPost"]          = relationship("JobPost", back_populates="bookmarks")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notification_user_id", "user_id"),)

    id         : Mapped[int]              = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id    : Mapped[int]              = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type       : Mapped[NotificationType] = mapped_column(Enum(NotificationType, name="notificationtype"), nullable=False)
    title      : Mapped[str]             = mapped_column(String(255), nullable=False)
    body       : Mapped[str | None]      = mapped_column(Text)
    link       : Mapped[str | None]      = mapped_column(String(500))   # relative URL to navigate to
    is_read    : Mapped[bool]            = mapped_column(Boolean, default=False)
    created_at : Mapped[datetime]        = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user : Mapped["User"] = relationship("User", back_populates="notifications")


# ---------------------------------------------------------------------------
# Outreach Messages  (unlimited back-and-forth per outreach thread)
# ---------------------------------------------------------------------------

class OutreachMessage(Base):
    """Individual message in an outreach thread. Either party can send."""

    __tablename__ = "outreach_messages"
    __table_args__ = (Index("ix_outreach_msg_outreach_id", "outreach_id"),)

    id          : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    outreach_id : Mapped[int]      = mapped_column(Integer, ForeignKey("direct_outreaches.id", ondelete="CASCADE"), nullable=False)
    sender_role : Mapped[str]      = mapped_column(String(20), nullable=False)   # "EMPLOYER" or "CANDIDATE"
    sender_id   : Mapped[int]      = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body        : Mapped[str]      = mapped_column(Text, nullable=False)
    created_at  : Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        Index("ix_rating_target_candidate", "target_candidate_id"),
        Index("ix_rating_target_employer",  "target_employer_id"),
    )

    id                  : Mapped[int]          = mapped_column(Integer, primary_key=True, autoincrement=True)
    rater_user_id       : Mapped[int]          = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_candidate_id : Mapped[int | None]   = mapped_column(Integer, ForeignKey("candidate_profiles.id", ondelete="CASCADE"))
    target_employer_id  : Mapped[int | None]   = mapped_column(Integer, ForeignKey("employer_profiles.id", ondelete="CASCADE"))
    target              : Mapped[RatingTarget] = mapped_column(Enum(RatingTarget, name="ratingtarget"), nullable=False)
    score               : Mapped[float]        = mapped_column(Float, nullable=False)   # 1.0 – 5.0
    review              : Mapped[str | None]   = mapped_column(Text)
    created_at          : Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    target_candidate : Mapped["CandidateProfile | None"] = relationship("CandidateProfile", foreign_keys=[target_candidate_id], back_populates="ratings_received")
    target_employer  : Mapped["EmployerProfile | None"]  = relationship("EmployerProfile",  foreign_keys=[target_employer_id],  back_populates="ratings_received")
