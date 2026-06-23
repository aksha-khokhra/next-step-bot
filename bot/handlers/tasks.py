from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.callbacks import PickTaskCallback
from bot.db import async_session
from bot.fsm import clear_work, start_goal
from bot.keyboards import (
    add_task_keyboard,
    my_tasks_keyboard,
    pick_task_keyboard,
    task_actions_keyboard,
)
from bot.messages import format_next_step
from bot.services import decomposer, tasks as task_svc
from bot.states import ManualStep

router = Router()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    text = (message.text or "").removeprefix("/add").strip()
    if not text:
        await message.answer("Usage: /add <task>\nExample: /add Write history essay")
        return
    await _add_task(message, text)


@router.message(Command("list", "breakdown"))
async def cmd_list(message: Message) -> None:
    await send_goal_list(message, message.from_user.id)


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    async with async_session() as session:
        count = await task_svc.count_tasks(session, message.from_user.id)
    await message.answer(
        f"You have *{count}* tasks stored (goals + subtasks).\n\n"
        "To delete **all** of them, send:\n`/confirmclear`",
        parse_mode="Markdown",
    )


@router.message(Command("confirmclear"))
async def cmd_confirm_clear(message: Message, state: FSMContext) -> None:
    async with async_session() as session:
        removed = await task_svc.clear_all_tasks(session, message.from_user.id)
        await session.commit()
    await clear_work(state)
    await message.answer(
        f"Removed {removed} tasks. You're starting fresh.\n\nUse /add when you're ready.",
        reply_markup=add_task_keyboard(),
    )


@router.message(F.text & ~F.text.startswith("/"))
async def free_text_add(message: Message, state: FSMContext) -> None:
    if await state.get_state() == ManualStep.waiting:
        await _save_manual_step(message, state)
        return
    text = (message.text or "").strip()
    if len(text) >= 3:
        await _add_task(message, text)


@router.callback_query(F.data == "menu:add")
async def menu_add(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            "Type your task below, or send /add <task>",
            reply_markup=add_task_keyboard(),
        )


@router.callback_query(F.data == "menu:list")
async def menu_list(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await send_goal_list(callback.message, callback.from_user.id)


@router.callback_query(F.data == "menu:cancel")
async def menu_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Cancelled.")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(PickTaskCallback.filter())
async def on_pick_task(
    callback: CallbackQuery, callback_data: PickTaskCallback, state: FSMContext
) -> None:
    from bot.handlers.next import send_next_step

    await callback.answer()
    user_id = callback.from_user.id
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    async with async_session() as session:
        task = await task_svc.get_task(session, callback_data.task_id, user_id)
        if task is None or task.parent_id is not None:
            await callback.answer("Task not found.", show_alert=True)
            return

        if task.children:
            await start_goal(state, task.id)
            await session.commit()
            if callback.message:
                await send_next_step(callback.message, user_id, state)
            return

        status = None
        if callback.message:
            status = await callback.message.answer("Breaking this down…")
        user = await task_svc.ensure_user(session, user_id)
        children, note = await decomposer.break_down_task(session, user, task)
        await session.commit()
        first = children[0] if children else task

    if callback.message and status:
        await status.delete()

    await start_goal(state, task.id)
    if callback.message:
        await callback.message.answer(
            format_next_step(first, note=None if note == "ok" else note),
            reply_markup=task_actions_keyboard(first.id),
        )


async def send_goal_list(message: Message, user_id: int) -> None:
    async with async_session() as session:
        goals = await task_svc.list_goals(session, user_id)
        in_progress = await task_svc.list_in_progress_goals(session, user_id)
        await session.commit()

    active = {t.id for t in in_progress}
    if not goals:
        await message.answer(
            "No tasks yet. Type one below or send /add <task>.",
            reply_markup=add_task_keyboard(),
        )
        return

    lines = ["*Your tasks*\n"]
    for i, g in enumerate(goals, 1):
        tag = " _(in progress)_" if g.id in active else ""
        lines.append(f"{i}. {g.title}{tag}")
    lines += ["\nTap a task to break down or continue.", "/done — mark a main task finished"]
    await message.answer(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=pick_task_keyboard(goals, in_progress_ids=active),
    )


async def _add_task(message: Message, title: str) -> None:
    async with async_session() as session:
        await task_svc.create_task(session, message.from_user.id, title)
        await session.commit()
    await message.answer(f'Added: "{title}"', reply_markup=my_tasks_keyboard())


async def _save_manual_step(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    parent_id = data.get("parent_task_id")
    if parent_id is None:
        await state.clear()
        return

    title = (message.text or "").strip()
    if len(title) < 3:
        await message.answer("Please type a tiny action (at least 3 characters).")
        return

    user_id = message.from_user.id
    async with async_session() as session:
        parent = await task_svc.get_task(session, parent_id, user_id)
        if parent is None:
            await state.clear()
            await message.answer("That task is gone. Try /add something new.")
            return
        child = await task_svc.create_task(
            session, user_id, title, parent_id=parent.id, estimated_minutes=5
        )
        await session.commit()

    await state.clear()
    await message.answer(
        format_next_step(child),
        reply_markup=task_actions_keyboard(child.id),
    )
