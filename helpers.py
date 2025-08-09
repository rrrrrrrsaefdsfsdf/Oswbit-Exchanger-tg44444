            
from config import config

def get_mirror_config(bot):
\
\
\
\
\
\
\
\
       
    mirror_id = getattr(bot, 'mirror_id', 'main')
    
    return {
        'BOT_USERNAME': config.get_config_value(mirror_id, 'BOT_USERNAME'),
        'EXCHANGE_NAME': config.get_config_value(mirror_id, 'EXCHANGE_NAME'),
        'SUPPORT_CHAT': config.get_config_value(mirror_id, 'SUPPORT_CHAT'),
        'SUPPORT_MANAGER': config.get_config_value(mirror_id, 'SUPPORT_MANAGER'),
        'NEWS_CHANNEL': config.get_config_value(mirror_id, 'NEWS_CHANNEL'),
        'REVIEWS_CHANNEL': config.get_config_value(mirror_id, 'REVIEWS_CHANNEL'),
        'ADMIN_USER_ID': config.get_config_value(mirror_id, 'ADMIN_USER_ID'),
        'ADMIN_CHAT_ID': config.get_config_value(mirror_id, 'ADMIN_CHAT_ID'),
        'OPERATOR_CHAT_ID': config.get_config_value(mirror_id, 'OPERATOR_CHAT_ID'),
        'REVIEWS_CHANNEL_ID': config.get_config_value(mirror_id, 'REVIEWS_CHANNEL_ID'),
    }

def get_mirror_id(bot):
\
\
\
\
\
\
\
\
       
    return getattr(bot, 'mirror_id', 'main')

def get_config_value(bot, key, default=None):
\
\
\
\
\
\
\
\
\
\
       
    mirror_id = get_mirror_id(bot)
    return config.get_config_value(mirror_id, key, default)

def is_admin(user_id: int, bot=None):
\
\
\
\
\
\
\
\
\
       
    if bot:
        admin_id = get_config_value(bot, 'ADMIN_USER_ID')
        return user_id == admin_id
    return user_id == config.ADMIN_USER_ID

def is_operator_chat(chat_id: int, bot=None):
\
\
\
\
\
\
\
\
\
       
    if bot:
        operator_chat_id = get_config_value(bot, 'OPERATOR_CHAT_ID')
        return chat_id == operator_chat_id
    return chat_id == config.OPERATOR_CHAT_ID

def is_admin_chat(chat_id: int, bot=None):
\
\
\
\
\
\
\
\
\
       
    if bot:
        admin_chat_id = get_config_value(bot, 'ADMIN_CHAT_ID')
        return chat_id == admin_chat_id
    return chat_id == config.ADMIN_CHAT_ID

def format_exchange_info(bot):
\
\
\
\
\
\
\
\
       
    mirror_config = get_mirror_config(bot)
    
    return {
        'welcome_text': f"🥷 Добро пожаловать в {mirror_config['EXCHANGE_NAME']}, ниндзя!",
        'support_info': f"Оператор: {mirror_config['SUPPORT_MANAGER']}",
        'news_info': f"Канал: {mirror_config['NEWS_CHANNEL']}",
        'referral_link': f"https://t.me/{mirror_config['BOT_USERNAME']}?start=r-{{user_id}}"
    }

def get_referral_link(bot, user_id: int):
\
\
\
\
\
\
\
\
\
       
    bot_username = get_config_value(bot, 'BOT_USERNAME')
    return f"https://t.me/{bot_username}?start=r-{user_id}"

                                                              
def with_mirror_config(func):
\
\
\
       
    import functools
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
                                             
        bot = None
        for arg in args:
            if hasattr(arg, 'bot'):
                bot = arg.bot
                break
        
        if bot:
            kwargs['mirror_config'] = get_mirror_config(bot)
        
        return await func(*args, **kwargs)
    
    return wrapper

                                                   
class CommonConfig:
                                                  
    
    @staticmethod
    def get_min_amount():
        return config.MIN_AMOUNT
    
    @staticmethod
    def get_max_amount():
        return config.MAX_AMOUNT
    
    @staticmethod
    def get_commission_percent():
        return getattr(config, 'COMMISSION_PERCENT', 20.0)
    
    @staticmethod
    def is_captcha_enabled():
        return config.CAPTCHA_ENABLED
    
    @staticmethod
    def get_database_url():
        return config.DATABASE_URL
    
    @staticmethod
    def get_central_db_path():
        return config.CENTRAL_DB_PATH
