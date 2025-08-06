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
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

async def on_startup():
    try:
        await init_database()
        
        if config.USE_WEBHOOK:
            await bot.set_webhook(url=config.WEBHOOK_URL + config.WEBHOOK_PATH, 
                                drop_pending_updates=True)
            logger.info("Webhook set successfully")
        
        logger.info("Bot startup completed")
    except Exception as e:
        logger.error(f"Startup error: {e}")
        raise

async def on_shutdown():
    try:
        if config.USE_WEBHOOK:
            await bot.delete_webhook()
            logger.info("Webhook deleted")
        
        await bot.session.close()
        logger.info("Bot shutdown completed")
    except Exception as e:
        logger.error(f"Shutdown error: {e}")

def create_app() -> web.Application:
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    return app

async def run_polling():
    logger.info("Starting bot in polling mode")
    try:
        await init_database()
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, skip_updates=True)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Polling error: {e}")
        raise
    finally:
        await on_shutdown()

async def run_webhook():
    logger.info("Starting bot in webhook mode")
    try:
        await on_startup()
        
        app = create_app()
        runner = web.AppRunner(app)
        await runner.setup()
        
        site = web.TCPSite(runner, host=config.WEBHOOK_HOST, port=config.WEBHOOK_PORT)
        await site.start()
        
        logger.info(f"Webhook server started on {config.WEBHOOK_HOST}:{config.WEBHOOK_PORT}")
        
                         
        await asyncio.Event().wait()
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise
    finally:
        await on_shutdown()

async def main():
    mode = os.getenv('BOT_MODE', 'polling').lower()
    
    if mode == 'webhook' and config.USE_WEBHOOK:
        await run_webhook()
    else:
        await run_polling()

if __name__ == "__main__":
    asyncio.run(main())
