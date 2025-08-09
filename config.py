import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_MODE = os.getenv("BOT_MODE", 'polling')
    
                             
    MIRROR_BOT_TOKENS = []
    
                                      
    MIRROR_CONFIGS = {}
    
                                       
    ONLYPAYS_API_ID = os.getenv("ONLYPAYS_API_ID")
    ONLYPAYS_SECRET_KEY = os.getenv("ONLYPAYS_SECRET_KEY")
    ONLYPAYS_PAYMENT_KEY = os.getenv("ONLYPAYS_PAYMENT_KEY")
    
    PSPWARE_API_KEY = os.getenv("PSPWARE_API_KEY")
    PSPWARE_MERCHANT_ID = os.getenv("PSPWARE_MERCHANT_ID")
    
    GREENGO_API_SECRET = os.getenv("GREENGO_API_SECRET")
    
    NICEPAY_MERCHANT_KEY = os.getenv("NICEPAY_MERCHANT_KEY")
    NICEPAY_MERCHANT_TOKEN_KEY = os.getenv("NICEPAY_MERCHANT_TOKEN_KEY")
    
                     
    DATABASE_URL = os.getenv("DATABASE_URL", "oswaldo_exchanger.db")
    MIRROR_ID = os.getenv("MIRROR_ID", "main_mirror")
    CENTRAL_DB_PATH = os.getenv("CENTRAL_DB_PATH", "oborot.db")
    
    CAPTCHA_ENABLED = os.getenv("CAPTCHA_ENABLED", "true").lower() == "true"
    MIN_AMOUNT = int(os.getenv("MIN_AMOUNT", 2000))
    MAX_AMOUNT = int(os.getenv("MAX_AMOUNT", 100000))
    
                                             
    ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", 0))
    ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", 0))
    OPERATOR_CHAT_ID = int(os.getenv("OPERATOR_CHAT_ID", 0))
    REVIEWS_CHANNEL_ID = int(os.getenv("REVIEWS_CHANNEL_ID", 0))
    
    BOT_USERNAME = os.getenv("BOT_USERNAME", "OswbitExchanger_bot")
    EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "Oswbit Exchanger")
    SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "@")
    SUPPORT_MANAGER = os.getenv("SUPPORT_MANAGER", "@")
    NEWS_CHANNEL = os.getenv("NEWS_CHANNEL", "@")
    REVIEWS_CHANNEL = os.getenv("REVIEWS_CHANNEL", "@")
    
    def __init__(self):
                                        
        self._parse_mirror_tokens()
        self._parse_mirror_configs()
    
    def _parse_mirror_tokens(self):
                                              
        mirror_tokens = os.getenv("MIRROR_BOT_TOKENS", "")
        if mirror_tokens.strip():
            self.MIRROR_BOT_TOKENS = [
                token.strip() 
                for token in mirror_tokens.split(",") 
                if token.strip()
            ]
    
    def _parse_mirror_configs(self):
                                             
                                            
        mirror_configs_json = os.getenv("MIRROR_CONFIGS", "{}")
        try:
            self.MIRROR_CONFIGS = json.loads(mirror_configs_json)
        except json.JSONDecodeError:
            self.MIRROR_CONFIGS = {}
        
                                                           
        for i in range(len(self.MIRROR_BOT_TOKENS)):
            mirror_key = f"mirror_{i+1}"
            
                                                                               
            if mirror_key not in self.MIRROR_CONFIGS:
                self.MIRROR_CONFIGS[mirror_key] = {}
            
                                                         
            mirror_config = self.MIRROR_CONFIGS[mirror_key]
            
                                            
            mirror_config.update({
                'BOT_USERNAME': os.getenv(f"MIRROR_{i+1}_BOT_USERNAME", self.BOT_USERNAME),
                'EXCHANGE_NAME': os.getenv(f"MIRROR_{i+1}_EXCHANGE_NAME", self.EXCHANGE_NAME),
                'SUPPORT_CHAT': os.getenv(f"MIRROR_{i+1}_SUPPORT_CHAT", self.SUPPORT_CHAT),
                'SUPPORT_MANAGER': os.getenv(f"MIRROR_{i+1}_SUPPORT_MANAGER", self.SUPPORT_MANAGER),
                'NEWS_CHANNEL': os.getenv(f"MIRROR_{i+1}_NEWS_CHANNEL", self.NEWS_CHANNEL),
                'REVIEWS_CHANNEL': os.getenv(f"MIRROR_{i+1}_REVIEWS_CHANNEL", self.REVIEWS_CHANNEL),
                
                                                      
                'ADMIN_USER_ID': int(os.getenv(f"MIRROR_{i+1}_ADMIN_USER_ID", self.ADMIN_USER_ID)),
                'ADMIN_CHAT_ID': int(os.getenv(f"MIRROR_{i+1}_ADMIN_CHAT_ID", self.ADMIN_CHAT_ID)),
                'OPERATOR_CHAT_ID': int(os.getenv(f"MIRROR_{i+1}_OPERATOR_CHAT_ID", self.OPERATOR_CHAT_ID)),
                'REVIEWS_CHANNEL_ID': int(os.getenv(f"MIRROR_{i+1}_REVIEWS_CHANNEL_ID", self.REVIEWS_CHANNEL_ID)),
            })
    
    def get_mirror_config(self, mirror_id):
                                                           
        if mirror_id == "main":
            return {
                'BOT_USERNAME': self.BOT_USERNAME,
                'EXCHANGE_NAME': self.EXCHANGE_NAME,
                'SUPPORT_CHAT': self.SUPPORT_CHAT,
                'SUPPORT_MANAGER': self.SUPPORT_MANAGER,
                'NEWS_CHANNEL': self.NEWS_CHANNEL,
                'REVIEWS_CHANNEL': self.REVIEWS_CHANNEL,
                'ADMIN_USER_ID': self.ADMIN_USER_ID,
                'ADMIN_CHAT_ID': self.ADMIN_CHAT_ID,
                'OPERATOR_CHAT_ID': self.OPERATOR_CHAT_ID,
                'REVIEWS_CHANNEL_ID': self.REVIEWS_CHANNEL_ID,
            }
        
        return self.MIRROR_CONFIGS.get(mirror_id, {})
    
    def get_config_value(self, mirror_id, key, default=None):
                                                                    
        mirror_config = self.get_mirror_config(mirror_id)
        return mirror_config.get(key, getattr(self, key, default))
    
    def get_all_bot_tokens(self):
                                                                    
        tokens = [self.BOT_TOKEN] if self.BOT_TOKEN else []
        tokens.extend(self.MIRROR_BOT_TOKENS)
        return tokens
    
    def get_mirror_count(self):
                                                    
        return len(self.MIRROR_BOT_TOKENS)
    
    def is_mirror_enabled(self):
                                                    
        return len(self.MIRROR_BOT_TOKENS) > 0

                                
config = Config()

                                                     
def get_current_config(mirror_id="main"):
                                                    
    return config.get_mirror_config(mirror_id)
