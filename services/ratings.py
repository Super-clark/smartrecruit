"""
Ratings Service
===============
Submit and aggregate ratings for candidates and employers.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Rating, RatingTarget


async def submit_rating(
    db: AsyncSession,
    rater_user_id: int,
    target: RatingTarget,
    score: float,
    review: str | None = None,
    target_candidate_id: int | None = None,
    target_employer_id: int | None = None,
) -> Rating:
    """Upsert a rating (one rating per rater per target)."""
    # Check for existing rating
    q = select(Rating).where(Rating.rater_user_id == rater_user_id, Rating.target == target)
    if target_candidate_id:
        q = q.where(Rating.target_candidate_id == target_candidate_id)
    if target_employer_id:
        q = q.where(Rating.target_employer_id == target_employer_id)

    result = await db.execute(q)
    existing = result.scalar_one_or_none()

    if existing:
        existing.score  = max(1.0, min(5.0, score))
        existing.review = review
        db.add(existing)
        return existing

    rating = Rating(
        rater_user_id=rater_user_id,
        target=target,
        score=max(1.0, min(5.0, score)),
        review=review,
        target_candidate_id=target_candidate_id,
        target_employer_id=target_employer_id,
    )
    db.add(rating)
    await db.flush()
    return rating


async def get_candidate_rating(db: AsyncSession, candidate_id: int) -> tuple[float, int]:
    """Returns (average_score, count)."""
    result = await db.execute(
        select(func.avg(Rating.score), func.count(Rating.id))
        .where(Rating.target_candidate_id == candidate_id)
    )
    avg, count = result.one()
    return (round(float(avg), 1) if avg else 0.0, count or 0)


async def get_employer_rating(db: AsyncSession, employer_id: int) -> tuple[float, int]:
    """Returns (average_score, count)."""
    result = await db.execute(
        select(func.avg(Rating.score), func.count(Rating.id))
        .where(Rating.target_employer_id == employer_id)
    )
    avg, count = result.one()
    return (round(float(avg), 1) if avg else 0.0, count or 0)


async def get_ratings_for_candidate(db: AsyncSession, candidate_id: int, limit: int = 20) -> list[Rating]:
    result = await db.execute(
        select(Rating)
        .where(Rating.target_candidate_id == candidate_id)
        .order_by(Rating.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_ratings_for_employer(db: AsyncSession, employer_id: int, limit: int = 20) -> list[Rating]:
    result = await db.execute(
        select(Rating)
        .where(Rating.target_employer_id == employer_id)
        .order_by(Rating.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
