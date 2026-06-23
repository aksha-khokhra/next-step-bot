from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks import DoneTaskCallback, TaskActionCallback
from bot.db import async_session
from bot.fsm import (
    active_goal,
    clear_work,
    prune_skipped,
    skip_id,
    skipped_ids,
    unskip_id,
)
from bot.keyboards import add_task_keyboard, my_tasks_keyboard, pick_done_keyboard, task_actions_keyboard
from bot.messages import format_empty, format_next_step
from bot.models import TaskStatus
from bot.services import decomposer, tasks as task_svc
from bot.services.recommender import get_next_task
from bot.states import ManualStep

router = Router()


async def _list_prompt(message: Message, text: str) -> None:
    await message.answer(text, reply_markup=my_tasks_keyboard())


@router.message(Command("done"))
async def cmd_done(message: Message) -> None:
    user_id = message.from_user.id
    async with async_session() as session:
        goals = await task_svc.list_goals(session, user_id)
        await session.commit()
    if not goals:
        await message.answer(
            "No main tasks to mark done. Use /add to add one.",
            reply_markup=add_task_keyboard(),
        )
        return
    await message.answer(
        "Which main task did you finish?",
        reply_markup=pick_done_keyboard(goals),
    )


@router.callback_query(DoneTaskCallback.filter())
async def on_done_goal(
    callback: CallbackQuery, callback_data: DoneTaskCallback, state: FSMContext
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    async with async_session() as session:
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None or task.parent_id is not None:
            await callback.answer("Task not found.", show_alert=True)
            return
        await task_svc.complete_goal(session, task)
        await prune_skipped(state, session, user_id)
        await session.commit()

    if callback.message:
        await callback.message.answer(
            "Nice — marked that task done.",
            reply_markup=my_tasks_keyboard(),
        )


async def send_next_step(message: Message, user_id: int, state: FSMContext) -> None:
    goal_id = await active_goal(state)
    if goal_id is None:
        await _list_prompt(message, "Pick a task from /list first.")
        return

    skipped = await skipped_ids(state)
    async with async_session() as session:
        task = await get_next_task(
            session, user_id, exclude_ids=skipped, goal_id=goal_id
        )
        if task is None:
            goal = await task_svc.get_task(session, goal_id, user_id)
        await session.commit()

    if task is not None:
        await message.answer(
            format_next_step(task),
            reply_markup=task_actions_keyboard(task.id),
        )
        return

    if skipped:
        async with async_session() as session:
            has_more = await get_next_task(session, user_id, goal_id=goal_id)
            await session.commit()
        if has_more:
            await _list_prompt(
                message,
                "No more steps — you skipped the rest on this task.\nOpen /list to switch.",
            )
            return

    await clear_work(state)
    if goal is not None and goal.status == TaskStatus.DONE:
        text = "Nice — you finished all steps for that task.\nOpen /list to pick another."
    elif await _has_other_tasks(user_id):
        text = "No steps left on that task.\nOpen /list to pick another."
    else:
        await message.answer(format_empty(), reply_markup=my_tasks_keyboard())
        return
    await _list_prompt(message, text)


async def _has_other_tasks(user_id: int) -> bool:
    async with async_session() as session:
        goals = await task_svc.list_goals(session, user_id)
        in_progress = await task_svc.list_in_progress_goals(session, user_id)
        await session.commit()
    return bool(goals or in_progress)


@router.callback_query(TaskActionCallback.filter(F.action == "next"))
async def on_next(
    callback: CallbackQuery, callback_data: TaskActionCallback, state: FSMContext
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    async with async_session() as session:
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None:
            await callback.answer("Task not found.", show_alert=True)
            return
        await task_svc.complete_task(session, task)
        await unskip_id(state, task.id)
        await session.commit()
    if callback.message:
        await send_next_step(callback.message, user_id, state)


@router.callback_query(TaskActionCallback.filter(F.action == "skip"))
async def on_skip(
    callback: CallbackQuery, callback_data: TaskActionCallback, state: FSMContext
) -> None:
    await callback.answer()
    await skip_id(state, callback_data.task_id)
    if callback.message:
        await callback.message.answer("Skipped — here's another step:")
        await send_next_step(callback.message, callback.from_user.id, state)


@router.callback_query(TaskActionCallback.filter(F.action == "too_big"))
async def on_too_big(
    callback: CallbackQuery, callback_data: TaskActionCallback, state: FSMContext
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    status = await callback.message.answer("Finding smaller steps…") if callback.message else None

    async with async_session() as session:
        user = await task_svc.ensure_user(session, user_id)
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None:
            if status:
                await status.delete()
            await callback.answer("Task not found.", show_alert=True)
            return
        children, note = await decomposer.break_down_task(
            session, user, task, smaller=True
        )
        await session.commit()
        first = children[0] if children else None

    if status:
        await status.delete()

    if first is None:
        await state.set_state(ManualStep.waiting)
        await state.update_data(parent_task_id=callback_data.task_id)
        if callback.message:
            await callback.message.answer(
                "What's the *tiniest* physical action? (e.g. open laptop, find the PDF)",
                parse_mode="Markdown",
            )
        return

    if callback.message:
        await callback.message.answer(
            format_next_step(first, note=None if note == "ok" else note),
            reply_markup=task_actions_keyboard(first.id),
        )
