from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.db import async_session
from bot.keyboards import main_menu_keyboard, task_actions_keyboard
from bot.messages import format_next_step
from bot.services import tasks as task_svc
from bot.states import ManualStep

router = Router()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    text = (message.text or "").removeprefix("/add").strip()
    if not text:
        await message.answer(
            "Usage: /add <task>\nExample: /add Write history essay"
        )
        return
    await _add_task(message, text, state)


@router.message(Command("clear"))
async def cmd_clear(message: Message, state: FSMContext) -> None:
    args = (message.text or "").split(maxsplit=1)
    if len(args) < 2 or args[1].strip().lower() != "confirm":
        async with async_session() as session:
            count = await task_svc.count_tasks(session, message.from_user.id)
        await message.answer(
            f"You have *{count}* tasks stored (goals + subtasks).\n\n"
            "To delete **all** of them, send:\n"
            "`/clear confirm`",
            parse_mode="Markdown",
        )
        return

    async with async_session() as session:
        removed = await task_svc.clear_all_tasks(session, message.from_user.id)
        await session.commit()

    from bot.handlers.next import _clear_skipped_ids

    await _clear_skipped_ids(state)

    await message.answer(
        f"Removed {removed} tasks. You're starting fresh.\n\nUse /add when you're ready.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    await _send_goal_list(message, message.from_user.id)


async def _send_goal_list(message: Message, user_id: int) -> None:
    async with async_session() as session:
        goals = await task_svc.list_goals(session, user_id)
        await session.commit()

    if not goals:
        await message.answer(
            "No tasks yet. Use /add to add one.",
            reply_markup=main_menu_keyboard(),
        )
        return

    lines = ["*Your tasks*:\n"]
    for i, g in enumerate(goals, 1):
        lines.append(f"{i}. {g.title}")
    lines.append("\n/breakdown — split a task into steps")
    await message.answer(
        "\n".join(lines), parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )


@router.message(F.text & ~F.text.startswith("/"))
async def free_text_add(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current == ManualStep.waiting:
        await _save_manual_step(message, state)
        return

    if len((message.text or "").strip()) < 3:
        return

    await _add_task(message, message.text.strip(), state)


async def _add_task(message: Message, title: str, state: FSMContext) -> None:
    user_id = message.from_user.id

    async with async_session() as session:
        await task_svc.create_task(session, user_id, title)
        await session.commit()

    await message.answer(
        f'Added: "{title}"\n\n'
        "When you're ready, use /breakdown to split it into steps.",
        reply_markup=main_menu_keyboard(),
    )


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
        child_id = child.id

    await state.clear()
    async with async_session() as session:
        child = await task_svc.get_task(session, child_id, user_id)
        await session.commit()

    if child is None:
        await message.answer("Something went wrong. Try /breakdown.")
        return

    await message.answer(
        format_next_step(child),
        reply_markup=task_actions_keyboard(child.id),
    )


@router.callback_query(F.data == "menu:list")
async def menu_list(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message:
        await _send_goal_list(callback.message, callback.from_user.id)

