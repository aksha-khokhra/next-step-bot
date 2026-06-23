from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Task, TaskStatus

SKIPPED_KEY = "skipped_task_ids"
GOAL_KEY = "active_goal_id"


async def skipped_ids(state: FSMContext) -> set[int]:
    return set((await state.get_data()).get(SKIPPED_KEY, []))


async def skip_id(state: FSMContext, task_id: int) -> None:
    ids = await skipped_ids(state)
    ids.add(task_id)
    await state.update_data(**{SKIPPED_KEY: list(ids)})


async def unskip_id(state: FSMContext, task_id: int) -> None:
    ids = await skipped_ids(state)
    ids.discard(task_id)
    await state.update_data(**{SKIPPED_KEY: list(ids)})


async def active_goal(state: FSMContext) -> int | None:
    goal_id = (await state.get_data()).get(GOAL_KEY)
    return int(goal_id) if goal_id is not None else None


async def start_goal(state: FSMContext, goal_id: int) -> None:
    await state.update_data(**{GOAL_KEY: goal_id, SKIPPED_KEY: []})


async def clear_work(state: FSMContext) -> None:
    await state.update_data(**{GOAL_KEY: None, SKIPPED_KEY: []})


async def prune_skipped(
    state: FSMContext, session: AsyncSession, user_id: int
) -> None:
    ids = await skipped_ids(state)
    if not ids:
        return
    result = await session.execute(
        select(Task).where(Task.user_id == user_id, Task.id.in_(ids))
    )
    pending = {t.id for t in result.scalars().all() if t.status == TaskStatus.PENDING}
    await state.update_data(**{SKIPPED_KEY: list(pending)})
