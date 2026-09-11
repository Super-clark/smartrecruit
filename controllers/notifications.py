"""
Notifications Controller
========================
Routes
------
GET  /notifications          — list notifications for current user
POST /notifications/read-all — mark all as read
POST /notifications/{id:int}/read — mark one as read
GET  /notifications/count    — JSON unread count (polled by frontend)
"""

from __future__ import annotations

from dataclasses import dataclass

from litestar import Controller, Request, get, post
from litestar.response import Redirect, Template

from services.auth import require_user
from services.notifications import (
    count_unread, get_notifications, mark_all_read, mark_read,
)


class NotificationsController(Controller):
    path = "/notifications"

    @get("/", include_in_schema=False)
    async def list_notifications(self, request: Request) -> Template:
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)
            notifs = await get_notifications(db, user.id, limit=50)
        return Template("shared/notifications.html", context={
            "user": user, "notifications": notifs,
        })

    @get("/count", summary="Unread notification count")
    async def unread_count(self, request: Request) -> dict:
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)
            cnt = await count_unread(db, user.id)
        return {"unread": cnt}

    @post("/read-all", include_in_schema=False)
    async def read_all(self, request: Request) -> Redirect:
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)
            await mark_all_read(db, user.id)
            await db.commit()
        return Redirect("/notifications")

    @post("/{notif_id:int}/read", include_in_schema=False)
    async def read_one(self, request: Request, notif_id: int) -> Redirect:
        async with request.app.state.db_session() as db:
            user = await require_user(request, db)
            await mark_read(db, notif_id, user.id)
            await db.commit()
        return Redirect("/notifications")
