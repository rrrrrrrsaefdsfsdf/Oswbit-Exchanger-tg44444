import logging
import aiohttp
from typing import List, Dict, Any, Optional
from config import config

logger = logging.getLogger(__name__)

class GreengoAPI:
    def __init__(self):
        self.api_secret = config.GREENGO_API_SECRET
        self.base_url = "https://api.greengo.cc/api/v2"
        self.headers = {
            "Api-Secret": self.api_secret,
            "Content-Type": "application/json"
        }

    async def _make_request(self, method: str, url: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        try:
            timeout = aiohttp.ClientTimeout(total=30)                    
            async with aiohttp.ClientSession(timeout=timeout) as session:
                if method.upper() == "GET":
                    async with session.get(url, headers=self.headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Greengo HTTP {response.status}: {error_text}")
                            return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
                        
                        result = await response.json()
                        logger.info(f"Greengo {method} response: {result}")
                        return result
                else:
                    async with session.post(url, json=data, headers=self.headers) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Greengo HTTP {response.status}: {error_text}")
                            return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
                        
                        result = await response.json()
                        logger.info(f"Greengo {method} response: {result}")
                        return result
                        
        except aiohttp.ClientError as e:
            logger.error(f"Greengo network error: {e}")
            return {"success": False, "error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Greengo unexpected error: {e}")
            return {"success": False, "error": str(e)}

                                                    
    async def create_order(self, payment_method: str, wallet: str, from_amount: str) -> Dict[str, Any]:
        url = f"{self.base_url}/order/create"
        data = {
            "payment_method": payment_method,
            "wallet": wallet,
            "from_amount": from_amount
        }
        
        logger.info(f"Создание Greengo ордера: {data}")
        response = await self._make_request("POST", url, data)
        
        if response.get("response") == "success" and "items" in response:
            if response["items"]:
                item = response["items"][0]
                return {
                    "success": True,
                    "order_id": item.get("order_id"),
                    "exchange_rate": item.get("exchange_rate"),
                    "amount_payable": item.get("amount_payable"),
                    "amount_receivable": item.get("amount_receivable"),
                    "wallet_payment": item.get("wallet_payment", ""),
                    "clients_wallet": item.get("clients_wallet"),
                    "order_status": item.get("order_status"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at"),
                    "requisite": item.get("wallet_payment", ""),
                    "owner": "Greengo Payment",
                    "bank": "Greengo Exchange"
                }
            else:
                return {"success": False, "error": "Пустой ответ от API"}
        elif "error" in response:
            return response
        else:
            return {"success": False, "error": f"Неожиданный формат ответа: {response}"}

    async def get_directions(self) -> Dict[str, Any]:
        url = f"{self.base_url}/directions"
        logger.info("Получение направлений Greengo")
        response = await self._make_request("GET", url)
        
        if isinstance(response, list):
            return {
                "success": True,
                "directions": response
            }
        elif "error" in response:
            return response
        else:
            return {"success": False, "error": f"Неожиданный формат ответа: {response}"}

    async def check_order(self, order_ids: List[str]) -> Dict[str, Any]:
        url = f"{self.base_url}/order/check"
        data = {"order_id": order_ids}
        
        logger.info(f"Проверка статуса Greengo ордеров: {order_ids}")
        response = await self._make_request("POST", url, data)
        
        if response.get("result") == "true" and "data" in response and "orders" in response["data"]:
            orders = response["data"]["orders"]
            if orders:
                order = orders[0]
                return {
                    "success": True,
                    "order_id": order.get("order_id"),
                    "exchange_rate": order.get("exchange_rate"),
                    "amount_payable": order.get("amount_payable"),
                    "amount_receivable": order.get("amount_receivable"),
                    "wallet_payment": order.get("wallet_payment", ""),
                    "clients_wallet": order.get("clients_wallet"),
                    "order_status": order.get("order_status"),
                    "created_at": order.get("created_at"),
                    "updated_at": order.get("updated_at"),
                    "all_orders": orders
                }
            else:
                return {"success": False, "error": "Ордера не найдены"}
        elif "error" in response:
            return response
        else:
            return {"success": False, "error": f"Неожиданный формат ответа: {response}"}

    async def cancel_order(self, order_ids: List[str]) -> Dict[str, Any]:
        url = f"{self.base_url}/order/cancel"
        data = {"order_id": order_ids}
        
        logger.info(f"Отмена Greengo ордеров: {order_ids}")
        response = await self._make_request("POST", url, data)
        
        if response.get("result") == "true" and "data" in response and "cancel" in response["data"]:
            canceled_orders = response["data"]["cancel"]
            return {
                "success": True,
                "canceled_orders": canceled_orders,
                "message": f"Отменено ордеров: {len(canceled_orders)}"
            }
        elif "error" in response:
            return response
        else:
            return {"success": False, "error": f"Неожиданный формат ответа: {response}"}

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        return await self.check_order([order_id])

    async def cancel_single_order(self, order_id: str) -> Dict[str, Any]:
        return await self.cancel_order([order_id])

    async def health_check(self) -> Dict[str, Any]:
        try:
            response = await self.get_directions()
            if response.get("success"):
                return {"success": True, "message": "Greengo API работает"}
            else:
                return {"success": False, "error": response.get("error", "Неизвестная ошибка")}
        except Exception as e:
            return {"success": False, "error": str(e)}
