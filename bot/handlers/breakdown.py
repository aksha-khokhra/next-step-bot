from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.callbacks import PickTaskCallback
from bot.db import async_session
from bot.keyboards import main_menu_keyboard, pick_task_keyboard, task_actions_keyboard
from bot.messages import format_next_step
from bot.services import decomposer, tasks as task_svc

router = Router()


async def show_breakdown_picker(message: Message, user_id: int) -> None:
    async with async_session() as session:
        candidates = await task_svc.list_tasks_for_breakdown(session, user_id)
        await session.commit()

    if not candidates:
        await message.answer(
            "No tasks ready to break down.\n\n"
            "Add one with /add, or pick a task that doesn't have sub-steps yet.",
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(
        "Which task do you want help with?\n"
        "I'll split it into small steps.",
        reply_markup=pick_task_keyboard(candidates),
    )


@router.message(Command("breakdown"))
async def cmd_breakdown(message: Message) -> None:
    await show_breakdown_picker(message, message.from_user.id)


@router.callback_query(F.data == "menu:breakdown")
async def menu_breakdown(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await show_breakdown_picker(callback.message, callback.from_user.id)


@router.callback_query(F.data == "menu:cancel")
async def menu_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Cancelled.")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(PickTaskCallback.filter())
async def on_pick_task(
    callback: CallbackQuery, callback_data: PickTaskCallback
) -> None:
    await callback.answer()
    user_id = callback.from_user.id

    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        status = await callback.message.answer("Breaking this down…")

    async with async_session() as session:
        user = await task_svc.ensure_user(session, user_id)
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None:
            if callback.message and status:
                await status.delete()
            await callback.answer("Task not found.", show_alert=True)
            return
        if task_svc.task_has_subtasks(task):
            if callback.message and status:
                await status.delete()
            if callback.message:
                await callback.message.answer(
                    "That task already has steps. Use /next to continue, "
                    "or tap *Too big* on a step to split it further.",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard(),
                )
            return

        children, note = await decomposer.break_down_task(session, user, task)
        await session.commit()
        first = children[0] if children else task

    if callback.message and status:
        await status.delete()

    if callback.message:
        await callback.message.answer(
            format_next_step(first, note=None if note == "ok" else note),
            reply_markup=task_actions_keyboard(first.id),
        )
