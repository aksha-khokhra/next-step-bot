import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.db import init_db
from bot.handlers import router
from bot.services.decomposer import warm_ollama

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()
    logger.info("Warming up Ollama (%s)...", settings.ollama_model)
    if await warm_ollama():
        logger.info("Ready — Ollama connected at %s", settings.ollama_base_url)
    else:
        logger.error(
            "Ollama NOT connected — open the Ollama app, wait ~10s, then restart this bot."
        )
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
