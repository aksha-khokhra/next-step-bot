from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards import main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hi! I'm your *next step* coach.\n\n"
        "Add tasks when they come to mind. When you want help, "
        "pick one and I'll break it into small steps — *one* at a time.\n\n"
        "• /add <task> — add a task\n"
        "• /breakdown — choose a task to split into steps\n"
        "• /next — what to do right now\n"
        "• /list — your tasks\n"
        "• /clear — remove all tasks\n"
        "• /help — reminder",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Commands:\n"
        "/add Write essay — add a task (no breakdown yet)\n"
        "/breakdown — pick a task to split into steps\n"
        "/next — one recommended step\n"
        "/list — your tasks\n"
        "/clear confirm — delete all your tasks\n\n"
        "Buttons: Done, Too big (smaller steps), Snooze 1h",
        reply_markup=main_menu_keyboard(),
    )
