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


@router.message(Command("next"))
async def cmd_next(message: Message) -> None:
    await send_next_step(message, message.from_user.id)


async def send_next_step(message: Message, user_id: int) -> None:
    async with async_session() as session:
        task = await get_next_task(session, user_id)
        if task is None:
            pending = await task_svc.list_tasks_for_breakdown(session, user_id)
        await session.commit()

    if task is not None:
        await message.answer(
            format_next_step(task),
            reply_markup=task_actions_keyboard(task.id),
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
async def on_done(callback: CallbackQuery, callback_data: TaskActionCallback) -> None:
    user_id = callback.from_user.id
    async with async_session() as session:
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None:
            await callback.answer("Task not found.", show_alert=True)
            return
        await task_svc.complete_task(session, task)
        await session.commit()

    await callback.answer("Nice — marked done.")
    if callback.message:
        await send_next_step(callback.message, user_id)


@router.callback_query(TaskActionCallback.filter(F.action == "snooze"))
async def on_snooze(callback: CallbackQuery, callback_data: TaskActionCallback) -> None:
    user_id = callback.from_user.id
    async with async_session() as session:
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None:
            await callback.answer("Task not found.", show_alert=True)
            return
        await task_svc.snooze_task(session, task, hours=1)
        await session.commit()

    await callback.answer("Snoozed for 1 hour.")
    if callback.message:
        await send_next_step(callback.message, user_id)


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
