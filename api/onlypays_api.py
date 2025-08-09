import logging
import aiohttp
import ssl
from config import config

logger = logging.getLogger(__name__)

class OnlyPaysAPI:
    def __init__(self, api_id: str, secret_key: str, payment_key: str = None):
        self.api_id = api_id
        self.secret_key = secret_key
        self.payment_key = payment_key
        self.base_url = "https://onlypays.net"

    async def create_order(self, amount: int, payment_type: str, personal_id: str = None, trans: bool = False):
        url = f"{self.base_url}/get_requisite"
        data = {
            "api_id": self.api_id,
            "secret_key": self.secret_key,
            "amount_rub": amount,
            "payment_type": payment_type
        }
        if personal_id:
            data["personal_id"] = personal_id
        if trans:
            data["trans"] = True

        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    logger.info(f"OnlyPays create_order response (sum {amount}): {result}")
                    return result
        except Exception as e:
            logger.error(f"OnlyPays create_order error: {e}")
            return {"success": False, "error": str(e)}

    async def get_order_status(self, order_id: str):
        url = f"{self.base_url}/get_status"
        data = {
            "api_id": self.api_id,
            "secret_key": self.secret_key,
            "id": order_id
        }
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    logger.info(f"OnlyPays get_status response: {result}")
                    return result
        except Exception as e:
            logger.error(f"OnlyPays get_status error: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_order(self, order_id: str):
        url = f"{self.base_url}/cancel_order"
        data = {
            "api_id": self.api_id,
            "secret_key": self.secret_key,
            "id": order_id
        }
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    logger.info(f"OnlyPays cancel_order response: {result}")
                    return result
        except Exception as e:
            logger.error(f"OnlyPays cancel_order error: {e}")
            return {"success": False, "error": str(e)}

    async def get_balance(self):
        if not self.payment_key:
            return {"success": False, "error": "Payment key not provided"}
        url = f"{self.base_url}/get_balance"
        data = {
            "api_id": self.api_id,
            "payment_key": self.payment_key
        }
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    logger.info(f"OnlyPays get_balance response: {result}")
                    return result
        except Exception as e:
            logger.error(f"OnlyPays get_balance error: {e}")
            return {"success": False, "error": str(e)}

    async def create_payout(self, payout_type: str, amount: int, requisite: str, bank: str, personal_id: str = None):
        if not self.payment_key:
            return {"success": False, "error": "Payment key not provided"}
        url = f"{self.base_url}/create_payout"
        data = {
            "api_id": self.api_id,
            "payment_key": self.payment_key,
            "type": payout_type,
            "amount": amount,
            "requisite": requisite,
            "bank": bank
        }
        if personal_id:
            data["personal_id"] = personal_id

        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    logger.info(f"OnlyPays create_payout response: {result}")
                    return result
        except Exception as e:
            logger.error(f"OnlyPays create_payout error: {e}")
            return {"success": False, "error": str(e)}

    async def get_payout_status(self, payout_id: str):
        if not self.payment_key:
            return {"success": False, "error": "Payment key not provided"}
        url = f"{self.base_url}/payout_status"
        data = {
            "api_id": self.api_id,
            "payment_key": self.payment_key,
            "id": payout_id
        }
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    logger.info(f"OnlyPays payout_status response: {result}")
                    return result
        except Exception as e:
            logger.error(f"OnlyPays payout_status error: {e}")
            return {"success": False, "error": str(e)}

onlypays_api = OnlyPaysAPI(
    api_id=config.ONLYPAYS_API_ID,
    secret_key=config.ONLYPAYS_SECRET_KEY,
    payment_key=getattr(config, 'ONLYPAYS_PAYMENT_KEY', None)
)
