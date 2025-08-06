import logging
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import Database
from keyboards.inline import Keyboards
from keyboards.reply import ReplyKeyboards
from config import config

logger = logging.getLogger(__name__)
router = Router()

class OperatorStates(StatesGroup):
    waiting_for_note = State()

db = Database(config.DATABASE_URL)

OPERATORS = [
    config.ADMIN_USER_ID
]

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_USER_ID

def is_operator(user_id: int) -> bool:
    return user_id in OPERATORS

def is_operator_chat(chat_id: int) -> bool:
    return chat_id == config.OPERATOR_CHAT_ID

def can_handle_orders(user_id: int, chat_id: int) -> bool:
    return (is_operator(user_id) or is_admin(user_id)) and is_operator_chat(chat_id)



async def notify_operators_new_order(bot, order: dict):
    display_id = order.get('personal_id', order.get('id', 'N/A'))
    chat_id = config.OPERATOR_CHAT_ID
    logger.info(f"notify_operators_new_order: попытка отправки уведомления заявки #{display_id} в чат {chat_id}")
    try:
        text = (
            f"📥 <b>НОВАЯ ЗАЯВКА</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Клиент ID: {order.get('user_id', 'N/A')}\n"
            f"💰 Сумма заявки: {order.get('total_amount', 0):,.0f} ₽\n"
            f"₿ К отправке: {order.get('amount_btc', 0):.8f} BTC\n"
            f"📍 Адрес: <code>{order.get('btc_address', 'N/A')}</code>\n\n"
            f"⏰ Создана: {order.get('created_at', 'N/A')}\n"
            f"📱 Тип: {order.get('payment_type', 'N/A')}\n\n"
            f"⚡ <b>Требуется обработка заявки</b>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Пометить как оплачена", callback_data=f"op_mark_paid_{order.get('id')}"),
            InlineKeyboardButton(text="⚠️ Проблема", callback_data=f"op_problem_{order.get('id')}")
        )
        builder.row(
            InlineKeyboardButton(text="📝 Заметка", callback_data=f"op_note_{order.get('id')}"),
            InlineKeyboardButton(text="📋 Детали заявки", callback_data=f"op_details_{order.get('id')}")
        )
        await bot.send_message(
            chat_id,
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        logger.info(f"notify_operators_new_order: уведомление заявки #{display_id} успешно отправлено")
    except Exception as e:
        logger.error(f"notify_operators_new_order: ошибка отправки уведомления заявки #{display_id}: {e}", exc_info=True)



async def notify_operators_paid_order(bot, order: dict, received_sum: float = None):
    try:
        display_id = order.get('personal_id', order['id'])
        if not received_sum:
            received_sum = order.get('total_amount', 0)
        text = (
            f"💰 <b>ЗАЯВКА ОПЛАЧЕНА</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Клиент ID: {order.get('user_id', 'N/A')}\n"
            f"💵 Получено: {received_sum:,.0f} ₽\n"
            f"💰 Сумма заявки: {order['total_amount']:,.0f} ₽\n"
            f"₿ К отправке: {order['amount_btc']:.8f} BTC\n"
            f"📍 Адрес: <code>{order['btc_address']}</code>\n\n"
            f"⏰ Создана: {order.get('created_at', 'N/A')}\n"
            f"📱 Тип: {order.get('payment_type', 'N/A')}\n\n"
            f"🎯 <b>Требуется отправка Bitcoin!</b>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Отправил Bitcoin",
                callback_data=f"op_sent_{order['id']}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="⚠️ Проблема",
                callback_data=f"op_problem_{order['id']}"
            ),
            InlineKeyboardButton(
                text="📝 Заметка",
                callback_data=f"op_note_{order['id']}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="📋 Детали заявки",
                callback_data=f"op_details_{order['id']}"
            )
        )
        await bot.send_message(
            config.OPERATOR_CHAT_ID,
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        logger.info(f"Операторам отправлено уведомление о оплаченной заявке #{display_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления об оплаченной заявке: {e}")

async def notify_operators_error_order(bot, order: dict, error_message: str):
    try:
        display_id = order.get('personal_id', order['id'])
        text = (
            f"⚠️ <b>ОШИБКА В ЗАЯВКЕ</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Клиент ID: {order.get('user_id', 'N/A')}\n"
            f"💰 Сумма: {order['total_amount']:,.0f} ₽\n"
            f"❌ Ошибка: {error_message}\n\n"
            f"⏰ Создана: {order.get('created_at', 'N/A')}\n\n"
            f"🔧 <b>Требуется вмешательство!</b>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🔧 Обработать",
                callback_data=f"op_handle_{order['id']}"
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"op_cancel_{order['id']}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="📝 Заметка",
                callback_data=f"op_note_{order['id']}"
            )
        )
        await bot.send_message(
            config.OPERATOR_CHAT_ID,
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        logger.info(f"Операторам отправлено уведомление об ошибочной заявке #{display_id}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления об ошибочной заявке: {e}")

async def notify_client_payment_received(bot, order: dict):
    try:
        display_id = order.get('personal_id', order['id'])
        text = (
            f"✅ <b>Платеж получен!</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"💰 Сумма: {order['total_amount']:,.0f} ₽\n"
            f"₿ К получению: {order['amount_btc']:.8f} BTC\n\n"
            f"🔄 <b>Обрабатываем заявку...</b>\n"
            f"Bitcoin будет отправлен на ваш адрес в течение 1 часа.\n\n"
            f"📱 Вы получите уведомление о завершении."
        )
        await bot.send_message(
            order['user_id'],
            text,
            parse_mode="HTML",
            reply_markup=ReplyKeyboards.main_menu()
        )
        logger.info(f"Клиенту {order['user_id']} отправлено уведомление о получении платежа по заявке #{display_id}")
    except Exception as e:
        logger.error(f"Ошибка при уведомлении клиента о полученном платеже: {e}")

async def notify_client_order_cancelled(bot, order: dict):
    try:
        display_id = order.get('personal_id', order['id'])
        text = (
            f"❌ <b>Заявка отменена</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"💰 Сумма: {order['total_amount']:,.0f} ₽\n\n"
            f"Причина: Превышено время ожидания оплаты\n\n"
            f"Создайте новую заявку для обмена."
        )
        await bot.send_message(
            order['user_id'],
            text,
            parse_mode="HTML",
            reply_markup=ReplyKeyboards.main_menu()
        )
        logger.info(f"Клиенту {order['user_id']} отправлено уведомление об отмене заявки #{display_id}")
    except Exception as e:
        logger.error(f"Ошибка при уведомлении клиента об отмене заявки: {e}")

async def notify_client_order_completed(bot, order: dict):
    try:
        display_id = order.get('personal_id', order['id'])
        text = (
            f"🎉 <b>Заявка завершена!</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"₿ Отправлено: {order['amount_btc']:.8f} BTC\n"
            f"📍 На адрес: <code>{order['btc_address']}</code>\n\n"
            f"✅ <b>Bitcoin успешно отправлен!</b>\n"
            f"Проверьте ваш кошелек.\n\n"
            f"Спасибо за использование {config.EXCHANGE_NAME}!"
        )
        await bot.send_message(
            order['user_id'],
            text,
            parse_mode="HTML",
            reply_markup=ReplyKeyboards.main_menu()
        )
        logger.info(f"Клиенту {order['user_id']} отправлено уведомление о завершении заявки #{display_id}")
    except Exception as e:
        logger.error(f"Ошибка при уведомлении клиента о завершении заявки: {e}")


@router.callback_query(F.data.startswith("op_sent_"))
async def operator_sent_handler(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[-1])
    try:
        await db.update_order(order_id, status='completed')
        order = await db.get_order(order_id)
        if not order:
            await callback.answer("Заявка не найдена")
            logger.warning(f"Оператор {callback.from_user.id} пытался отметить несуществующую заявку #{order_id} как завершенную")
            return
        display_id = order.get('personal_id', order_id)
        text_client = (
            f"🎉 <b>Заявка завершена!</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"₿ Отправлено: {order['amount_btc']:.8f} BTC\n"
            f"📍 На адрес: <code>{order['btc_address']}</code>\n\n"
            f"✅ <b>Bitcoin успешно отправлен!</b>\n"
            f"Проверьте ваш кошелек.\n\n"
            f"Спасибо за использование {config.EXCHANGE_NAME}!"
        )
        await callback.bot.send_message(
            order['user_id'],
            text_client,
            parse_mode="HTML",
            reply_markup=ReplyKeyboards.main_menu()
        )
        await callback.message.edit_text(
            f"✅ <b>ЗАЯВКА ЗАВЕРШЕНА</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Обработал: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время завершения: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💎 Bitcoin отправлен клиенту!"
        )
        await callback.answer("✅ Заявка отмечена как завершенная")
        logger.info(f"Заявка #{display_id} отмечена как завершенная оператором {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка в handler'e отметки заявки как завершенной: {e}")
        await callback.answer("❌ Ошибка обновления статуса")

@router.callback_query(F.data.startswith("op_mark_paid_"))
async def operator_mark_paid_handler(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[-1])
    try:
        await db.update_order(order_id, status='paid_by_client')
        order = await db.get_order(order_id)
        if not order:
            await callback.answer("Заявка не найдена")
            logger.warning(f"Оператор {callback.from_user.id} пытался пометить несуществующую заявку #{order_id} как оплачена")
            return
        await notify_operators_paid_order(callback.bot, order)
        await notify_client_payment_received(callback.bot, order)
        await callback.message.edit_text(
            f"✅ <b>ЗАЯВКА ПОМЕЧЕНА КАК ОПЛАЧЕННАЯ</b>\n\n"
            f"🆔 Заявка: #{order.get('personal_id', order_id)}\n"
            f"👤 Пометил: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await callback.answer("Заявка отмечена как оплаченная")
        logger.info(f"Заявка #{order_id} отмечена как оплаченная оператором {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при отметке заявки как оплаченной: {e}")
        await callback.answer("Ошибка при обновлении статуса заявки")

@router.callback_query(F.data.startswith("op_problem_"))
async def operator_problem_handler(callback: CallbackQuery):
    if not can_handle_orders(callback.from_user.id, callback.message.chat.id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        logger.warning(f"Пользователь {callback.from_user.id} пытался отметить заявку проблемной без прав")
        return
    order_id = int(callback.data.split("_")[-1])
    try:
        await db.update_order(order_id, status='problem')
        order = await db.get_order(order_id)
        display_id = order.get('personal_id', order_id) if order else order_id
        admin_text = (
            f"⚠️ <b>ПРОБЛЕМНАЯ ЗАЯВКА</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Оператор: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"❗ Требуется вмешательство администратора"
        )
        await callback.bot.send_message(config.ADMIN_CHAT_ID, admin_text, parse_mode="HTML")
        await callback.message.edit_text(
            f"⚠️ <b>ЗАЯВКА ОТМЕЧЕНА КАК ПРОБЛЕМНАЯ</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Оператор: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📨 Администратор уведомлен",
            parse_mode="HTML"
        )
        await callback.answer("⚠️ Заявка отмечена как проблемная")
        logger.info(f"Заявка #{display_id} отмечена проблемной оператором {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка обработки отметки заявки как проблемной: {e}")
        await callback.answer("❌ Ошибка")

@router.callback_query(F.data.startswith("op_note_"))
async def operator_note_handler(callback: CallbackQuery, state: FSMContext):
    if not can_handle_orders(callback.from_user.id, callback.message.chat.id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        logger.warning(f"Пользователь {callback.from_user.id} пытался добавить заметку без прав")
        return
    order_id = int(callback.data.split("_")[-1])
    await state.update_data(
        note_order_id=order_id,
        note_message_id=callback.message.message_id,
        note_user_id=callback.from_user.id
    )
    await callback.bot.send_message(
        callback.message.chat.id,
        f"📝 <b>Добавить заметку к заявке #{order_id}</b>\n\n"
        f"Напишите заметку в следующем сообщении:",
        parse_mode="HTML"
    )
    await state.set_state(OperatorStates.waiting_for_note)
    await callback.answer()
    logger.info(f"Оператор {callback.from_user.id} начал добавление заметки к заявке #{order_id}")

@router.callback_query(F.data.startswith("op_details_"))
async def operator_details_handler(callback: CallbackQuery):
    if not can_handle_orders(callback.from_user.id, callback.message.chat.id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        logger.warning(f"Пользователь {callback.from_user.id} пытался получить детали заявки без прав")
        return
    order_id = int(callback.data.split("_")[-1])
    try:
        order = await db.get_order(order_id)
        if not order:
            await callback.answer("Заявка не найдена")
            logger.warning(f"Запрошены детали несуществующей заявки #{order_id} оператором {callback.from_user.id}")
            return
        display_id = order.get('personal_id', order_id)
        text = (
            f"📋 <b>ДЕТАЛИ ЗАЯВКИ #{display_id}</b>\n\n"
            f"🆔 ID: {order['id']}\n"
            f"🔗 OnlyPays ID: {order.get('onlypays_id', 'N/A')}\n"
            f"👤 Пользователь: {order['user_id']}\n"
            f"💰 Сумма: {order['total_amount']:,.0f} ₽\n"
            f"₿ Bitcoin: {order['amount_btc']:.8f} BTC\n"
            f"💱 Курс: {order.get('rate', 0):,.0f} ₽\n"
            f"📱 Тип оплаты: {order.get('payment_type', 'N/A')}\n"
            f"📊 Статус: {order.get('status', 'N/A')}\n"
            f"⏰ Создана: {order.get('created_at', 'N/A')}\n\n"
            f"₿ <b>BTC адрес:</b>\n<code>{order.get('btc_address', 'N/A')}</code>\n\n"
            f"💳 <b>Реквизиты:</b>\n{order.get('requisites', 'N/A')}"
        )
        await callback.answer()
        await callback.bot.send_message(
            callback.message.chat.id,
            text,
            parse_mode="HTML"
        )
        logger.info(f"Оператор {callback.from_user.id} получил детали заявки #{display_id}")
    except Exception as e:
        logger.error(f"Ошибка при получении деталей заявки: {e}")
        await callback.answer("❌ Ошибка получения деталей")

@router.callback_query(F.data.startswith("op_cancel_"))
async def operator_cancel_handler(callback: CallbackQuery):
    if not can_handle_orders(callback.from_user.id, callback.message.chat.id):
        await callback.answer("❌ У вас нет прав для этого действия", show_alert=True)
        logger.warning(f"Пользователь {callback.from_user.id} пытался отменить заявку без прав")
        return
    order_id = int(callback.data.split("_")[-1])
    try:
        await db.update_order(order_id, status='cancelled')
        order = await db.get_order(order_id)
        if order:
            await notify_client_order_cancelled(callback.bot, order)
        display_id = order.get('personal_id', order_id) if order else order_id
        await callback.message.edit_text(
            f"❌ <b>ЗАЯВКА ОТМЕНЕНА</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Отменил: @{callback.from_user.username or callback.from_user.first_name}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"📨 Клиент уведомлен",
            parse_mode="HTML"
        )
        await callback.answer("❌ Заявка отменена")
        logger.info(f"Заявка #{display_id} отменена оператором {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка в обработчике отмены заявки: {e}")
        await callback.answer("❌ Ошибка отмены заявки")

@router.message(OperatorStates.waiting_for_note)
async def note_input_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get('note_order_id')
    note_user_id = data.get('note_user_id')
    if note_user_id != message.from_user.id or not can_handle_orders(message.from_user.id, message.chat.id):
        logger.warning(f"Пользователь {message.from_user.id} пытался добавить заметку неавторизованным или в чужом чате")
        return
    if not order_id:
        await message.answer("Ошибка: ID заявки не найден")
        logger.error("Заметка: ID заявки не найден при вводе заметки")
        await state.clear()
        return
    note_text = message.text
    try:
        order = await db.get_order(order_id)
        display_id = order.get('personal_id', order_id) if order else order_id
        admin_text = (
            f"📝 <b>ЗАМЕТКА К ЗАЯВКЕ</b>\n\n"
            f"🆔 Заявка: #{display_id}\n"
            f"👤 Оператор: @{message.from_user.username or message.from_user.first_name}\n"
            f"📝 Заметка: {note_text}\n"
            f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        await message.bot.send_message(
            config.ADMIN_CHAT_ID,
            admin_text,
            parse_mode="HTML"
        )
        try:
            await db.update_order(order_id, operator_notes=note_text)
        except Exception as exc:
            logger.warning(f"Не удалось сохранить заметку в БД для заявки #{display_id}: {exc}")
        await message.answer(
            f"✅ Заметка к заявке #{display_id} добавлена!",
            parse_mode="HTML"
        )
        try:
            await message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение с заметкой оператора: {e}")
        logger.info(f"Оператор {message.from_user.id} добавил заметку к заявке #{display_id}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении заметки: {e}")
        await message.answer("❌ Ошибка сохранения заметки")
    await state.clear()

async def add_operator(user_id: int) -> bool:
    if user_id not in OPERATORS:
        OPERATORS.append(user_id)
        logger.info(f"Добавлен оператор: {user_id}")
        return True
    return False

async def remove_operator(user_id: int) -> bool:
    if user_id in OPERATORS:
        OPERATORS.remove(user_id)
        logger.info(f"Удалён оператор: {user_id}")
        return True
    return False

def get_operators_list() -> list:
    return OPERATORS.copy()




