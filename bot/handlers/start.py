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
        "• /breakdown — split a task into steps and start\n"
        "• /skip — move to another step\n"
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
        "/breakdown — pick a task and split into steps\n"
        "/skip — skip current step, get another one\n"
        "/done — mark current step done\n"
        "/list — your tasks\n"
        "/clear confirm — delete all your tasks\n\n"
        "Buttons: Done, Too big (smaller steps), Skip",
        reply_markup=main_menu_keyboard(),
    )
