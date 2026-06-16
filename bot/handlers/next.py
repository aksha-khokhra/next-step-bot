from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks import TaskActionCallback
from bot.db import async_session
from bot.states import ManualStep
from bot.keyboards import main_menu_keyboard, task_actions_keyboard
from bot.messages import format_empty, format_next_step
from bot.services import decomposer, tasks as task_svc
from bot.services.recommender import get_next_task

router = Router()

SKIPPED_IDS_KEY = "skipped_task_ids"


async def _get_skipped_ids(state: FSMContext) -> set[int]:
    data = await state.get_data()
    return set(data.get(SKIPPED_IDS_KEY, []))


async def _add_skipped_id(state: FSMContext, task_id: int) -> None:
    skipped = await _get_skipped_ids(state)
    skipped.add(task_id)
    await state.update_data(**{SKIPPED_IDS_KEY: list(skipped)})


async def _clear_skipped_ids(state: FSMContext) -> None:
    await state.update_data(**{SKIPPED_IDS_KEY: []})


@router.message(Command("done"))
async def cmd_done(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    skipped = await _get_skipped_ids(state)
    async with async_session() as session:
        task = await get_next_task(session, user_id, exclude_ids=skipped)
        if task is None:
            await session.commit()
            await message.answer("Nothing to mark done right now.")
            return
        await task_svc.complete_task(session, task)
        skipped.discard(task.id)
        await state.update_data(**{SKIPPED_IDS_KEY: list(skipped)})
        await session.commit()

    await message.answer("Nice — marked done.")
    await send_next_step(message, user_id, state)


@router.message(Command("skip"))
async def cmd_skip(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    skipped = await _get_skipped_ids(state)
    async with async_session() as session:
        current = await get_next_task(session, user_id, exclude_ids=skipped)
        await session.commit()

    if current is None:
        await message.answer(
            "Nothing to skip. Use /breakdown to start on a task.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await _add_skipped_id(state, current.id)
    await message.answer("Skipped — here's another step:")
    await send_next_step(message, user_id, state)


async def send_next_step(
    message: Message,
    user_id: int,
    state: FSMContext,
    *,
    max_minutes: int | None = None,
) -> None:
    skipped = await _get_skipped_ids(state)
    async with async_session() as session:
        task = await get_next_task(
            session, user_id, max_minutes=max_minutes, exclude_ids=skipped
        )
        if task is None:
            pending = await task_svc.list_tasks_for_breakdown(session, user_id)
        await session.commit()

    if task is not None:
        await message.answer(
            format_next_step(task),
            reply_markup=task_actions_keyboard(task.id),
        )
        return

    if skipped:
        async with async_session() as session:
            has_more = await get_next_task(session, user_id, exclude_ids=set())
            await session.commit()
        if has_more is not None:
            await message.answer(
                "No more steps to show — you skipped the rest.\n"
                "Use /done when you finish a step, or /breakdown for another task.",
                reply_markup=main_menu_keyboard(),
            )
            return

    if pending:
        await message.answer(
            "You have tasks on your list but no steps yet.\n\n"
            "Use /breakdown to pick one and split it into small steps.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(format_empty(), reply_markup=main_menu_keyboard())


@router.callback_query(TaskActionCallback.filter(F.action == "done"))
async def on_done(
    callback: CallbackQuery, callback_data: TaskActionCallback, state: FSMContext
) -> None:
    user_id = callback.from_user.id
    async with async_session() as session:
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None:
            await callback.answer("Task not found.", show_alert=True)
            return
        await task_svc.complete_task(session, task)
        skipped = await _get_skipped_ids(state)
        skipped.discard(task.id)
        await state.update_data(**{SKIPPED_IDS_KEY: list(skipped)})
        await session.commit()

    await callback.answer("Nice — marked done.")
    if callback.message:
        await send_next_step(callback.message, user_id, state)


@router.callback_query(TaskActionCallback.filter(F.action == "skip"))
async def on_skip(
    callback: CallbackQuery, callback_data: TaskActionCallback, state: FSMContext
) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    skipped = await _get_skipped_ids(state)
    skipped.add(callback_data.task_id)
    await state.update_data(**{SKIPPED_IDS_KEY: list(skipped)})

    if callback.message:
        await callback.message.answer("Skipped — here's another step:")
        await send_next_step(callback.message, user_id, state)


@router.callback_query(TaskActionCallback.filter(F.action == "too_big"))
async def on_too_big(
    callback: CallbackQuery,
    callback_data: TaskActionCallback,
    state: FSMContext,
) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    status = None
    if callback.message:
        status = await callback.message.answer("Finding smaller steps…")

    async with async_session() as session:
        user = await task_svc.ensure_user(session, user_id)
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None:
            if callback.message and status:
                await status.delete()
            await callback.answer("Task not found.", show_alert=True)
            return

        children, note = await decomposer.break_down_task(
            session, user, task, smaller=True
        )
        await session.commit()
        first = children[0] if children else None

    if callback.message and status:
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
