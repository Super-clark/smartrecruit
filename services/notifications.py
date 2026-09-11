"""
Notification Service
====================
Helpers for creating, fetching, and marking notifications.
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification, NotificationType


async def create_notification(
    db: AsyncSession,
    user_id: int,
    type: NotificationType,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> Notification:
    notif = Notification(
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
        is_read=False,
    )
    db.add(notif)
    await db.flush()
    return notif


async def get_notifications(
    db: AsyncSession,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
) -> list[Notification]:
    q = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        q = q.where(Notification.is_read.is_(False))
    q = q.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


async def count_unread(db: AsyncSession, user_id: int) -> int:
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )
    return len(result.scalars().all())


async def mark_read(db: AsyncSession, notification_id: int, user_id: int) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True)
    )


async def mark_all_read(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
