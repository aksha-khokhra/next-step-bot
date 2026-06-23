from aiogram.filters.callback_data import CallbackData


class TaskActionCallback(CallbackData, prefix="task"):
    action: str
    task_id: int


class PickTaskCallback(CallbackData, prefix="pick"):
    task_id: int


class DoneTaskCallback(CallbackData, prefix="done"):
    task_id: int
