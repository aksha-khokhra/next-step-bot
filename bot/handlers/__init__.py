from aiogram import Router

from bot.handlers import next, start, tasks

router = Router()
router.include_router(start.router)
router.include_router(tasks.router)
router.include_router(next.router)
