import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import config
from database.models import Database
from handlers import user, admin, operator, calculator
from middlewares.chat_type import PrivateChatMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs.log", encoding="utf-8", mode="a")
    ]
)

logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(admin.router)
dp.include_router(user.router)
dp.include_router(operator.router)
dp.include_router(calculator.router)

dp.message.middleware(PrivateChatMiddleware())
dp.callback_query.middleware(PrivateChatMiddleware())

async def init_database():
    try:
        db = Database(config.DATABASE_URL)
        await db.init_db()
        await db.init_turnover_db()
        logger.info(f"Bot started with MIRROR_ID: {config.MIRROR_ID}")                   
        logger.info(f"Oborot DB: {config.CENTRAL_DB_PATH}")                     

    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        raise

async def on_shutdown():
    try:
        await bot.session.close()
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")

async def run_polling():
    try:
        await init_database()
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка polling: {e}")
        raise
    finally:
        await on_shutdown()

async def main():
    try:
        await run_polling()
    except KeyboardInterrupt:
        logger.info("Основной процесс остановлен пользователем")
    finally:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            tasks = [task for task in asyncio.all_tasks(loop) if task is not asyncio.current_task(loop)]
            for task in tasks:
                task.cancel()
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

if __name__ == "__main__":
    asyncio.run(main())