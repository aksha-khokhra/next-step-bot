from aiogram import Router  # pyright: ignore[reportMissingImports]
from aiogram.filters import Command, CommandStart  # pyright: ignore[reportMissingImports]
from aiogram.types import Message  # pyright: ignore[reportMissingImports]

from bot.keyboards import my_tasks_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hi! I'm *Thinklet!* Your personal assistant.\n\n"
        "Add tasks when they come to mind. When you want help, "
        "pick one and I'll break it into small steps — *one* at a time.\n\n"
        "• /add <task> — add a task\n"
        "• /list — your tasks (tap one to break down)\n"
        "• /clear — remove all tasks\n"
        "• /help — reminder",
        parse_mode="Markdown",
        reply_markup=my_tasks_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Commands:\n"
        "/add Write essay — add a task\n"
        "/list — your tasks (tap one to break down or continue)\n"
        "/done — pick which main task you finished\n"
        "/clear — ask for delete confirmation\n"
        "/confirmclear — delete all your tasks\n"
        "/breakdown — same as picking a task from /list\n\n"
        "While working on steps: Next, Too big, Skip, My tasks",
        reply_markup=my_tasks_keyboard(),
    )
