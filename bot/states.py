from aiogram.fsm.state import State, StatesGroup


class ManualStep(StatesGroup):
    waiting = State()
