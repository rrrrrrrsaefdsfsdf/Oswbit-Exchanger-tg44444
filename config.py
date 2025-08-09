import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_MODE = os.getenv("BOT_MODE", 'polling')
    
    ONLYPAYS_API_ID = os.getenv("ONLYPAYS_API_ID")
    ONLYPAYS_SECRET_KEY = os.getenv("ONLYPAYS_SECRET_KEY")
    ONLYPAYS_PAYMENT_KEY = os.getenv("ONLYPAYS_PAYMENT_KEY")
    
    PSPWARE_API_KEY = os.getenv("PSPWARE_API_KEY")
    PSPWARE_MERCHANT_ID = os.getenv("PSPWARE_MERCHANT_ID")
    
    GREENGO_API_SECRET = os.getenv("GREENGO_API_SECRET")
    
    NICEPAY_MERCHANT_KEY = os.getenv("NICEPAY_MERCHANT_KEY")
    NICEPAY_MERCHANT_TOKEN_KEY = os.getenv("NICEPAY_MERCHANT_TOKEN_KEY")
    
    DATABASE_URL = os.getenv("DATABASE_URL", "oswaldo_exchanger.db")
    
    # Добавляем новые параметры для системы оборота
    MIRROR_ID = os.getenv("MIRROR_ID", "main_mirror")  # Уникальный ID зеркала
    CENTRAL_DB_PATH = os.getenv("CENTRAL_DB_PATH", "oborot.db")  # Общая база оборота
    
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))
    ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
    OPERATOR_CHAT_ID = int(os.getenv("OPERATOR_CHAT_ID", 0))
    REVIEWS_CHANNEL_ID = int(os.getenv("REVIEWS_CHANNEL_ID", 0))
    
    CAPTCHA_ENABLED = os.getenv("CAPTCHA_ENABLED", "true").lower() == "true"
    MIN_AMOUNT = int(os.getenv("MIN_AMOUNT", 2000))
    MAX_AMOUNT = int(os.getenv("MAX_AMOUNT", 100000))
    
    BOT_USERNAME = os.getenv("BOT_USERNAME", "OswbitExchanger_bot")
    EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "Oswbit Exchanger")
    SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "@")
    SUPPORT_MANAGER = os.getenv("SUPPORT_MANAGER", "@")
    NEWS_CHANNEL = os.getenv("NEWS_CHANNEL", "@")
    REVIEWS_CHANNEL = os.getenv("REVIEWS_CHANNEL", "@")

config = Config()
