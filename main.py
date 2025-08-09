import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

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

async def init_database():
                                   
    try:
        db = Database(config.DATABASE_URL)
        await db.init_db()
        await db.init_turnover_db()
        logger.info(f"База данных инициализирована")
        logger.info(f"Oborot DB: {config.CENTRAL_DB_PATH}")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        raise

async def create_bot_instance(token, mirror_id):
                                                         
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
                                                        
                                                             
    import importlib
    
                                       
    admin_module = importlib.reload(admin)
    user_module = importlib.reload(user)
    operator_module = importlib.reload(operator)
    calculator_module = importlib.reload(calculator)
    
                             
    dp.include_router(admin_module.router)
    dp.include_router(user_module.router)
    dp.include_router(operator_module.router)
    dp.include_router(calculator_module.router)
    
                          
    dp.message.middleware(PrivateChatMiddleware())
    dp.callback_query.middleware(PrivateChatMiddleware())
    
                                    
    bot.mirror_id = mirror_id
    bot.mirror_config = config.get_mirror_config(mirror_id)
    
    return bot, dp

async def run_bot_polling(bot, dp, mirror_id):
                                                 
    try:
        logger.info(f"Запуск бота: {mirror_id}")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Ошибка в боте {mirror_id}: {e}")
        raise
    finally:
        try:
            await bot.session.close()
        except Exception as e:
            logger.error(f"Ошибка закрытия сессии бота {mirror_id}: {e}")

async def run_polling():
                                            
    await init_database()
    
    tasks = []
    
                  
    try:
        main_bot, main_dp = await create_bot_instance(config.BOT_TOKEN, "main")
        tasks.append(asyncio.create_task(
            run_bot_polling(main_bot, main_dp, "main"),
            name="main_bot"
        ))
        logger.info(f"Основной бот запущен с MIRROR_ID: {config.MIRROR_ID}")
    except Exception as e:
        logger.error(f"Ошибка создания основного бота: {e}")
        raise
    
                                        
    if hasattr(config, 'MIRROR_BOT_TOKENS') and config.MIRROR_BOT_TOKENS:
        for i, mirror_token in enumerate(config.MIRROR_BOT_TOKENS):
            mirror_token = mirror_token.strip()
            if mirror_token:
                try:
                    mirror_id = f"mirror_{i+1}"
                    mirror_bot, mirror_dp = await create_bot_instance(mirror_token, mirror_id)
                    tasks.append(asyncio.create_task(
                        run_bot_polling(mirror_bot, mirror_dp, mirror_id),
                        name=f"mirror_bot_{i+1}"
                    ))
                    logger.info(f"Зеркальный бот {mirror_id} добавлен в очередь запуска")
                except Exception as e:
                    logger.error(f"Ошибка создания зеркального бота {i+1}: {e}")
                    continue
    
                                    
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        logger.info("Все боты остановлены пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка в polling: {e}")
        raise

async def on_shutdown():
                                   
    try:
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        
        for task in tasks:
            task.cancel()
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        logger.info("Все задачи завершены")
    except Exception as e:
        logger.error(f"Ошибка при завершении работы: {e}")

async def main():
                                 
    try:
        await run_polling()
    except KeyboardInterrupt:
        logger.info("Основной процесс остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        raise
    finally:
        await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Программа завершена")
    except Exception as e:
        logger.error(f"Фатальная ошибка: {e}")
    finally:
        logger.info("Завершение работы программы")
