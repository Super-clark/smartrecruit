"""
Ratings Controller
==================
Routes
------
POST /ratings/candidate/{id:int} — rate a candidate
POST /ratings/employer/{id:int}  — rate an employer
GET  /ratings/candidate/{id:int} — get ratings for a candidate (JSON)
GET  /ratings/employer/{id:int}  — get ratings for an employer  (JSON)
"""

from __future__ import annotations

from dataclasses import dataclass

from litestar import Controller, Request, get, post
from litestar.enums import RequestEncodingType
from litestar.exceptions import NotFoundException
from litestar.params import Body
from litestar.response import Redirect

from models import CandidateProfile, EmployerProfile, RatingTarget
from services.auth import require_user
from services.notifications import create_notification
from models import NotificationType
from services.ratings import (
    get_candidate_rating, get_employer_rating,
    get_ratings_for_candidate, get_ratings_for_employer,
    submit_rating,
)


@dataclass
class RatingForm:
    score: float
    review: str | None = None


class RatingsController(Controller):
    path = "/ratings"

    @post("/candidate/{candidate_id:int}", include_in_schema=False)
    async def rate_candidate(
        self,
        request: Request,
        candidate_id: int,
        data: RatingForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Redirect:
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)
            cp = await db.get(CandidateProfile, candidate_id)
            if not cp:
                raise NotFoundException(detail="Candidate not found.")

            await submit_rating(
                db, rater_user_id=user.id,
                target=RatingTarget.CANDIDATE,
                score=data.score,
                review=data.review,
                target_candidate_id=candidate_id,
            )
            from models import User as _User
            cand_user = await db.get(_User, cp.user_id)
            if cand_user:
                await create_notification(
                    db, cand_user.id, NotificationType.RATING,
                    title="You received a new rating!",
                    body=f"Someone rated you {data.score}/5.",
                    link=f"/profile/candidate/{candidate_id}",
                )
            await db.commit()
        return Redirect(f"/profile/candidate/{candidate_id}")

    @post("/employer/{employer_id:int}", include_in_schema=False)
    async def rate_employer(
        self,
        request: Request,
        employer_id: int,
        data: RatingForm = Body(media_type=RequestEncodingType.URL_ENCODED),
    ) -> Redirect:
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)
            ep = await db.get(EmployerProfile, employer_id)
            if not ep:
                raise NotFoundException(detail="Employer not found.")

            await submit_rating(
                db, rater_user_id=user.id,
                target=RatingTarget.EMPLOYER,
                score=data.score,
                review=data.review,
                target_employer_id=employer_id,
            )
            from models import User as _User
            emp_user = await db.get(_User, ep.user_id)
            if emp_user:
                await create_notification(
                    db, emp_user.id, NotificationType.RATING,
                    title="You received a new rating!",
                    body=f"Someone rated your company {data.score}/5.",
                    link=f"/profile/employer/{employer_id}",
                )
            await db.commit()
        return Redirect(f"/profile/employer/{employer_id}")

    @get("/candidate/{candidate_id:int}", summary="Get candidate ratings")
    async def candidate_ratings(self, request: Request, candidate_id: int) -> dict:
        async with request.app.state.db_session() as db:
            avg, cnt = await get_candidate_rating(db, candidate_id)
            reviews = await get_ratings_for_candidate(db, candidate_id)
        return {
            "average": avg, "count": cnt,
            "reviews": [
                {"score": r.score, "review": r.review,
                 "created_at": r.created_at.isoformat()}
                for r in reviews
            ],
        }

    @get("/employer/{employer_id:int}", summary="Get employer ratings")
    async def employer_ratings(self, request: Request, employer_id: int) -> dict:
        async with request.app.state.db_session() as db:
            avg, cnt = await get_employer_rating(db, employer_id)
            reviews = await get_ratings_for_employer(db, employer_id)
        return {
            "average": avg, "count": cnt,
            "reviews": [
                {"score": r.score, "review": r.review,
                 "created_at": r.created_at.isoformat()}
                for r in reviews
            ],
        }
