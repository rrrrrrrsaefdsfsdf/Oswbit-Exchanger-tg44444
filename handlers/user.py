                  
import logging
import asyncio
import os
from datetime import datetime
import traceback
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import Database
from keyboards.reply import ReplyKeyboards
from keyboards.inline import InlineKeyboards
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.bitcoin import BitcoinAPI
from utils.captcha import CaptchaGenerator
from config import config
from handlers.operator import (
    notify_operators_new_order,
    notify_operators_paid_order,
    notify_operators_error_order,
    notify_client_payment_received,
    notify_client_order_cancelled
)
from api.onlypays_api import OnlyPaysAPI
from api.pspware_api import PSPWareAPI
from api.greengo_api import GreengoAPI
from api.nicepay_api import NicePayAPI
from api.api_manager import PaymentAPIManager

logger = logging.getLogger(__name__)
router = Router()
logger.info("User router loaded")

onlypays_api = OnlyPaysAPI(
    api_id=os.getenv('ONLYPAYS_API_ID'),
    secret_key=os.getenv('ONLYPAYS_SECRET_KEY'),
    payment_key=os.getenv('ONLYPAYS_PAYMENT_KEY')
)
pspware_api = PSPWareAPI()
greengo_api = GreengoAPI()
nicepay_api = NicePayAPI()

                                                     
payment_api_manager = PaymentAPIManager([
    {"api": onlypays_api, "name": "OnlyPays"},
    {"api": pspware_api, "name": "PSPWare", "pay_type_mapping": {"card": "c2c", "sbp": "sbp"}},
    {"api": greengo_api, "name": "Greengo", "pay_type_mapping": {"card": "card", "sbp": "sbp"}},
    {"api": nicepay_api, "name": "NicePay", "pay_type_mapping": {"card": "sberbank_rub", "sbp": "sbp_rub"}}
])



                                                                     
class ExchangeStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_btc_address = State()
    waiting_for_captcha = State()
    waiting_for_contact = State()
    waiting_for_address = State()
    waiting_for_card_details = State()
    waiting_for_note = State()

db = Database(config.DATABASE_URL)






async def show_main_menu(message_or_callback, is_callback=False):


        

    default_welcome = (
        f"<b>🥷 Добро пожаловать в {config.EXCHANGE_NAME}, ниндзя!</b>\n"
        f"\nУ нас ты можешь купить Bitcoin по лучшему курсу.\n\n"
        f"Быстро. Дешево. Анонимно.\n\n"
        f"Оператор: {config.SUPPORT_MANAGER}\n"
        f"Канал: {config.NEWS_CHANNEL}\n\n"
        f"Выберите действие в меню:"
    )

    welcome_msg = await db.get_setting("welcome_message", default_welcome)
    if is_callback:
        await message_or_callback.bot.send_message(
            message_or_callback.message.chat.id,
            welcome_msg,
            reply_markup=ReplyKeyboards.main_menu()
        )
    else:
        await message_or_callback.answer(welcome_msg, reply_markup=ReplyKeyboards.main_menu())





@router.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    if not user:
        captcha_enabled = await db.get_setting("captcha_enabled", config.CAPTCHA_ENABLED)
        if captcha_enabled:
            image_buffer, answer = CaptchaGenerator.generate_image_captcha()
            await db.create_captcha_session(message.from_user.id, answer.upper())
            captcha_photo = BufferedInputFile(
                image_buffer.read(),
                filename="captcha.png"
            )
            await message.answer_photo(
                photo=captcha_photo,
                caption="🤖 Добро пожаловать! Введите код с картинки:",
                reply_markup=ReplyKeyboards.back_to_main()
            )
            await state.set_state(ExchangeStates.waiting_for_captcha)
            return
        else:
            await db.add_user(
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
    await show_main_menu(message)

@router.message(ExchangeStates.waiting_for_captcha)
async def captcha_handler(message: Message, state: FSMContext):
    if message.text == "◶️ Главное меню":
        await state.clear()
        await message.answer("Для использования бота пройдите проверку через /start")
        return
    session = await db.get_captcha_session(message.from_user.id)
    if not session:
        await message.answer("Ошибка сессии. Попробуйте /start")
        return
    user_answer = message.text.upper().strip()
    correct_answer = session['answer'].upper().strip()
    if user_answer == correct_answer:
        await db.delete_captcha_session(message.from_user.id)
        await db.add_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name
        )
        data = await state.get_data()
        referral_user_id = data.get('referral_user_id')
        if referral_user_id and referral_user_id != message.from_user.id:
            await db.update_user(message.from_user.id, referred_by=referral_user_id)
            await db.update_referral_count(referral_user_id)
            try:
                await message.bot.send_message(
                    referral_user_id,
                    f"🎉 По вашей ссылке зарегистрировался новый пользователь!\n"
                    f"👤 {message.from_user.first_name}\n"
                    f"💰 Вам начислен бонус за приглашение!"
                )
            except:
                pass
        await message.answer("✅ Верно! Регистрация завершена.")
        await show_main_menu(message)
        await state.clear()
    else:
        attempts = session['attempts'] + 1
        if attempts >= 3:
            await db.delete_captcha_session(message.from_user.id)
            await message.answer("❌ Превышено количество попыток. Попробуйте /start снова.")
            await state.clear()
        else:
            await db.execute_query(
                'UPDATE captcha_sessions SET attempts = ? WHERE user_id = ?',
                (attempts, message.from_user.id)
            )
            try:
                image_buffer, answer = CaptchaGenerator.generate_simple_image_captcha()
                await db.execute_query(
                    'UPDATE captcha_sessions SET answer = ? WHERE user_id = ?',
                    (answer.upper(), message.from_user.id)
                )
                captcha_photo = BufferedInputFile(
                    image_buffer.read(),
                    filename="captcha.png"
                )
                await message.answer_photo(
                    photo=captcha_photo,
                    caption=f"❌ Неверно. Попыток осталось: {3-attempts}\nВведите код с новой картинки:"
                )
            except:
                await message.answer(f"❌ Неверно. Попыток осталось: {3-attempts}")

@router.message(F.text == "Купить")
async def buy_handler(message: Message, state: FSMContext):
    await state.clear()
    text = "Выберите что хотите купить."
    await message.answer(
        text,
        reply_markup=InlineKeyboards.buy_crypto_selection()
    )


@router.callback_query(F.data.startswith("buy_"))
async def buy_crypto_selected(callback: CallbackQuery, state: FSMContext):
    if callback.data == "buy_main_menu":
        await show_main_menu(callback, is_callback=True)
        return

    crypto = callback.data.replace("buy_", "").upper()
    if crypto == "BTC":
        await state.update_data(
            operation="buy",
            crypto=crypto,
            direction="rub_to_crypto"
        )
        btc_rate = await BitcoinAPI.get_btc_rate()
        text = (
            f"💰 <b>Покупка Bitcoin\n\n"
            f"📊 Текущий курс: {btc_rate:,.0f} ₽\n"
            f"\n💱Обмен: от {config.MIN_AMOUNT:,.0f} RUB до {config.MAX_AMOUNT:,.0f} RUB</b>\n\n"
            f"Введите сумму в рублях или BTC (в BTC вводить через точку, например 0.001):"
        )
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboards.amount_input_keyboard(crypto.lower(), "rub_to_crypto"),
            parse_mode="HTML"
        )
        await state.set_state(ExchangeStates.waiting_for_amount)







@router.callback_query(F.data.startswith("amount_"))
async def amount_selected(callback: CallbackQuery, state: FSMContext):
    if "back" in callback.data:
        data = await state.get_data()
        operation = data.get("operation", "buy")
        if operation == "buy":
            await buy_handler(callback.message, state)
        return
    if "main_menu" in callback.data:
        await show_main_menu(callback, is_callback=True)
        return
    parts = callback.data.split("_")
    crypto = parts[1].upper()
    direction = "_".join(parts[2:-1])
    amount = float(parts[-1])
    await process_amount_and_show_calculation(callback, state, crypto, direction, amount)

@router.callback_query(F.data == "back_to_buy_selection")
async def back_to_buy_selection(callback: CallbackQuery, state: FSMContext):
    text = "Выберите что хотите купить."
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboards.buy_crypto_selection()
    )


@router.message(ExchangeStates.waiting_for_amount)
async def manual_amount_input(message: Message, state: FSMContext):
    if message.text == "◶️ Главное меню":
        await state.clear()
        await show_main_menu(message)
        return

    data = await state.get_data()
    try:
        amount = float(message.text.replace(' ', '').replace(',', '.'))
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return

        crypto = data.get("crypto")
        direction = data.get("direction")
        if not crypto or not direction:
            await message.answer("❌ Ошибка: данные о криптовалюте или направлении отсутствуют.")
            return

        if amount < 1:
                                                        
            await process_amount_and_show_calculation_for_message(
                message, state, crypto, direction, amount, is_crypto=True
            )
        elif 1 <= amount <= 2000:
            await message.answer("⚠️ Минимальная сумма для обмена 2.000 RUB")
            return
        else:
                                                           
            if not (config.MIN_AMOUNT <= amount <= config.MAX_AMOUNT):
                await message.answer(
                    f"❌ Сумма должна быть от {config.MIN_AMOUNT:,} ₽ до {config.MAX_AMOUNT:,} ₽. Пожалуйста, введите корректную сумму."
                )
                return
            await process_amount_and_show_calculation_for_message(
                message, state, crypto, direction, amount
            )

    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing amount: {message.text}, error: {e}")
        await message.answer("❌ Введите корректное число (например, 5000 или 5000.50)")






async def process_amount_and_show_calculation(callback: CallbackQuery, state: FSMContext,
                                            crypto: str, direction: str, amount: float):
    btc_rate = await BitcoinAPI.get_btc_rate()
    if direction == "rub_to_crypto":
        rub_amount = amount
        crypto_amount = BitcoinAPI.calculate_btc_amount(rub_amount, btc_rate)
    else:
        crypto_amount = amount
        rub_amount = crypto_amount * btc_rate
    COMMISSION_PERCENT = await db.get_commission_percentage()
    total_amount = rub_amount / (1 - COMMISSION_PERCENT / 100)
    await state.update_data(
        crypto=crypto,
        direction=direction,
        rub_amount=rub_amount,
        crypto_amount=crypto_amount,
        rate=btc_rate,
        total_amount=total_amount,
        payment_type='card'
    )
    operation_text = "Покупка" if direction == "rub_to_crypto" else "Продажа"
    text = (
        f"📊 <b>{operation_text} Bitcoin</b>\n\n"
        f"💱 Курс: {btc_rate:,.0f} ₽\n"
        f"💰 Сумма: {rub_amount:,.0f} ₽\n"
        f"₿ Получите: {crypto_amount:.8f} BTC\n\n"
        f"💸 <b>Итого: {total_amount:,.0f} ₽</b>\n\n"
        f"Введите ваш Bitcoin адрес:"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state(ExchangeStates.waiting_for_address)

async def process_amount_and_show_calculation_for_message(message: Message, state: FSMContext,
                                                        crypto: str, direction: str, amount: float, is_crypto: bool = False):
    btc_rate = await BitcoinAPI.get_btc_rate()
    if direction == "rub_to_crypto":
        if is_crypto:
            rub_amount = await BitcoinAPI.get_btc_to_rub(amount)
        else:
            rub_amount = amount
        crypto_amount = BitcoinAPI.calculate_btc_amount(rub_amount, btc_rate)
    else:
        crypto_amount = amount
        rub_amount = crypto_amount * btc_rate
    COMMISSION_PERCENT = await db.get_commission_percentage()
    total_amount = rub_amount / (1 - COMMISSION_PERCENT / 100)
    await state.update_data(
        crypto=crypto,
        direction=direction,
        rub_amount=rub_amount,
        crypto_amount=crypto_amount,
        rate=btc_rate,
        total_amount=total_amount,
        payment_type='card'
    )
    operation_text = "Покупка" if direction == "rub_to_crypto" else "Продажа"
    text = (
        f"📊 <b>{operation_text} Bitcoin</b>\n\n"
        f"💱 Курс: {btc_rate:,.0f} ₽\n"
        f"💰 Сумма: {rub_amount:,.0f} ₽\n"
        f"₿ Получите: {crypto_amount:.8f} BTC\n\n"
        f"💸 <b>Итого: {total_amount:,.0f} ₽</b>\n\n"
        f"Введите ваш Bitcoin адрес:"
    )
    await message.answer(text, parse_mode="HTML")
    await state.set_state(ExchangeStates.waiting_for_address)






@router.callback_query(F.data.startswith("payment_"))
async def payment_method_selected(callback: CallbackQuery, state: FSMContext):
    if "back" in callback.data:
        data = await state.get_data()
        crypto = data.get("crypto")
        direction = data.get("direction")
        await callback.message.edit_text(
            f"Введите {'сумму в рублях' if direction == 'rub_to_crypto' else 'количество BTC'}:",
            reply_markup=InlineKeyboards.amount_input_keyboard(crypto.lower(), direction)
        )
        return
    if "main_menu" in callback.data:
        await show_main_menu(callback, is_callback=True)
        return
    parts = callback.data.split("_")
    crypto = parts[1].upper()
    direction = "_".join(parts[2:-2])
    amount = parts[-2]
    payment_type = parts[-1]
    await state.update_data(payment_type=payment_type)
    if direction == "rub_to_crypto":
        text = (
            f"₿ <b>Введите ваш Bitcoin адрес</b>\n\n"
            f"Убедитесь, что адрес указан правильно!\n"
            f"Bitcoin будет отправлен именно на этот адрес."
        )
    else:
        text = (
            f"💳 <b>Введите реквизиты для получения</b>\n\n"
            f"{'Номер карты' if payment_type == 'card' else 'Номер телефона для СБП'}:"
        )
    await callback.message.edit_text(text, parse_mode="HTML")
    await state.set_state(ExchangeStates.waiting_for_address)









@router.message(ExchangeStates.waiting_for_btc_address)
async def btc_address_handler(message: Message, state: FSMContext):
    if message.text == "◶️ Главное меню":
        await state.clear()
        await show_main_menu(message)
        return
    btc_address = message.text.strip()
    if not BitcoinAPI.validate_btc_address(btc_address):
        await message.answer("❌ Некорректный Bitcoin адрес. Попробуйте еще раз.")
        return
    data = await state.get_data()
    btc_rate = await BitcoinAPI.get_btc_rate()
    if not btc_rate:
        await message.answer("❌ Ошибка получения курса. Попробуйте позже.")
        return
    rub_amount = data['rub_amount']
    btc_amount = BitcoinAPI.calculate_btc_amount(rub_amount, btc_rate)
    COMMISSION_PERCENT = await db.get_commission_percentage()
    total_amount = rub_amount / (1 - COMMISSION_PERCENT / 100)
    text = (
        f"📊 <b>Предварительный расчет:</b>\n\n"
        f"💱 Курс BTC: {btc_rate:,.0f} ₽\n"
        f"💰 Сумма к обмену: {rub_amount:,.0f} ₽\n"
        f"₿ Получите Bitcoin: {btc_amount:.8f} BTC\n\n"
        f"💸 <b>К оплате: {total_amount:,.0f} ₽</b>\n\n"
        f"₿ Bitcoin адрес:\n<code>{btc_address}</code>\n\n"
        f"Выберите способ оплаты:"
    )
    await state.update_data(
        btc_address=btc_address,
        rub_amount=rub_amount,
        btc_amount=btc_amount,
        btc_rate=btc_rate,
        total_amount=total_amount
    )
    await message.answer(text, reply_markup=ReplyKeyboards.payment_methods(), parse_mode="HTML")




@router.message(ExchangeStates.waiting_for_address)
async def address_input_handler(message: Message, state: FSMContext):
    address = message.text.strip()
    data = await state.get_data()
    direction = data.get("direction")
    crypto = data.get("crypto")
    if direction == "rub_to_crypto":
        if not BitcoinAPI.validate_btc_address(address):
            await message.answer("❌ Некорректный Bitcoin адрес. Попробуйте еще раз.")
            return
    else:
        if len(address) < 10:
            await message.answer("❌ Некорректные реквизиты. Попробуйте еще раз.")
            return
    await state.update_data(address=address)
    order_id = await create_exchange_order(message.from_user.id, state)
    await show_order_confirmation(message, state, order_id)






                                                                          
                                   
                                       
                          
                                        
                                           
                                      
                            
                                            
                                           
       
                     


async def create_exchange_order(user_id: int, state: FSMContext) -> int:
    
    data = await state.get_data()
    
    order_id = await db.create_order(
        user_id=user_id,
        amount_rub=data["rub_amount"],
        amount_btc=data["crypto_amount"],
        btc_address=data["address"],
        rate=data["rate"],
        total_amount=data["total_amount"],
        payment_type=data["payment_type"]
    )
    
                                               
    await db.add_turnover_record(
        order_id=order_id,
        user_id=user_id,
        amount=data["total_amount"],
        status="created"
    )
    
    return order_id







async def show_order_confirmation(message: Message, state: FSMContext, order_id: int):
    data = await state.get_data()
    order = await db.get_order(order_id)
    display_id = order.get('personal_id', order_id) if order else order_id
    operation_text = "Покупка" if data["direction"] == "rub_to_crypto" else "Продажа"
    text = (
        f"✅ <b>Заявка создана!</b>\n\n"
        f"📋 <b>{operation_text} Bitcoin</b>\n"
        f"💰 Сумма: {data['rub_amount']:,.0f} ₽\n"
        f"₿ Количество: {data['crypto_amount']:.8f} BTC\n"
        f"💸 К {'оплате' if data['direction'] == 'rub_to_crypto' else 'получению'}: {data['total_amount']:,.0f} ₽\n\n"
        f"📝 Адрес/Реквизиты:\n<code>{data['address']}</code>\n\n"
        f"Подтвердите создание заявки:"
    )
    
    await message.answer(
        text,
        reply_markup=InlineKeyboards.order_confirmation(order_id),
        parse_mode="HTML"
    )
                         










async def request_requisites_with_retries(order_id: int, user_id: int, payment_type: str, bot, max_attempts=3, delay_sec=60):
    order = await db.get_order(order_id)
    if not order:
        logger.error(f"Order not found: {order_id}")
        return False
    
    is_sell_order = not order.get('btc_address')
    total_amount = int(await db.get_order_total_amount(order_id))
    
    for attempt in range(1, max_attempts + 1):
        try:
                                                    
            for api_config in payment_api_manager.apis:
                api_name = api_config['name']
                if api_name == 'Greengo':
                    min_amount = api_config.get('min_amount', 500)
                    if total_amount < min_amount:
                        logger.warning(f"Order {order_id} amount {total_amount} is below Greengo minimum {min_amount}")
                        await bot.send_message(
                            user_id,
                            f"❌ Минимальная сумма для оплаты {min_amount} ₽. Ваша сумма: {total_amount} ₽. Пожалуйста, увеличьте сумму.",
                            reply_markup=ReplyKeyboards.main_menu()
                        )
                        await db.update_order(order_id, status='error_requisites')
                        return False
            
                                                                  
            wallet = order.get('btc_address') if not is_sell_order else None
            
            api_response = await payment_api_manager.create_order(
                amount=total_amount,
                payment_type=payment_type,
                personal_id=str(order_id),
                is_sell_order=is_sell_order,
                wallet=wallet                                             
            )
            
            if api_response.get('success'):
                payment_data = api_response['data']
                api_name = api_response.get('api_name')
                
                                                           
                if api_name == 'NicePay':
                    logger.debug(f"Payment data for NicePay: {payment_data}")
                    requisites_text = (
                        f"🔗 <b>Ссылка для оплаты:</b> {payment_data['payment_url']}\n"
                        f"💳 Тип платежа: {'Карта' if payment_type == 'card' else 'СБП'}\n"
                        f"📋 ID транзакции: {payment_data['id']}"
                    )
                    
                else:
                    requisites_text = (
                        f"{'💳 Карта' if payment_type == 'card' else '📱 Телефон'}: {payment_data['requisite']}\n"
                        f"👤 Получатель: {payment_data['owner']}\n"
                        f"🏛 Банк: {payment_data['bank']}"
                    )
                
                update_data = {
                    'requisites': requisites_text,
                    'status': 'waiting',
                    'personal_id': payment_data['id']
                }
                if api_name == 'OnlyPays':
                    update_data['onlypays_id'] = payment_data['id']
                elif api_name == 'PSPWare':
                    update_data['pspware_id'] = payment_data['id']
                elif api_name == 'Greengo':
                    update_data['greengo_id'] = payment_data['id']
                elif api_name == 'NicePay':
                    update_data['nicepay_id'] = payment_data['id']
                
                await db.update_order(order_id, **update_data)
                await bot.send_message(
                    user_id,
                    f"💳 <b>Ваша заявка #{payment_data['id']} подтверждена!</b>\n\n"
                    f"💰 К оплате: <b>{total_amount:,.0f} ₽</b>\n\n"
                    f"📋 <b>Реквизиты для оплаты:</b>\n{requisites_text}\n\n"
                    f"⚠️ <b>Важно:</b>\n"
                    f"• Переведите точную сумму\n"
                    f"• После оплаты ожидайте подтверждения\n"
                    f"• Bitcoin будет отправлен автоматически\n\n"
                    f"⏰ Заявка действительна 30 минут",
                    parse_mode="HTML",
                    reply_markup=ReplyKeyboards.order_menu(is_nicepay=(api_name == 'NicePay'))
                )
                return True
            else:
                logger.warning(f"{api_response.get('api_name')} order creation failed on attempt {attempt} for order {order_id}: {api_response.get('error')}")
                if api_response.get('api_name') == 'Greengo' and "Нет свободных счетов" in str(api_response.get('error', '')):
                    await bot.send_message(
                        user_id,
                        "❌ Временно нет доступных счетов для оплаты через Greengo. Пожалуйста, попробуйте позже или выберите другой способ оплаты.",
                        reply_markup=ReplyKeyboards.main_menu()
                    )
                    await db.update_order(order_id, status='error_requisites')
                    return False
                elif api_response.get('api_name') == 'NicePay' and 'getaddrinfo failed' in str(api_response.get('error', '')):
                    await bot.send_message(
                        user_id,
                        "❌ Временная ошибка сети при подключении к NicePay. Пожалуйста, попробуйте позже.",
                        reply_markup=ReplyKeyboards.main_menu()
                    )
                    await db.update_order(order_id, status='error_requisites')
                    return False
        
        except Exception as e:
            logger.error(f"Attempt {attempt} failed for order {order_id}: {e}")
        
        if attempt < max_attempts:
            await asyncio.sleep(delay_sec)

    await db.update_order(order_id, status='error_requisites')
    error_msg = "❌ Извините, реквизиты для вашей заявки временно недоступны.\nПожалуйста, попробуйте создать заявку позже."
    if is_sell_order:
        error_msg = "❌ Извините, сервис продажи временно недоступен.\nПожалуйста, попробуйте позже."
    
    await bot.send_message(
        user_id,
        error_msg,
        reply_markup=ReplyKeyboards.main_menu()
    )
    return False







                                                                                
                                                                                   
                                            
                                                                             
                                                  
                                          
    
                                                                
                                                                   
                
    
                             






@router.callback_query(F.data.startswith(("confirm_order_", "cancel_order_")))
async def order_confirmation_handler(callback: CallbackQuery, state: FSMContext):
    action = "confirm" if callback.data.startswith("confirm") else "cancel"
    order_id = int(callback.data.split("_")[-1])
    order = await db.get_order(order_id)
    if not order or order['user_id'] != callback.from_user.id:
        await callback.answer("❌ Нет прав или заявка не найдена")
        return
    if action == "confirm":
        if not order:
            await callback.message.edit_text("❌ Заявка не найдена")
            return
        user_id = order['user_id']
        payment_type = order.get('payment_type')
        if order['total_amount'] and payment_type:
            await callback.message.edit_text(
                "⏳ Ваш запрос принят. Реквизиты будут отправлены в следующем сообщении.\nВремя ожидания до 4-х минут..."
            )
            asyncio.create_task(
                request_requisites_with_retries(order_id, user_id, payment_type, callback.bot)
            )
            await state.clear()  
            return
        else:
            text = (
                f"✅ <b>Заявка #{order.get('personal_id', order_id)} подтверждена!</b>\n\n"
                f"Ожидайте реквизиты для оплаты.\n"
                f"Время обработки: 5-15 минут."
            )
    else:
        await db.update_order(order_id, status='cancelled')
        order = await db.get_order(order_id)
        display_id = order.get('personal_id', order_id) if order else order_id
        text = f"❌ Заявка #{display_id} отменена."
    await callback.message.edit_text(text, parse_mode="HTML")
    await asyncio.sleep(3)
    await callback.bot.send_message(
        callback.message.chat.id,
        "🎯 Главное меню:",
        reply_markup=ReplyKeyboards.main_menu()
    )
    await state.clear() 







                                                                              
@router.message(F.text.in_(["💳 Банковская карта", "📱 СБП"]))
async def payment_method_handler(message: Message, state: FSMContext):
    logger.info(f"payment_method_handler вызывается для пользователя {message.from_user.id} с текстом: {message.text}")

    payment_type = "card" if "карта" in message.text else "sbp"
    data = await state.get_data()

                                                 
    rub_amount = data.get('rub_amount')
    btc_amount = data.get('btc_amount')
    btc_rate = data.get('btc_rate')

    logger.debug(f"Данные из состояния: rub_amount={rub_amount}, btc_amount={btc_amount}, btc_rate={btc_rate}")

    if rub_amount is None or btc_amount is None or btc_rate is None:
        logger.error(f"Недостаточно данных в состоянии пользователя {message.from_user.id}, прекращаю обработку.")
        await message.answer(
            "❌ Ошибка внутренних данных. Попробуйте начать заново через главное меню."
        )
        await state.clear()
        return
    
    total_amount = rub_amount / (1 - (await db.get_commission_percentage()) / 100)

    logger.info(f"Создаём заказ: user_id={message.from_user.id}, rub_amount={rub_amount}, btc_amount={btc_amount}, "
                f"btc_address={data.get('btc_address', data.get('address', ''))}, rate={btc_rate}, total_amount={total_amount}, payment_type={payment_type}")
    
    order_id = await db.create_order(
        user_id=message.from_user.id,
        amount_rub=rub_amount,
        amount_btc=btc_amount,
        btc_address=data.get('btc_address', data.get('address', '')),
        rate=btc_rate,
        total_amount=total_amount,
        payment_type=payment_type
    )
    logger.info(f"Заказ создан с ID {order_id}")

                                    
    order = await db.get_order(order_id)
    logger.debug(f"Данные заказа из БД: {order}")

                                                      
    try:
        logger.info(f"Попытка отправить уведомление операторам о новой заявке {order_id}")
        await notify_operators_new_order(message.bot, order)
        logger.info(f"Уведомление операторам о новой заявке #{order.get('personal_id', order_id)} успешно отправлено")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления операторам о новой заявке: {e}")

                                       
    is_sell_order = not order.get('btc_address')
    logger.info(f"Создаём платёжный заказ в API. is_sell_order={is_sell_order}, order_id={order_id}")

    try:
        api_response = await payment_api_manager.create_order(
            amount=int(total_amount),
            payment_type=payment_type,
            personal_id=str(order_id),
            is_sell_order=is_sell_order
        )
    except Exception as e:
        logger.error(f"Ошибка при обращении к API платёжного сервиса: {e}")
        await message.answer("❌ Ошибка связи с платёжным сервисом. Попробуйте позже.")
        await state.clear()
        return

    if api_response.get('success'):
        payment_data = api_response['data']
        api_name = api_response.get('api_name')
        
                                                    
                                            
        if api_name == 'NicePay':
            requisites_text = (
                f"🔗 <b>Ссылка для оплаты:</b> {payment_data['payment_url']}\n"
                f"💳 Тип платежа: {'Карта' if payment_type == 'card' else 'СБП'}\n"
                f"📋 ID транзакции: {payment_data['id']}"
            )
            reply_markup = ReplyKeyboards.main_menu()                                   
        else:
            requisites_text = (
                f"{'💳 Карта' if payment_type == 'card' else '📱 Телефон'}: {payment_data['requisite']}\n"
                f"👤 Получатель: {payment_data['owner']}\n"
                f"🏛 Банк: {payment_data['bank']}"
            )
            reply_markup = ReplyKeyboards.order_menu(is_nicepay=False)                              
        
                                                     
        update_data = {
            'requisites': requisites_text,
            'personal_id': payment_data['id'],
            'status': 'waiting'
        }
        if api_name == 'OnlyPays':
            update_data['onlypays_id'] = payment_data['id']
        elif api_name == 'PSPWare':
            update_data['pspware_id'] = payment_data['id']
        elif api_name == 'Greengo':
            update_data['greengo_id'] = payment_data['id']
        elif api_name == 'NicePay':
            update_data['nicepay_id'] = payment_data['id']

        try:
            await db.update_order(order_id, **update_data)
            logger.info(f"Обновлены данные заказа ID {order_id} с реквизитами оплаты")
        except Exception as e:
            logger.error(f"Ошибка обновления заказа {order_id} в БД: {e}")

        text = (
            f"💳 <b>Заявка #{payment_data['id']} создана!</b>\n\n"
            f"💰 Сумма к обмену: {rub_amount:,.0f} ₽\n"
            f"₿ Получите: {btc_amount:.8f} BTC\n"
            f"💸 К оплате: <b>{total_amount:,.0f} ₽</b>\n\n"
            f"📋 <b>Реквизиты для оплаты:</b>\n"
            f"{requisites_text}\n\n"
            f"⚠️ <b>Важно:</b>\n"
            f"• Переведите точную сумму\n"
            f"• После оплаты ожидайте подтверждения\n"
            f"• Bitcoin будет отправлен автоматически\n\n"
            f"⏰ Заявка действительна 30 минут"
        )

        try:
            await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
            logger.info(f"Пользователю {message.from_user.id} отправлена информация о реквизитах оплаты для заявки #{payment_data['id']}")
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {message.from_user.id} текста реквизитов: {e}")
    else:
        error_msg = api_response.get('error', 'Неизвестная ошибка')
        logger.error(f"Платёжный сервис вернул ошибку для заказа {order_id}: {error_msg}")
        await message.answer(
            f"❌ Ошибка создания заявки: {error_msg}\n\nПопробуйте позже или обратитесь в поддержку.",
            reply_markup=ReplyKeyboards.main_menu()
        )

    await state.clear()








@router.message(F.text == "🔄 Проверить статус")
async def check_status_handler(message: Message):
    orders = await db.get_user_orders(message.from_user.id, 1)
    if not orders:
        await message.answer(
            "У вас нет активных заявок",
            reply_markup=ReplyKeyboards.main_menu()
        )
        return
    
    order = orders[0]
    display_id = order.get('personal_id', order['id'])
    
                                                      
    if order.get('nicepay_id'):
        await message.answer(
            f"📋 Статус заявки #{display_id}: ⏳ В обработке\n\n"
            f"Для заявок статус обновляется автоматически.\n"
            f"Вы получите уведомление при изменении статуса.",
            reply_markup=ReplyKeyboards.main_menu()
        )
        return
    
    if order['status'] == 'waiting' and (order.get('onlypays_id') or order.get('pspware_id') or order.get('greengo_id')):
                                           
        api_name = 'OnlyPays' if order.get('onlypays_id') else 'PSPWare' if order.get('pspware_id') else 'Greengo' if order.get('greengo_id') else None
        api_order_id = order.get('onlypays_id') or order.get('pspware_id') or order.get('greengo_id')
        
        if not api_name or not api_order_id:
            await message.answer(
                f"❌ Ошибка: Не удалось определить API для заявки #{display_id}",
                reply_markup=ReplyKeyboards.main_menu()
            )
            return
        
        api_response = await payment_api_manager.get_order_status(
            order_id=api_order_id,
            api_name=api_name
        )
        
        if api_response and api_response.get('success'):
            status_data = api_response['data']
            logger.debug(f"Status data for order {display_id}: {status_data}")                    
            if status_data.get('status') == 'finished':
                                                      
                webhook_data = {
                    'id': api_order_id,
                    'status': 'finished',
                    'personal_id': str(order['id']),
                    'received_sum': status_data.get('received_sum', order['total_amount'])
                }
                
                                                               
                if order.get('onlypays_id'):
                    await process_onlypays_webhook(webhook_data, message.bot)
                elif order.get('pspware_id'):
                    await process_pspware_webhook(webhook_data, message.bot)
                elif order.get('greengo_id'):
                    await process_greengo_webhook(webhook_data, message.bot)
                
                await message.answer(
                    f"✅ <b>Заявка #{display_id} оплачена!</b>\n\n"
                    f"Платеж получен и обрабатывается.\n"
                    f"Bitcoin будет отправлен в течение 1 часа.",
                    reply_markup=ReplyKeyboards.main_menu(),
                    parse_mode="HTML"
                )
            elif status_data.get('status') == 'cancelled':
                await db.update_order(order['id'], status='cancelled')
                await message.answer(
                    f"❌ Заявка #{display_id} отменена.\n\n"
                    f"Создайте новую заявку для обмена.",
                    reply_markup=ReplyKeyboards.main_menu(),
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"⏳ Заявка #{display_id} в обработке\n\n"
                    f"Ожидаем поступления платежа...\n"
                    f"Заявка действительна 30 минут.",
                    reply_markup=ReplyKeyboards.order_menu(),
                    parse_mode="HTML"
                )
        else:
            error_message = api_response.get('error', 'Неизвестная ошибка') if api_response else 'Не удалось проверить статус'
            await message.answer(
                f"❌ Ошибка проверки статуса: {error_message}\n"
                f"Попробуйте позже или обратитесь в поддержку.",
                reply_markup=ReplyKeyboards.main_menu()
            )
    else:
        status_text = {
            'waiting': '⏳ В обработке',
            'paid_by_client': '💰 Оплачена, обрабатывается',
            'completed': '✅ Завершена',
            'cancelled': '❌ Отменена',
            'problem': '⚠️ Проблемная'
        }.get(order['status'], f"❓ {order['status']}")
                                                    
        cleaned_status_text = ''.join(c for c in status_text if c not in '<>')
        await message.answer(
            f"📋 Статус заявки #{display_id}: {cleaned_status_text}",
            reply_markup=ReplyKeyboards.main_menu()
        )






@router.message(F.text == "О сервисе ℹ️")
async def about_handler(message: Message):
    btc_rate = await BitcoinAPI.get_btc_rate()
    COMMISSION_PERCENT = await db.get_commission_percentage()
    text = (
        f"👑 {config.EXCHANGE_NAME} 👑\n\n"
        f"🔷 НАШИ ПРИОРИТЕТЫ 🔷\n"
        f"🔸 100% ГАРАНТИИ\n"
        f"🔸 БЫСТРЫЙ ОБМЕН\n"
        f"🔸 НАДЕЖНЫЙ СЕРВИС\n"
        f"🔸 КАЧЕСТВЕННАЯ РАБОТА\n"
        f"🔸 АНОНИМНЫЙ ОБМЕН\n\n"
        f"🔷 НАШИ КОНТАКТЫ 🔷\n"
        f"⚙️ ОПЕРАТОР Тех.поддержка ➖ {config.SUPPORT_MANAGER}\n"
        f"📣 НОВОСТНОЙ КАНАЛ ➖ {config.NEWS_CHANNEL}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💱 Текущий курс BTC: {btc_rate:,.0f} ₽\n"
        f"🏛 Комиссия сервиса: {COMMISSION_PERCENT}%\n\n"
        f"💰 Лимиты: {config.MIN_AMOUNT:,} - {config.MAX_AMOUNT:,} ₽"
    )
    await message.answer(text, reply_markup=ReplyKeyboards.main_menu(), parse_mode="HTML")

@router.message(F.text == "Калькулятор валют")
async def calculator_handler(message: Message, state: FSMContext):
    await state.clear()
    text = "<b>Выберите направление:</b>"
    await message.answer(
        text,
        reply_markup=InlineKeyboards.currency_calculator(),
        parse_mode="HTML"
    )

@router.message(F.text == "Оставить отзыв")
async def review_handler(message: Message, state: FSMContext):
    await message.answer(
        "📝 <b>Оставить отзыв</b>\n\n"
        "Напишите ваш отзыв о работе сервиса.\n"
        "Мы ценим любую обратную связь!",
        reply_markup=ReplyKeyboards.back_to_main(),
        parse_mode="HTML"
    )
    await state.set_state(ExchangeStates.waiting_for_contact)

@router.message(F.text == "Как сделать обмен?")
async def how_to_exchange_handler(message: Message):
    text = (
        "📘 <b>Как сделать обмен?</b>\n\n"
        "📹 Видео-инструкция: \n\n"
    )
    await message.answer(text, reply_markup=ReplyKeyboards.main_menu(), parse_mode="HTML")

@router.message(F.text == "Друзья")
async def referral_handler(message: Message):
    try:
        user = await db.get_user(message.from_user.id)
        if not user:
            await db.add_user(
                message.from_user.id,
                message.from_user.username,
                message.from_user.first_name,
                message.from_user.last_name
            )
            user = await db.get_user(message.from_user.id)
        if not user:
            await message.answer(
                "❌ Ошибка доступа к базе данных.\n"
                "Попробуйте выполнить /start",
                reply_markup=ReplyKeyboards.main_menu()
            )
            return
        stats = await db.get_referral_stats(message.from_user.id)
        text = (
            f"👥 <b>Реферальная программа</b>\n\n"
            f"🎁 <b>Ваши бонусы:</b>\n"
            f"• За каждого друга: 100 ₽\n"
            f"• От каждой сделки друга: 2%\n\n"
            f"📊 <b>Ваша статистика:</b>\n"
            f"👤 Приглашено друзей: {stats['referral_count']} чел.\n"
            f"💰 Заработано бонусов: {stats['referral_balance']} ₽\n\n"
            f"🔗 <b>Ваша реферальная ссылка:</b>\n"
            f"<code>https://t.me/{config.BOT_USERNAME}?start=r-{message.from_user.id}</code>\n\n"
            f"📤 <b>Отправьте эту ссылку друзьям!</b>\n"
            f"Когда они зарегистрируются и сделают обмен, "
            f"вы получите бонусы!"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="📤 Поделиться ссылкой", 
                url=f"https://t.me/share/url?url=https://t.me/{config.BOT_USERNAME}?start=r-{message.from_user.id}&text=Присоединяйся к лучшему криптообменнику {config.EXCHANGE_NAME}!"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🏠 Главная", 
                callback_data="referral_main_menu"
            )
        )
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Referral handler error: {e}")
        await message.answer(
            "❌ Произошла ошибка при загрузке реферальной программы.\n"
            "Попробуйте позже или выполните /start",
            reply_markup=ReplyKeyboards.main_menu()
        )

@router.callback_query(F.data == "referral_history")
async def referral_history_handler(callback: CallbackQuery):
    await callback.answer("История бонусов пока пуста")

@router.callback_query(F.data == "referral_main_menu")
async def referral_main_menu_handler(callback: CallbackQuery):
    await show_main_menu(callback, is_callback=True)

@router.message(F.text == "₽ → ₿ Рубли в Bitcoin")
async def rub_to_btc_handler(message: Message, state: FSMContext):
    await state.update_data(exchange_type="rub")
    min_amount = await db.get_setting("min_amount", config.MIN_AMOUNT)
    max_amount = await db.get_setting("max_amount", config.MAX_AMOUNT)
    text = (
        f"💰 <b>Обмен рублей на Bitcoin</b>\n\n"
        f"Введите сумму в рублях:\n\n"
        f"Минимум: {min_amount:,} ₽\n"
        f"Максимум: {max_amount:,} ₽"
    )
    await message.answer(text, reply_markup=ReplyKeyboards.back_to_main(), parse_mode="HTML")
    await state.set_state(ExchangeStates.waiting_for_amount)

@router.message(F.text == "₿ → ₽ Bitcoin в рубли")
async def btc_to_rub_handler(message: Message, state: FSMContext):
    text = (
        f"₿ <b>Обмен Bitcoin на рубли</b>\n\n"
        f"Введите количество Bitcoin:"
    )
    await message.answer(text, reply_markup=ReplyKeyboards.back_to_main(), parse_mode="HTML")
    await state.set_state(ExchangeStates.waiting_for_amount)

@router.message(F.text == "📊 Мои заявки")
async def my_orders_handler(message: Message):
    orders = await db.get_user_orders(message.from_user.id, 5)
    if not orders:
        text = (
            "📋 <b>Ваши заявки</b>\n\n"
            "У вас пока нет заявок.\n"
            "Создайте новую заявку на обмен!"
        )
    else:
        status_emoji_map = {
            'waiting': '⏳',
            'paid_by_client': '💰',
            'completed': '✅',
            'cancelled': '❌',
            'problem': '⚠️'
        }
        text = "📋 <b>Ваши последние заявки:</b>\n\n"
        for order in orders:
            emoji = status_emoji_map.get(order['status'], '❓')
            display_id = order.get('personal_id', order['id'])
            text += (
                f"{emoji} Заявка #{display_id}\n"
                f"💰 {order['total_amount']:,.0f} ₽\n"
                f"Статус: {order['status']}\n"
                f"📅 {order['created_at'][:16]}\n\n"
            )
    await message.answer(text, reply_markup=ReplyKeyboards.main_menu(), parse_mode="HTML")

@router.message(F.text == "📈 Курсы валют")
async def rates_handler(message: Message):
    try:
        btc_rate = await BitcoinAPI.get_btc_rate()
        text = (
            f"📈 <b>Актуальные курсы</b>\n\n"
            f"₿ Bitcoin: {btc_rate:,.0f} ₽\n\n"
            f"💡 Курсы обновляются каждые 5 минут"
        )
    except:
        text = (
            f"📈 <b>Актуальные курсы</b>\n\n"
            f"❌ Ошибка получения курса\n\n"
            f"💡 Попробуйте позже"
        )
    await message.answer(text, reply_markup=ReplyKeyboards.main_menu(), parse_mode="HTML")

@router.message(F.text == "◶️ Главное меню")
async def main_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    await show_main_menu(message)

@router.message(F.text == "◶️ Назад")
async def back_handler(message: Message, state: FSMContext):
    await message.answer(
        "💰 <b>Покупка криптовалюты</b>\n\n"
        "Выберите направление обмена:",
        reply_markup=ReplyKeyboards.exchange_menu(),
        parse_mode="HTML"
    )

@router.message(ExchangeStates.waiting_for_contact)
async def contact_handler(message: Message, state: FSMContext):
    if message.text == "◶️ Главное меню":
        await state.clear()
        await show_main_menu(message)
        return
    user_id = message.from_user.id
    try:
        last_review = await db.get_last_review_time(user_id)
        current_time = message.date.replace(tzinfo=None)
        if last_review:
            time_diff = current_time - last_review
            cooldown_hours = 24
            if time_diff.total_seconds() < cooldown_hours * 3600:
                remaining = cooldown_hours * 3600 - time_diff.total_seconds()
                hours_left = int(remaining // 3600)
                minutes_left = int((remaining % 3600) // 60)
                await message.answer(
                    f"⏰ <b>Отзыв можно оставить раз в сутки</b>\n\n"
                    f"Время до следующего отзыва: {hours_left}ч {minutes_left}м",
                    reply_markup=ReplyKeyboards.main_menu(),
                    parse_mode="HTML"
                )
                await state.clear()
                return
        if len(message.text) < 10:
            await message.answer(
                f"📝 <b>Отзыв слишком короткий</b>\n\n"
                f"Минимум 10 символов, у вас: {len(message.text)}",
                parse_mode="HTML"
            )
            return
        if len(message.text) > 1000:
            await message.answer(
                f"📝 <b>Отзыв слишком длинный</b>\n\n"
                f"Максимум 1000 символов, у вас: {len(message.text)}",
                parse_mode="HTML"
            )
            return
        user = await db.get_user(user_id)
        review_text = (
            f"📝 <b>Новый отзыв</b>\n\n"
            f"📅 {current_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💬 <b>Текст:</b>\n{message.text}"
        )
        review_id = await db.save_review(user_id, message.text)
        if config.ADMIN_CHAT_ID:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"review_approve_{review_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"review_reject_{review_id}")
            )
            await message.bot.send_message(
                config.ADMIN_CHAT_ID,
                review_text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        await message.answer(
            "✅ <b>Спасибо за отзыв!</b>\n\n"
            "Отзыв отправлен на модерацию.",
            reply_markup=ReplyKeyboards.main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Review error: {e}")
        await message.answer(
            "❌ Ошибка отправки отзыва. Попробуйте позже.",
            reply_markup=ReplyKeyboards.main_menu()
        )
    await state.clear()







from aiogram.types import ReplyKeyboardRemove

                         
                                                  
                                                                                                
                

                                              
                                                
                               
                                                                                                            


@router.message(F.text == "❌ Отменить заявку")
async def cancel_order_handler(message: Message):
    orders = await db.get_user_orders(message.from_user.id, 1)
    if not orders:
        await message.answer(
            "У вас нет активных заявок",
            reply_markup=ReplyKeyboards.main_menu()
        )
        return

    order = orders[0]
    order_id = order['id']
    if order['user_id'] != message.from_user.id:
        await message.answer("❌ Нет прав для этой заявки", reply_markup=ReplyKeyboardRemove())
        return

    await db.update_order(order_id, status='cancelled')
    display_id = order.get('personal_id', order_id)
    await message.answer(
        f"❌ Заявка #{display_id} отменена.",
        parse_mode="HTML",
        reply_markup=ReplyKeyboards.main_menu()                                  
    )











@router.message(ExchangeStates.waiting_for_note)
async def note_handler(message: Message, state: FSMContext):
    if message.text == "◶️ Главное меню":
        await state.clear()
        await show_main_menu(message)
        return
    data = await state.get_data()
    order_id = data.get("order_id")
    try:
        order = await db.get_order(order_id)
        if not order:
            await message.answer("❌ Заявка не найдена")
            await state.clear()
            return
        display_id = order.get('personal_id', order_id)
        await db.update_order(order_id, note=message.text)
        text = (
            f"📝 <b>Заметка добавлена к заявке #{display_id}</b>\n\n"
            f"💬 Текст: {message.text}\n\n"
            f"🔧 Заявка помечена как проблемная и ожидает решения."
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=ReplyKeyboards.main_menu()
        )
        await notify_operators_error_order(order, message.text)
    except Exception as e:
        logger.error(f"Note handler error: {e}")
        await message.answer(
            "❌ Ошибка при добавлении заметки",
            reply_markup=ReplyKeyboards.main_menu()
        )
    await state.clear()

@router.callback_query(F.data.startswith("op_handle_"))
async def operator_handle_handler(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[-1])
    try:
        order = await db.get_order(order_id)
        if not order:
            await callback.answer("Заявка не найдена")
            return
        display_id = order.get('personal_id', order_id)
        await db.update_order(order_id, status='processing')
        text = (
            f"🔧 <b>Обработка заявки #{display_id}</b>\n\n"
            f"👤 Обработал: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Заявка взята в обработку."
        )
        await callback.message.edit_text(
            text,
            parse_mode="HTML"
        )
        await callback.answer("🔧 Заявка в обработке")
    except Exception as e:
        logger.error(f"Operator handle handler error: {e}")
        await callback.answer("❌ Ошибка")

@router.callback_query(F.data.startswith("review_approve_"))
async def review_approve_handler(callback: CallbackQuery):
    review_id = int(callback.data.split("_")[-1])
    try:
        review = await db.get_review(review_id)
        if not review:
            await callback.answer("Отзыв не найден")
            return
        await db.update_review(review_id, status='approved')
        text = (
            f"✅ <b>Отзыв #{review_id} одобрен</b>\n\n"
            f"👤 Обработал: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await callback.message.edit_text(
            text,
            parse_mode="HTML"
        )
        if config.REVIEWS_CHANNEL:
            await callback.bot.send_message(
                config.REVIEWS_CHANNEL,
                f"📝 <b>Новый отзыв</b>\n\n{review['text']}",
                parse_mode="HTML"
            )
        await callback.answer("✅ Отзыв одобрен")
    except Exception as e:
        logger.error(f"Review approve handler error: {e}")
        await callback.answer("❌ Ошибка")

@router.callback_query(F.data.startswith("review_reject_"))
async def review_reject_handler(callback: CallbackQuery):
    review_id = int(callback.data.split("_")[-1])
    try:
        await db.update_review(review_id, status='rejected')
        text = (
            f"❌ <b>Отзыв #{review_id} отклонен</b>\n\n"
            f"👤 Обработал: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await callback.message.edit_text(
            text,
            parse_mode="HTML"
        )
        await callback.answer("❌ Отзыв отклонен")
    except Exception as e:
        logger.error(f"Review reject handler error: {e}")
        await callback.answer("❌ Ошибка")

@router.message(Command("broadcast"), F.from_user.id.in_(config.ADMIN_USER_ID))
async def broadcast_handler(message: Message, state: FSMContext):
    try:
        await message.answer(
            "📢 Введите сообщение для рассылки всем пользователям:",
            reply_markup=ReplyKeyboards.back_to_main(),
            parse_mode="HTML"
        )
        await state.set_state(ExchangeStates.waiting_for_contact)
    except Exception as e:
        logger.error(f"Broadcast handler error: {e}")
        await message.answer("❌ Ошибка при запуске рассылки")

@router.message(ExchangeStates.waiting_for_contact)
async def broadcast_message_handler(message: Message, state: FSMContext):
    if message.text == "◶️ Главное меню":
        await state.clear()
        await show_main_menu(message)
        return
    try:
        users = await db.get_all_users()
        broadcast_text = message.text
        success_count = 0
        for user in users:
            try:
                await message.bot.send_message(
                    user['user_id'],
                    broadcast_text,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
                success_count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                logger.warning(f"Failed to send broadcast to {user['user_id']}: {e}")
        await message.answer(
            f"✅ <b>Рассылка завершена</b>\n\n"
            f"Отправлено {success_count} из {len(users)} пользователям",
            reply_markup=ReplyKeyboards.main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Broadcast message handler error: {e}")
        await message.answer(
            "❌ Ошибка при отправке рассылки",
            reply_markup=ReplyKeyboards.main_menu()
        )
    await state.clear()

@router.message(CommandStart(deep_link=True))
async def deep_link_start_handler(message: Message, state: FSMContext):
    try:
        args = message.text.split()
        if len(args) > 1 and args[1].startswith("r-"):
            referral_user_id = int(args[1].split("-")[1])
            await state.update_data(referral_user_id=referral_user_id)
        user = await db.get_user(message.from_user.id)
        if not user:
            captcha_enabled = await db.get_setting("captcha_enabled", config.CAPTCHA_ENABLED)
            if captcha_enabled:
                image_buffer, answer = CaptchaGenerator.generate_image_captcha()
                await db.create_captcha_session(message.from_user.id, answer.upper())
                captcha_photo = BufferedInputFile(
                    image_buffer.read(),
                    filename="captcha.png"
                )
                await message.answer_photo(
                    photo=captcha_photo,
                    caption="🤖 Добро пожаловать! Введите код с картинки:",
                    reply_markup=ReplyKeyboards.back_to_main()
                )
                await state.set_state(ExchangeStates.waiting_for_captcha)
                return
            else:
                await db.add_user(
                    message.from_user.id,
                    message.from_user.username,
                    message.from_user.first_name,
                    message.from_user.last_name,
                    referred_by=referral_user_id if 'referral_user_id' in await state.get_data() else None
                )
        await show_main_menu(message)
    except Exception as e:
        logger.error(f"Deep link start handler error: {e}")
        await message.answer(
            "❌ Ошибка обработки реферальной ссылки. Попробуйте /start",
            reply_markup=ReplyKeyboards.main_menu()
        )

@router.message(Command("stats"), F.from_user.id.in_(config.ADMIN_USER_ID))
async def admin_stats_handler(message: Message):
    try:
        total_users = await db.get_total_users()
        total_orders = await db.get_total_orders()
        completed_orders = await db.get_total_completed_orders()
        total_volume_rub = await db.get_total_volume_rub()
        text = (
            f"📊 <b>Статистика сервиса</b>\n\n"
            f"👥 Пользователей: {total_users:,}\n"
            f"📋 Всего заявок: {total_orders:,}\n"
            f"✅ Завершенных заявок: {completed_orders:,}\n"
            f"💰 Общий объем: {total_volume_rub:,.0f} ₽"
        )
        await message.answer(
            text,
            reply_markup=ReplyKeyboards.main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Admin stats handler error: {e}")
        await message.answer(
            "❌ Ошибка получения статистики",
            reply_markup=ReplyKeyboards.main_menu()
        )




@router.message(Command("health"), F.from_user.id.in_(config.ADMIN_USER_ID))
async def health_check_handler(message: Message):
    try:
        response = await payment_api_manager.health_check()
        text = ""
        for api_name, result in response.items():
            if result.get("success"):
                text += f"✅ {api_name}: <b>{result.get('message', 'Working')}</b>\n"
            else:
                text += f"❌ {api_name}: {result.get('error', 'Неизвестная ошибка')}\n"
                if "status_code" in result:
                    text += f"Код ошибки: {result['status_code']}\n"
        await message.answer(
            text,
            reply_markup=ReplyKeyboards.main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Health check handler error: {e}")
        await message.answer(
            "❌ Ошибка при проверке состояния сервиса",
            reply_markup=ReplyKeyboards.main_menu()
        )







async def process_pspware_webhook(webhook_data: dict, bot):
    try:
        order_id = webhook_data.get('personal_id')
        status = webhook_data.get('status')
        received_sum = webhook_data.get('received_sum')

        if not order_id:
            logger.error(f"Webhook без personal_id: {webhook_data}")
            return

        order = await db.get_order(int(order_id))
        if not order:
            logger.error(f"Заказ не найден: {order_id}")
            return

        if status == 'finished':
            await db.update_order(
                order['id'],
                status='paid_by_client',
                received_sum=received_sum
            )
            updated_order = await db.get_order(order['id'])
            await notify_operators_paid_order(bot, updated_order, received_sum)
            await notify_client_payment_received(bot, updated_order)
        elif status == 'cancelled':
            await db.update_order(order['id'], status='cancelled')
            updated_order = await db.get_order(order['id'])
            await notify_client_order_cancelled(bot, updated_order)
    except Exception as e:
        logger.error(f"Ошибка обработки webhook PSPWare: {e}")

async def process_greengo_webhook(webhook_data: dict, bot):
    try:
        order_id = webhook_data.get('personal_id')
        status = webhook_data.get('order_status')
        received_sum = webhook_data.get('amount_payable')

        if not order_id:
            logger.error(f"Greengo webhook without personal_id: {webhook_data}")
            return
        
        order = await db.get_order(int(order_id))
        if not order:
            logger.error(f"Order not found: {order_id}")
            return
        
        if status == 'completed':
            await db.update_order(
                order['id'], 
                status='paid_by_client',
                received_sum=received_sum
            )
            updated_order = await db.get_order(order['id'])
            await notify_operators_paid_order(bot, updated_order, received_sum)
            await notify_client_payment_received(bot, updated_order)
            logger.info(f"Greengo заявка #{order_id} успешно обработана")
        elif status == 'canceled':
            await db.update_order(order['id'], status='cancelled')
            updated_order = await db.get_order(order['id'])
            await notify_client_order_cancelled(bot, updated_order)
    except Exception as e:
        logger.error(f"Greengo webhook processing error: {e}")






async def process_nicepay_webhook(webhook_data: dict, bot):
    try:
        order_id = webhook_data.get('merchantOrderId')
        status = webhook_data.get('status')
        received_sum = webhook_data.get('amount')

        if not order_id:
            logger.error(f"NicePay webhook without merchantOrderId: {webhook_data}")
            return

        order = await db.get_order(int(order_id))
        if not order:
            logger.error(f"Order not found: {order_id}")
            return

        if status == 'PAID':
            await db.update_order(
                order['id'],
                status='paid_by_client',
                received_sum=received_sum
            )
            updated_order = await db.get_order(order['id'])
            await notify_operators_paid_order(bot, updated_order, received_sum)
            await notify_client_payment_received(bot, updated_order)
            logger.info(f"NicePay заявка #{order_id} успешно оплачена")
        elif status == 'CANCELLED':
            await db.update_order(order['id'], status='cancelled')
            updated_order = await db.get_order(order['id'])
            await notify_client_order_cancelled(bot, updated_order)
            logger.info(f"NicePay заявка #{order_id} отменена")
    except Exception as e:
        logger.error(f"NicePay webhook processing error: {e}")







async def process_onlypays_webhook(webhook_data: dict, bot):
    try:
        order_id = webhook_data.get('personal_id')
        status = webhook_data.get('status')
        received_sum = webhook_data.get('received_sum')

        if not order_id:
            logger.error(f"OnlyPays webhook без personal_id: {webhook_data}")
            return

        order = await db.get_order(int(order_id))
        if not order:
            logger.error(f"Заказ не найден: {order_id}")
            return

        if status == 'finished':
            await db.update_order(
                order['id'],
                status='paid_by_client',
                received_sum=received_sum
            )
            updated_order = await db.get_order(order['id'])
            await notify_operators_paid_order(bot, updated_order, received_sum)
            await notify_client_payment_received(bot, updated_order)
            logger.info(f"Заявка #{updated_order.get('personal_id', order_id)} успешно оплачена")
        elif status == 'cancelled':
            await db.update_order(order['id'], status='cancelled')
            updated_order = await db.get_order(order['id'])
            await notify_client_order_cancelled(bot, updated_order)
            logger.info(f"Заявка #{updated_order.get('personal_id', order_id)} отменена")
    except Exception as e:
        logger.error(f"Ошибка обработки OnlyPays webhook: {e}")



