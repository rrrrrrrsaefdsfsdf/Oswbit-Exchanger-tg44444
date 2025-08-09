import aiohttp
import logging
from typing import Optional
import ssl

logger = logging.getLogger(__name__)

class BitcoinAPI:
    
    @staticmethod
    async def get_btc_rate() -> Optional[float]:
        try:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=rub'
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data['bitcoin']['rub']
        except Exception as e:
            logger.error(f"Error fetching BTC rate: {e}")
        
        return 2800000.0

    @staticmethod
    def validate_btc_address(address: str) -> bool:
        if not address:
            return False
        
        if address.startswith(('1', '3', 'bc1')):
            if len(address) >= 26 and len(address) <= 62:
                return True
        
        return False

    @staticmethod
    def calculate_btc_amount(rub_amount: float, btc_rate: float) -> float:
        return rub_amount / btc_rate

    @staticmethod
    def calculate_fees(amount: float, processing_percentage: float, admin_percentage: float) -> tuple:
        processing_fee = amount * (processing_percentage / 100)
        total_with_processing = amount + processing_fee
        admin_fee = total_with_processing * (admin_percentage / 100)
        total_amount = total_with_processing + admin_fee
        
        return processing_fee, admin_fee, total_amount
