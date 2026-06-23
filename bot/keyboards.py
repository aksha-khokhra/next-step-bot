from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup  # pyright: ignore[reportMissingImports]

from bot.callbacks import DoneTaskCallback, PickTaskCallback, TaskActionCallback
from bot.models import Task


def _truncate(text: str, max_len: int = 48) -> str:
    text = text.strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _btn(text: str, callback_data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=_truncate(text), callback_data=callback_data)


def task_actions_keyboard(task_id: int) -> InlineKeyboardMarkup:
    pack = lambda action: TaskActionCallback(action=action, task_id=task_id).pack()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _btn("Next", pack("next")),
                _btn("Too big", pack("too_big")),
                _btn("Skip", pack("skip")),
            ],
            [_btn("My tasks", "menu:list")],
        ]
    )


def my_tasks_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("My tasks", "menu:list")]]
    )


def add_task_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[_btn("Add task", "menu:add")]]
    )


def _task_picker(
    tasks: list[Task],
    callback_cls: type[DoneTaskCallback] | type[PickTaskCallback],
    *,
    in_progress_ids: set[int] | None = None,
) -> InlineKeyboardMarkup:
    active = in_progress_ids or set()
    rows = [
        [
            _btn(
                f"▶ {t.title}" if t.id in active else t.title,
                callback_cls(task_id=t.id).pack(),
            )
        ]
        for t in tasks
    ]
    rows.append([_btn("Cancel", "menu:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pick_done_keyboard(tasks: list[Task]) -> InlineKeyboardMarkup:
    return _task_picker(tasks, DoneTaskCallback)


def pick_task_keyboard(
    tasks: list[Task], *, in_progress_ids: set[int] | None = None
) -> InlineKeyboardMarkup:
    return _task_picker(tasks, PickTaskCallback, in_progress_ids=in_progress_ids)
