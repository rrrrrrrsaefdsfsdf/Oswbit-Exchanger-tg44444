import logging
import ssl
import aiohttp
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class PaymentAPIManager:
    def __init__(self, apis: List[Dict[str, Any]]):
        self.apis = apis
        self.nicepay_methods = {
            "sbp": "sbp_rub",
            "sberbank": "sberbank_rub",
            "tinkoff": "tinkoff_rub",
            "alfabank": "alfabank_rub",
            "raiffeisen": "raiffeisen_rub",
            "vtb": "vtb_rub",
            "rnkbbank": "rnkbbank_rub",
            "postbank": "postbank_rub",
            "yoomoney": "yoomoney_rub",
            "advcash": "advcash_rub",
            "payeer": "payeer_rub"
        }

    async def create_order(self, amount: int, payment_type: str, personal_id: str, is_sell_order: bool = False, wallet: Optional[str] = None) -> Dict[str, Any]:
        for api_config in self.apis:
            api = api_config['api']
            api_name = api_config['name']
            pay_type_mapping = api_config.get('pay_type_mapping', self.nicepay_methods if api_name == 'NicePay' else {})
            mapped_payment_type = pay_type_mapping.get(payment_type, payment_type)
            logger.info(f"Вызов create_order для {api_name} с параметрами: amount={amount}, pay_types={[mapped_payment_type] if api_name == 'PSPWare' else mapped_payment_type}, personal_id={personal_id}, wallet={'None' if api_name != 'Greengo' else wallet}")

            try:
                if is_sell_order and api_name != 'OnlyPays':
                    logger.debug(f"Пропуск {api_name} для продажи")
                    continue

                logger.info(f"Попытка создания заказа через {api_name} (тип платежа: {payment_type} -> {mapped_payment_type})")

                if api_name == 'Greengo':
                    wallet_address = wallet if wallet and wallet.startswith(('bc1', '1', '3', '0x')) else ''
                    response = await api.create_order(
                        payment_method=mapped_payment_type,
                        wallet=wallet_address,
                        from_amount=str(amount)
                    )
                elif api_name == 'PSPWare':
                    response = await api.create_order(
                        amount=amount,
                        pay_types=[mapped_payment_type],
                        personal_id=personal_id
                    )
                elif api_name == 'NicePay':
                    if mapped_payment_type not in self.nicepay_methods.values():
                        logger.error(f"Недопустимый метод оплаты для NicePay: {mapped_payment_type}")
                        return {"success": False, "error": f"Invalid payment method: {mapped_payment_type}", "api_name": api_name}
                    response = await api.create_payment(
                        merchant_order_id=personal_id,
                        amount=amount,
                        currency="RUB",
                        method=mapped_payment_type,
                        description=f"Payment for order {personal_id}"
                    )
                    logger.debug(f"NicePay raw response: {response}")
                else:
                    response = await api.create_order(
                        amount=amount,
                        payment_type=mapped_payment_type,
                        personal_id=personal_id
                    )

                if response.get('success'):
                    response['api_name'] = api_name
                    if api_name == 'Greengo':
                        response['data'] = {
                            'id': response.get('order_id', personal_id),
                            'requisite': response.get('requisite', ''),
                            'owner': response.get('owner', 'Неизвестно'),
                            'bank': response.get('bank', 'Неизвестно')
                        }
                    elif api_name == 'NicePay':
                        nicepay_data = response.get('data', {})
                        response['data'] = {
                            'id': nicepay_data.get('payment_id', personal_id),
                            'order_id': personal_id,
                            'payment_url': nicepay_data.get('payment_url', ''),
                            'amount': amount
                        }
                        logger.debug(f"Processed NicePay data: {response['data']}")
                    logger.info(f"Успешное создание заказа через {api_name}: {response['data']}")
                    return response
                else:
                    logger.warning(f"{api_name} не смог создать заказ: {response.get('error')}")
            except Exception as e:
                logger.error(f"Ошибка при создании заказа через {api_name}: {e}")
                response = {'success': False, 'error': str(e), 'api_name': api_name}

        logger.error("Все платежные API не сработали")
        return {'success': False, 'error': 'Все платежные API не сработали', 'api_name': 'None'}

    async def get_order_status(self, order_id: str, api_name: str, amount: int = None) -> Dict[str, Any]:
        api_config = next((api for api in self.apis if api['name'] == api_name), None)
        if not api_config:
            logger.error(f"API {api_name} не найдено")
            return {'success': False, 'error': f"API {api_name} не найдено"}

        try:
            if api_name == 'Greengo':
                response = await api_config['api'].get_order_status(order_id)
            elif api_name == 'NicePay':
                response = await api_config['api'].get_payment_status(order_id, amount)
            else:
                response = await api_config['api'].get_order_status(order_id)
            response['api_name'] = api_name
            logger.info(f"Статус заказа {order_id} от {api_name}: {response}")
            return response
        except Exception as e:
            logger.error(f"Ошибка проверки статуса через {api_name}: {e}")
            return {'success': False, 'error': str(e), 'api_name': api_name}

    async def cancel_order(self, order_id: str, api_name: str, amount: int = None) -> Dict[str, Any]:
        api_config = next((api for api in self.apis if api['name'] == api_name), None)
        if not api_config:
            logger.error(f"API {api_name} не найдено")
            return {'success': False, 'error': f"API {api_name} не найдено"}

        try:
            if api_name == 'Greengo':
                response = await api_config['api'].cancel_single_order(order_id)
            elif api_name == 'NicePay':
                response = await api_config['api'].cancel_payment(order_id, amount)
            else:
                response = await api_config['api'].cancel_order(order_id)
            response['api_name'] = api_name
            logger.info(f"Отмена заказа {order_id} через {api_name}: {response}")
            return response
        except Exception as e:
            logger.error(f"Ошибка отмены заказа через {api_name}: {e}")
            return {'success': False, 'error': str(e), 'api_name': api_name}

    async def health_check(self) -> Dict[str, Dict[str, Any]]:
        results = {}
        for api_config in self.apis:
            api = api_config['api']
            api_name = api_config['name']
            try:
                response = await api.health_check()
                results[api_name] = response
                logger.info(f"Health check for {api_name}: {response}")
            except Exception as e:
                results[api_name] = {'success': False, 'error': str(e)}
                logger.error(f"Health check error for {api_name}: {e}")
        return results
