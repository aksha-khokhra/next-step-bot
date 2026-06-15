from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.models import Task, TaskStatus, User


async def ensure_user(session: AsyncSession, telegram_id: int) -> User:
    user = await session.get(User, telegram_id)
    if user is None:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.flush()
    return user


async def create_task(
    session: AsyncSession,
    user_id: int,
    title: str,
    *,
    parent_id: int | None = None,
    estimated_minutes: int | None = None,
) -> Task:
    await ensure_user(session, user_id)
    task = Task(
        user_id=user_id,
        parent_id=parent_id,
        title=title.strip(),
        estimated_minutes=estimated_minutes,
    )
    session.add(task)
    await session.flush()
    return task


async def get_task(
    session: AsyncSession, task_id: int, user_id: int
) -> Task | None:
    result = await session.execute(
        select(Task)
        .where(Task.id == task_id, Task.user_id == user_id)
        .options(selectinload(Task.children))
    )
    return result.scalar_one_or_none()


async def complete_task(session: AsyncSession, task: Task) -> None:
    now = datetime.now(UTC)
    task.status = TaskStatus.DONE
    task.completed_at = now
    task.snoozed_until = None

    if task.parent_id is not None:
        parent = await get_task(session, task.parent_id, task.user_id)
        if parent is not None:
            siblings = await session.execute(
                select(Task).where(Task.parent_id == parent.id)
            )
            children = list(siblings.scalars().all())
            if children and all(c.status == TaskStatus.DONE for c in children):
                await complete_task(session, parent)


async def snooze_task(session: AsyncSession, task: Task, hours: int = 1) -> None:
    task.status = TaskStatus.SNOOZED
    task.snoozed_until = datetime.now(UTC) + timedelta(hours=hours)


async def list_goals(session: AsyncSession, user_id: int, limit: int = 5) -> list[Task]:
    result = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.parent_id.is_(None),
            Task.status == TaskStatus.PENDING,
        )
        .order_by(Task.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def list_tasks_for_breakdown(
    session: AsyncSession, user_id: int, limit: int = 10
) -> list[Task]:
    """Pending root tasks that have not been broken into subtasks yet."""
    result = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.parent_id.is_(None),
            Task.status == TaskStatus.PENDING,
        )
        .options(selectinload(Task.children))
        .order_by(Task.created_at.desc())
        .limit(limit)
    )
    return [t for t in result.scalars().all() if not t.children]


def task_has_subtasks(task: Task) -> bool:
    return bool(task.children)


async def get_pending_leaves(session: AsyncSession, user_id: int) -> list[Task]:
    now = datetime.now(UTC)
    result = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            or_(
                Task.status == TaskStatus.PENDING,
                and_(
                    Task.status == TaskStatus.SNOOZED,
                    Task.snoozed_until.is_not(None),
                    Task.snoozed_until <= now,
                ),
            ),
        )
        .options(selectinload(Task.children))
    )
    all_pending = list(result.scalars().all())

    leaves: list[Task] = []
    for task in all_pending:
        active_children = [
            c
            for c in task.children
            if c.status == TaskStatus.PENDING
            or (
                c.status == TaskStatus.SNOOZED
                and c.snoozed_until
                and c.snoozed_until <= now
            )
        ]
        if not active_children:
            leaves.append(task)
    return leaves


def can_breakdown(user: User) -> bool:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if user.breakdowns_date != today:
        return True
    from bot.config import settings

    return user.breakdowns_today < settings.max_breakdowns_per_day


async def count_tasks(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(func.count()).select_from(Task).where(Task.user_id == user_id)
    )
    return int(result.scalar_one())


async def clear_all_tasks(session: AsyncSession, user_id: int) -> int:
    count = await count_tasks(session, user_id)
    await session.execute(delete(Task).where(Task.user_id == user_id))
    user = await session.get(User, user_id)
    if user is not None:
        user.breakdowns_today = 0
        user.breakdowns_date = None
    return count


async def record_breakdown(session: AsyncSession, user: User) -> None:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    if user.breakdowns_date != today:
        user.breakdowns_date = today
        user.breakdowns_today = 0
    user.breakdowns_today += 1
