import asyncio
import logging
import aiohttp
from config import config

logger = logging.getLogger(__name__)

class NicePayAPI:
    def __init__(self):
        self.merchant_id = config.NICEPAY_MERCHANT_KEY
        self.secret = config.NICEPAY_MERCHANT_TOKEN_KEY
        self.base_url = "https://nicepay.io/public/api/payment"




    async def _make_request(self, url: str, params: dict, retries: int = 3, delay: int = 5) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        for attempt in range(1, retries + 1):
            logger.debug(f"Attempt {attempt} to {url} with params: {params}")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=params, headers=headers) as resp:
                        logger.debug(f"Response status: {resp.status}")
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(f"HTTP {resp.status}: {error_text} for {url}")
                            return {"success": False, "error": f"HTTP {resp.status}: {error_text}"}
                        result = await resp.json()
                        logger.info(f"NicePay response: {result}")
                        if result.get("status") == "success":
                            return {
                                "success": True,
                                "data": {
                                    "id": result["data"]["payment_id"],
                                    "payment_url": result["data"]["link"],
                                    "amount": result["data"]["amount"],
                                    "currency": result["data"]["currency"],
                                    "expired": result["data"]["expired"]
                                }
                            }
                        logger.warning(f"API error: {result.get('data', {}).get('message', 'Unknown error')}")
                        return {"success": False, "error": result["data"].get("message", "Unknown error")}
            except aiohttp.ClientConnectorError as e:
                logger.error(f"Network error (attempt {attempt}): {e}, host={url}")
                if attempt < retries:
                    await asyncio.sleep(delay)
                    continue
                return {"success": False, "error": f"Network error after {retries} attempts: {str(e)}"}
            except Exception as e:
                logger.error(f"Unexpected error: {e}, host={url}")
                return {"success": False, "error": str(e)}
        return {"success": False, "error": f"Failed after {retries} attempts"}

    async def create_payment(self, merchant_order_id: str, amount: int, currency: str = "RUB",
                            method: str = "sbp_rub", description: str = "") -> dict:
        url = self.base_url
        params = {
            "merchant_id": self.merchant_id,
            "secret": self.secret,
            "order_id": merchant_order_id,
            "customer": f"customer_{merchant_order_id}@example.com",
            "amount": int(amount * 100),
            "currency": currency,
            "description": description or f"Payment for order {merchant_order_id}",
            "method": method
        }
        logger.debug(f"Creating payment with params: {params}")
        return await self._make_request(url, params)

