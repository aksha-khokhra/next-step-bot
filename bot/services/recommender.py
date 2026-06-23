from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Task
from bot.services import tasks as task_svc
from bot.services.tasks import root_id


def pick_next(
    leaves: list[Task],
    all_tasks: list[Task],
    *,
    max_minutes: int | None = None,
    exclude_ids: set[int] | None = None,
) -> Task | None:
    excluded = exclude_ids or set()
    eligible = [
        t
        for t in leaves
        if t.id not in excluded
        and (
            max_minutes is None
            or (t.estimated_minutes if t.estimated_minutes is not None else 999)
            <= max_minutes
        )
    ]
    if not eligible:
        return None

    by_id = {t.id: t for t in all_tasks}

    def sort_key(t: Task) -> tuple:
        depth = 0
        current = t
        while current.parent_id is not None:
            depth += 1
            parent = by_id.get(current.parent_id)
            if parent is None:
                break
            current = parent
        minutes = t.estimated_minutes if t.estimated_minutes is not None else 999
        created = t.created_at or datetime.min.replace(tzinfo=UTC)
        return (depth, minutes, -t.priority, created)

    return min(eligible, key=sort_key)


async def get_next_task(
    session: AsyncSession,
    user_id: int,
    *,
    max_minutes: int | None = None,
    exclude_ids: set[int] | None = None,
    goal_id: int | None = None,
) -> Task | None:
    leaves = await task_svc.get_pending_leaves(session, user_id)
    result = await session.execute(select(Task).where(Task.user_id == user_id))
    all_tasks = list(result.scalars().all())
    by_id = {t.id: t for t in all_tasks}

    subtask_leaves = [t for t in leaves if t.parent_id is not None]
    if goal_id is not None:
        subtask_leaves = [t for t in subtask_leaves if root_id(t, by_id) == goal_id]

    if not subtask_leaves:
        return None
    return pick_next(
        subtask_leaves, all_tasks, max_minutes=max_minutes, exclude_ids=exclude_ids
    )
