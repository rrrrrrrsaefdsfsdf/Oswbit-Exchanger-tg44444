import aiohttp
import logging
from config import config

logger = logging.getLogger(__name__)

class PSPWareAPI:
    def __init__(self):
        self.base_url = "https://api.pspware.space/merchant/v2"
        self.api_key = config.PSPWARE_API_KEY
        self.merchant_id = config.PSPWARE_MERCHANT_ID
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

    async def create_order(self, amount: float, pay_types: list, personal_id: str, order_type: str = "PAY-IN", geos: list = None) -> dict:
        url = f"{self.base_url}/orders"
        payload = {
            "sum": amount,
            "currency": "RUB",
            "order_type": order_type,
            "pay_types": pay_types,
            "geos": geos or ["RU"],
            "merchant_id": self.merchant_id,
            "order_id": personal_id,
            "description": f"Exchange order {personal_id}"
        }
        if order_type == "PAY-OUT":
            payload.pop("pay_types", None)
            payload.pop("geos", None)
            payload["bank"] = "any-bank"
        logger.info(f"[PSPWareAPI] POST {url} Headers: {self.headers} Payload: {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    text_resp = await response.text()
                    logger.info(f"[PSPWareAPI] Response status {response.status} Body: {text_resp}")
                    response_data = await response.json(content_type=None)
                    if response.status == 200 and response_data.get("status") == "success":
                        return {
                            "success": True,
                            "data": {
                                "id": response_data.get("id"),
                                "sum": response_data.get("sum"),
                                "requisite": response_data.get("card", ""),
                                "owner": response_data.get("recipient", ""),
                                "bank": response_data.get("bankName", ""),
                                "pay_type": response_data.get("pay_type", ""),
                                "payment_url": response_data.get("payment_url", None),
                                "bik": response_data.get("bik", None),
                                "geo": response_data.get("geo", ""),
                                "status": response_data.get("status", "")
                            }
                        }
                    else:
                        error_message = "Неизвестная ошибка"
                        if response_data.get("detail"):
                            if isinstance(response_data["detail"], list):
                                errors = []
                                for error in response_data["detail"]:
                                    field = ".".join(str(loc) for loc in error.get("loc", []))
                                    msg = error.get("msg", "Недопустимое значение")
                                    errors.append(f"{field}: {msg}")
                                error_message = "; ".join(errors)
                            else:
                                error_message = str(response_data["detail"])
                        elif response_data.get("message"):
                            error_message = response_data["message"]
                        logger.error(f"[PSPWareAPI] Ошибка создания заказа: {response_data}")
                        return {
                            "success": False,
                            "error": error_message,
                            "status_code": response.status,
                            "raw_response": response_data
                        }
        except Exception as e:
            logger.error(f"[PSPWareAPI] Исключение при создании заказа: {e}")
            return {"success": False, "error": str(e)}

    async def create_withdrawal(self, address: str, amount: float) -> dict:
        url = f"{self.base_url}/withdrawal"
        payload = {"address": address, "sum": amount}
        logger.info(f"[PSPWareAPI] POST {url} Headers: {self.headers} Payload: {payload}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    text_resp = await response.text()
                    logger.info(f"[PSPWareAPI] Response status {response.status} Body: {text_resp}")
                    response_data = await response.json(content_type=None)
                    if response.status == 200:
                        return {
                            "success": True,
                            "data": {
                                "id": response_data.get("id"),
                                "address": response_data.get("address"),
                                "sum": response_data.get("sum"),
                                "status": response_data.get("status"),
                                "merchant_id": response_data.get("merchantId"),
                                "created_at": response_data.get("createdAt"),
                                "updated_at": response_data.get("updatedAt")
                            }
                        }
                    else:
                        logger.error(f"[PSPWareAPI] Ошибка создания заявки на вывод: {response_data}")
                        return {"success": False, "error": response_data.get("message", "Неизвестная ошибка"), "status_code": response.status}
        except Exception as e:
            logger.error(f"[PSPWareAPI] Исключение при создании заявки на вывод: {e}")
            return {"success": False, "error": str(e)}

    async def get_order_status(self, order_id: str) -> dict:
        url = f"{self.base_url}/orders/{order_id}"
        logger.info(f"[PSPWareAPI] GET {url} Headers: {self.headers}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    text_resp = await response.text()
                    logger.info(f"[PSPWareAPI] Response status {response.status} Body: {text_resp}")
                    response_data = await response.json(content_type=None)
                    if response.status == 200:
                        return {
                            "success": True,
                            "data": {
                                "id": response_data.get("id"),
                                "sum": response_data.get("sum"),
                                "status": response_data.get("status"),
                                "requisite": response_data.get("card", ""),
                                "owner": response_data.get("recipient", ""),
                                "bank": response_data.get("bankName", ""),
                                "pay_type": response_data.get("pay_type", ""),
                                "payment_url": response_data.get("payment_url", None),
                                "bik": response_data.get("bik", None),
                                "geo": response_data.get("geo", ""),
                                "is_sbp": response_data.get("is_sbp", False)
                            }
                        }
                    else:
                        logger.error(f"[PSPWareAPI] Ошибка получения статуса заказа: {response_data}")
                        return {"success": False, "error": response_data.get("message", "Неизвестная ошибка"), "status_code": response.status}
        except Exception as e:
            logger.error(f"[PSPWareAPI] Исключение при получении статуса заказа: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_order(self, order_id: str) -> dict:
        url = f"{self.base_url}/orders/{order_id}/cancel"
        logger.info(f"[PSPWareAPI] POST {url} Headers: {self.headers}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers) as response:
                    text_resp = await response.text()
                    logger.info(f"[PSPWareAPI] Response status {response.status} Body: {text_resp}")
                    response_data = await response.json(content_type=None)
                    if response.status == 200 and response_data.get("status") == "success":
                        return {"success": True, "data": {"id": order_id, "status": "canceled"}}
                    else:
                        logger.error(f"[PSPWareAPI] Ошибка отмены заказа: {response_data}")
                        return {"success": False, "error": response_data.get("message", "Неизвестная ошибка"), "status_code": response.status}
        except Exception as e:
            logger.error(f"[PSPWareAPI] Исключение при отмене заказа: {e}")
            return {"success": False, "error": str(e)}

    async def get_merchant_info(self) -> dict:
        url = f"{self.base_url}/merchant/me"
        logger.info(f"[PSPWareAPI] GET {url} Headers: {self.headers}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    text_resp = await response.text()
                    logger.info(f"[PSPWareAPI] Response status {response.status} Body: {text_resp}")
                    response_data = await response.json(content_type=None)
                    if response.status == 200:
                        return {
                            "success": True,
                            "data": {
                                "id": response_data.get("id"),
                                "name": response_data.get("name"),
                                "balance": response_data.get("balance"),
                                "hold_balance": response_data.get("hold_balance"),
                                "percents": response_data.get("percents", [])
                            }
                        }
                    else:
                        logger.error(f"[PSPWareAPI] Ошибка получения информации о мерчанте: {response_data}")
                        return {"success": False, "error": response_data.get("message", "Неизвестная ошибка"), "status_code": response.status}
        except Exception as e:
            logger.error(f"[PSPWareAPI] Исключение при получении информации о мерчанте: {e}")
            return {"success": False, "error": str(e)}

    async def health_check(self) -> dict:
        url = f"{self.base_url}/health"
        logger.info(f"[PSPWareAPI] GET {url} Headers: {self.headers}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=self.headers) as response:
                    text_resp = await response.text()
                    logger.info(f"[PSPWareAPI] Response status {response.status} Body: {text_resp}")
                    response_data = await response.json(content_type=None)
                    if response.status == 200 and response_data.get("status") == "ok":
                        return {"success": True, "data": {"status": "ok"}}
                    else:
                        logger.error(f"[PSPWareAPI] Проверка состояния сервиса не удалась: {response_data}")
                        return {"success": False, "error": response_data.get("message", "Сервис недоступен"), "status_code": response.status}
        except Exception as e:
            logger.error(f"[PSPWareAPI] Исключение при проверке состояния сервиса: {e}")
            return {"success": False, "error": str(e)}