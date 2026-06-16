from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.callbacks import PickTaskCallback, TaskActionCallback
from bot.models import Task


def _truncate(text: str, max_len: int = 48) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def task_actions_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Done",
                    callback_data=TaskActionCallback(action="done", task_id=task_id).pack(),
                ),
                InlineKeyboardButton(
                    text="Too big",
                    callback_data=TaskActionCallback(
                        action="too_big", task_id=task_id
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Skip",
                    callback_data=TaskActionCallback(
                        action="skip", task_id=task_id
                    ).pack(),
                ),
            ],
        ]
    )


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="My tasks", callback_data="menu:list"),
                InlineKeyboardButton(
                    text="Break down a task", callback_data="menu:breakdown"
                ),
            ],
        ]
    )


def pick_task_keyboard(tasks: list[Task]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=_truncate(task.title),
                callback_data=PickTaskCallback(task_id=task.id).pack(),
            )
        ]
        for task in tasks
    ]
    rows.append(
        [InlineKeyboardButton(text="Cancel", callback_data="menu:cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)
