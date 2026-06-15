from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Task, TaskStatus
from bot.services import tasks as task_svc


def _depth(task: Task, by_id: dict[int, Task]) -> int:
    depth = 0
    current = task
    while current.parent_id is not None:
        depth += 1
        parent = by_id.get(current.parent_id)
        if parent is None:
            break
        current = parent
    return depth


def pick_next(leaves: list[Task], all_tasks: list[Task]) -> Task | None:
    if not leaves:
        return None

    now = datetime.now(UTC)
    eligible: list[Task] = []
    for task in leaves:
        if task.status == TaskStatus.SNOOZED:
            if task.snoozed_until and task.snoozed_until > now:
                continue
            task.status = TaskStatus.PENDING
            task.snoozed_until = None
        eligible.append(task)

    if not eligible:
        return None

    by_id = {t.id: t for t in all_tasks}

    def sort_key(t: Task) -> tuple:
        depth = _depth(t, by_id)
        minutes = t.estimated_minutes if t.estimated_minutes is not None else 999
        created = t.created_at or datetime.min.replace(tzinfo=UTC)
        return (depth, minutes, -t.priority, created)

    return min(eligible, key=sort_key)


async def get_next_task(session: AsyncSession, user_id: int) -> Task | None:
    leaves = await task_svc.get_pending_leaves(session, user_id)
    result = await session.execute(select(Task).where(Task.user_id == user_id))
    all_tasks = list(result.scalars().all())

    subtask_leaves = [t for t in leaves if t.parent_id is not None]
    if subtask_leaves:
        return pick_next(subtask_leaves, all_tasks)

    return None
