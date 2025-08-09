import logging
from datetime import datetime, timedelta
import aiosqlite
import os
import psutil
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ChatType
from database.models import Database
from keyboards.reply import ReplyKeyboards
from config import config
from api.pspware_api import PSPWareAPI
from helpers import get_mirror_config, get_config_value, is_admin
import json




import platform

def format_size(bytes_size):
                                                        
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"

logger = logging.getLogger(__name__)
router = Router()
db = Database(config.DATABASE_URL)
pspware_api = PSPWareAPI()

class AdminStates(StatesGroup):
    admin_mode = State()
    waiting_for_welcome_message = State()
    waiting_for_percentage = State()
    waiting_for_broadcast_message = State()
    waiting_for_limits = State()
    waiting_for_user_id = State()
    waiting_for_message_to_user = State()
    waiting_for_block_reason = State()
    waiting_for_order_id = State()

class MirrorStates(StatesGroup):
    waiting_for_mirror_name = State()
    waiting_for_mirror_token = State()
    waiting_for_mirror_config = State()
    waiting_for_mirror_id = State()

def normalize_bool(value):
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes', 'on', 'enabled')
    return bool(value) if value is not None else False

async def is_admin_extended(user_id: int) -> bool:
    if user_id == config.ADMIN_USER_ID:
        return True
    try:
        admin_users = await db.get_setting("admin_users", [])
        return user_id in admin_users
    except:
        return False

async def is_operator_extended(user_id: int) -> bool:
    if user_id == config.ADMIN_USER_ID:
        return True
    try:
        admin_users = await db.get_setting("admin_users", [])
        operator_users = await db.get_setting("operator_users", [])
        return user_id in admin_users or user_id in operator_users
    except:
        return False

async def is_admin_in_chat(user_id: int, chat_id: int) -> bool:
    if user_id == config.ADMIN_USER_ID:
        return True
    admin_chats = [config.ADMIN_CHAT_ID, config.OPERATOR_CHAT_ID]
    admin_chats_setting = await db.get_setting("admin_chats", [])
    admin_chats.extend(admin_chats_setting)
    if chat_id not in admin_chats:
        return False
    admin_users = await db.get_setting("admin_users", [])
    operator_users = await db.get_setting("operator_users", [])
    return user_id in admin_users or user_id in operator_users

def create_main_admin_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Заявки", callback_data="admin_orders_menu"),
        InlineKeyboardButton(text="💰 Баланс", callback_data="admin_balance")
    )
    builder.row(
        InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users_menu"),
        InlineKeyboardButton(text="🔧 Персонал", callback_data="admin_staff_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast_menu"),
        InlineKeyboardButton(text="🛠 Система", callback_data="admin_system_menu")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Оборот зеркал", callback_data="view_turnover"),
        InlineKeyboardButton(text="🪞 Зеркала", callback_data="admin_mirrors_menu")                
    )
    return builder

def create_settings_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💸 Изменить комиссию", callback_data="admin_change_percentage"),
        InlineKeyboardButton(text="🤖 Капча", callback_data="admin_toggle_captcha")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Лимиты сумм", callback_data="admin_change_limits"),
        InlineKeyboardButton(text="📝 Приветствие", callback_data="admin_change_welcome")
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main_panel")
    )
    return builder

def create_users_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="admin_find_user"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_user_stats")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Последние", callback_data="admin_recent_users"),
        InlineKeyboardButton(text="💬 Написать", callback_data="admin_message_user")
    )
    builder.row(
        InlineKeyboardButton(text="🚫 Заблокировать", callback_data="admin_block_user"),
        InlineKeyboardButton(text="✅ Разблокировать", callback_data="admin_unblock_user")
    )
    builder.row(
        InlineKeyboardButton(text="◶️ Назад", callback_data="admin_main_panel")
    )
    return builder

def create_staff_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add_admin"),
        InlineKeyboardButton(text="➖ Убрать админа", callback_data="admin_remove_admin")
    )
    builder.row(
        InlineKeyboardButton(text="🔧 Добавить оператора", callback_data="admin_add_operator"),
        InlineKeyboardButton(text="❌ Убрать оператора", callback_data="admin_remove_operator")
    )
    builder.row(
        InlineKeyboardButton(text="📋 Список персонала", callback_data="admin_staff_list")
    )
    builder.row(
        InlineKeyboardButton(text="◶️ Назад", callback_data="admin_main_panel")
    )
    return builder

def create_orders_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Последние заявки", callback_data="admin_recent_orders"),
        InlineKeyboardButton(text="⏳ Ожидающие", callback_data="admin_pending_orders")
    )
    builder.row(
        InlineKeyboardButton(text="✅ Завершенные", callback_data="admin_completed_orders"),
        InlineKeyboardButton(text="❌ Отмененные", callback_data="admin_cancelled_orders")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Найти заявку", callback_data="admin_find_order"),
        InlineKeyboardButton(text="⚠️ Проблемные", callback_data="admin_problem_orders")
    )
    builder.row(
        InlineKeyboardButton(text="◶️ Назад", callback_data="admin_main_panel")
    )
    return builder

def create_system_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Системная информация", callback_data="admin_system_info"),
        InlineKeyboardButton(text="📋 Логи", callback_data="admin_view_logs")
    )
    builder.row(
        InlineKeyboardButton(text="🧹 Очистить БД", callback_data="admin_cleanup_db")
    )
    builder.row(
        InlineKeyboardButton(text="◶️ Назад", callback_data="admin_main_panel")
    )
    return builder

def create_broadcast_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 Отправить всем", callback_data="admin_broadcast_all"),
        InlineKeyboardButton(text="👥 Активным", callback_data="admin_broadcast_active")
    )
    builder.row(
        InlineKeyboardButton(text="🆕 Новым (за неделю)", callback_data="admin_broadcast_new"),
        InlineKeyboardButton(text="🎯 С операциями", callback_data="admin_broadcast_traders")
    )
    builder.row(
        InlineKeyboardButton(text="◶️ Назад", callback_data="admin_main_panel")
    )
    return builder

def create_mirror_management_panel():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Статистика зеркал", callback_data="admin_mirrors_stats"),
        InlineKeyboardButton(text="📋 Список зеркал", callback_data="admin_mirrors_list")
    )
    builder.row(
        InlineKeyboardButton(text="➕ Создать зеркало", callback_data="admin_mirrors_create"),
        InlineKeyboardButton(text="⚙️ Настройки зеркал", callback_data="admin_mirrors_settings")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить токены", callback_data="admin_mirrors_update"),
        InlineKeyboardButton(text="🗑️ Удалить зеркало", callback_data="admin_mirrors_delete")
    )
    builder.row(
        InlineKeyboardButton(text="📝 Сообщения", callback_data="admin_messages_menu"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main_panel")
    )
    return builder

@router.callback_query(F.data == "admin_messages_menu")
async def admin_messages_menu_handler(callback: CallbackQuery):
    if not await is_admin_extended(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    text = "📝 <b>Управление сообщениями</b>\n\nВыберите действие:"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Изменить приветствие", callback_data="admin_messages_welcome"))
    builder.row(InlineKeyboardButton(text="📋 Просмотр текущих", callback_data="admin_messages_view"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_menu"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_messages"))
async def admin_messages_handler(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_extended(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    action = callback.data.split("_")[-1]
    
    if action == "welcome":
        mirrors_info = "🔧 <b>Изменение приветственного сообщения</b>\n\n"
        mirrors_info += "📱 <b>Основной бот:</b>\n"
        main_config = config.get_mirror_config("main")
        current_welcome = main_config.get('WELCOME_MESSAGE', 'Не задано')
        if len(str(current_welcome)) > 100:
            current_welcome = current_welcome[:100] + "..."
        mirrors_info += f"Текущее: {current_welcome}\n\n"
        
        if config.MIRROR_BOT_TOKENS:
            for i in range(len(config.MIRROR_BOT_TOKENS)):
                mirror_id = f"mirror_{i+1}"
                mirror_config = config.get_mirror_config(mirror_id)
                current_welcome = mirror_config.get('WELCOME_MESSAGE', 'Использует основное')
                if len(str(current_welcome)) > 100:
                    current_welcome = current_welcome[:100] + "..."
                mirrors_info += f"🪞 <b>Зеркало {i+1}:</b>\n"
                mirrors_info += f"Текущее: {current_welcome}\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="✏️ Основной бот", callback_data="admin_edit_welcome_main"))
        
        for i in range(len(config.MIRROR_BOT_TOKENS)):
            builder.row(InlineKeyboardButton(text=f"✏️ Зеркало {i+1}", callback_data=f"admin_edit_welcome_mirror_{i+1}"))
        
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_messages_menu"))
        
        await callback.message.edit_text(mirrors_info, reply_markup=builder.as_markup(), parse_mode="HTML")
    
    elif action == "view":
        text = "📋 <b>Текущие приветственные сообщения:</b>\n\n"
        
        
        main_config = config.get_mirror_config("main")
        text += f"📱 <b>Основной бот:</b>\n{main_config.get('WELCOME_MESSAGE', 'Не задано')}\n\n"
        
        
        for i in range(len(config.MIRROR_BOT_TOKENS)):
            mirror_id = f"mirror_{i+1}"
            mirror_config = config.get_mirror_config(mirror_id)
            text += f"🪞 <b>Зеркало {i+1}:</b>\n{mirror_config.get('WELCOME_MESSAGE', 'Использует основное')}\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_messages_menu"))
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("admin_edit_welcome"))
async def admin_edit_welcome_handler(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_extended(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    parts = callback.data.split("_")
    mirror_type = parts[3]                   
    mirror_num = parts[4] if len(parts) > 4 else None
    
    if mirror_type == "main":
        mirror_id = "main"
        bot_name = "Основной бот"
    else:
        mirror_id = f"mirror_{mirror_num}"
        bot_name = f"Зеркало {mirror_num}"
    
    await state.update_data(editing_welcome=mirror_id)
    await state.set_state(AdminStates.waiting_for_welcome_message)
    
    current_message = config.get_config_value(mirror_id, 'WELCOME_MESSAGE', '')
    
    text = (f"✏️ <b>Редактирование приветствия - {bot_name}</b>\n\n"
            f"<b>Текущее сообщение:</b>\n{current_message}\n\n"
            f"<b>Доступные переменные:</b>\n"
            f"• <code>{{exchange_name}}</code> - название обменника\n"
            f"• <code>{{support_manager}}</code> - менеджер поддержки\n"
            f"• <code>{{news_channel}}</code> - канал новостей\n"
            f"• <code>{{support_chat}}</code> - чат поддержки\n"
            f"• <code>{{reviews_channel}}</code> - канал отзывов\n\n"
            f"Отправьте новое приветственное сообщение:")
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_messages_welcome"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(AdminStates.waiting_for_welcome_message)
async def process_welcome_message(message: Message, state: FSMContext):
    if not await is_admin_extended(message.from_user.id):
        return
    
    data = await state.get_data()
    mirror_id = data.get('editing_welcome')
    new_message = message.text.strip()
    
    
    await db.save_config_value(mirror_id, 'WELCOME_MESSAGE', new_message)
    
    
    if mirror_id == "main":
        config.WELCOME_MESSAGE = new_message
    else:
        if mirror_id not in config.MIRROR_CONFIGS:
            config.MIRROR_CONFIGS[mirror_id] = {}
        config.MIRROR_CONFIGS[mirror_id]['WELCOME_MESSAGE'] = new_message
    
    await state.clear()
    
    bot_name = "Основной бот" if mirror_id == "main" else f"Зеркало {mirror_id.split('_')[1]}"
    
    await message.answer(
        f"✅ <b>Приветственное сообщение для {bot_name} обновлено!</b>\n\n"
        f"<b>Новое сообщение:</b>\n{new_message}",
        reply_markup=create_main_admin_panel().as_markup(),
        parse_mode="HTML"
    )

@router.message(Command("admin"))
async def admin_panel_handler(message: Message, state: FSMContext):
    if not await is_admin_in_chat(message.from_user.id, message.chat.id):
        await message.answer("❌ У вас нет прав администратора")
        return
    
    await state.clear()
    
    if message.chat.type == ChatType.PRIVATE:
        await state.set_state(AdminStates.admin_mode)
        await message.answer(
            "👑 <b>Панель администратора</b>\n\nВыберите раздел для управления:",
            reply_markup=ReplyKeyboards.admin_menu(),
            parse_mode="HTML"
        )
    else:
        builder = create_main_admin_panel()
        await message.answer(
            f"👑 <b>Панель администратора</b>\n"
            f"Чат: {message.chat.title}\n"
            f"Администратор: {message.from_user.first_name}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("admin_"))
async def admin_callback_handler(callback: CallbackQuery, state: FSMContext):
    if not await is_admin_in_chat(callback.from_user.id, callback.message.chat.id):
        await callback.answer("❌ У вас нет прав", show_alert=True)
        return
    
    action = callback.data.replace("admin_", "")
    
    try:
        if action == "main_panel":
            builder = create_main_admin_panel()
            text = (
                f"👑 <b>Панель администратора</b>\n"
                f"Администратор: {callback.from_user.first_name}"
            )
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

        elif action == "stats":
            stats = await db.get_statistics()
            health_response = await pspware_api.health_check()
            if health_response.get("success"):
                service_status = health_response["data"]["status"]
            else:
                service_status = f"Ошибка: {health_response.get('error', 'Неизвестная ошибка')}"
                if "status_code" in health_response:
                    service_status += f" (Код: {health_response['status_code']})"
            text = (
                f"📊 <b>Статистика системы</b>\n\n"
                f"👥 Пользователей: {stats['total_users']}\n"
                f"📋 Заявок: {stats['total_orders']}\n"
                f"✅ Завершено: {stats['completed_orders']}\n"
                f"💰 Оборот: {stats['total_volume']:,.0f} ₽\n\n"
                f"📈 Процент завершения: {stats['completion_rate']:.1f}%\n"
                f"📅 Сегодня заявок: {stats['today_orders']}\n"
                f"💵 Сегодня оборот: {stats['today_volume']:,.0f} ₽\n\n"
                f"🔧 Состояние сервиса PSPWare: {service_status}"
            )
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats"),
                InlineKeyboardButton(text="◶️ Назад", callback_data="admin_main_panel")
            )
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

        elif action == "balance":
            try:
                if not hasattr(config, 'ONLYPAYS_PAYMENT_KEY') or not config.ONLYPAYS_PAYMENT_KEY:
                    text = "❌ <b>Ошибка получения баланса</b>\n\nPayment Key не настроен"
                else:
                    from handlers.user import onlypays_api
                    balance_response = await onlypays_api.get_balance()
                    if balance_response.get('success'):
                        balance = balance_response.get('balance', 0)
                        text = f"💰 <b>Баланс процессинга</b>\n\n💳 Доступно: {balance:,.2f} ₽"
                    else:
                        error_msg = balance_response.get('error', 'Неизвестная ошибка')
                        text = f"❌ Ошибка получения баланса:\n{error_msg}"
            except Exception as e:
                text = f"❌ Ошибка получения баланса:\n{e}"
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_balance"),
                InlineKeyboardButton(text="◶️ Назад", callback_data="admin_main_panel")
            )
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

        elif action.startswith("view_turnover"):
            try:
                                                 
                all_mirrors_stats = await db.get_all_mirrors_turnover()
                
                text = "📊 <b>Оборот по зеркалам</b>\n\n"
                
                if not all_mirrors_stats:
                    text += "❌ Нет данных по оборотам"
                else:
                    total_global = 0
                    for mirror_stat in all_mirrors_stats:
                        mirror_id = mirror_stat['mirror_id']
                        amount = mirror_stat['total'] 
                        orders = mirror_stat['orders']
                        total_global += amount
                        
                        text += f"🪞 <b>{mirror_id}</b>:\n"
                        text += f"💰 {amount:,.0f} ₽ ({orders} заявок)\n\n"
                    
                    text += f"💎 <b>Общий оборот:</b> {total_global:,.0f} ₽"
                
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="🔄 Обновить", callback_data="view_turnover"),
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main_panel")
                )
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "settings":
            commission_percentage = await db.get_setting("commission_percentage", float(os.getenv('COMMISSION_PERCENT', '20.0')))
            captcha_status = normalize_bool(await db.get_setting("captcha_enabled", config.CAPTCHA_ENABLED))
            min_amount = await db.get_setting("min_amount", config.MIN_AMOUNT)
            max_amount = await db.get_setting("max_amount", config.MAX_AMOUNT)
            
            status_text = "✅ Включена" if captcha_status else "❌ Отключена"
            
            text = (
                f"⚙️ <b>Настройки системы</b>\n\n"
                f"💸 Комиссия сервиса: {commission_percentage}%\n"
                f"🤖 Капча: {status_text}\n"
                f"💰 Лимиты: {min_amount:,} - {max_amount:,} ₽"
            )
            await callback.message.edit_text(text, reply_markup=create_settings_panel().as_markup(), parse_mode="HTML")

        elif action == "users_menu":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('SELECT COUNT(*) FROM users') as cursor:
                        total_users = (await cursor.fetchone())[0]
                    async with database.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1') as cursor:
                        blocked_users = (await cursor.fetchone())[0]
                    async with database.execute('SELECT COUNT(*) FROM users WHERE total_operations > 0') as cursor:
                        active_users = (await cursor.fetchone())[0]
                
                text = (
                    f"👥 <b>Управление пользователями</b>\n\n"
                    f"📊 Всего: {total_users}\n"
                    f"⚡ Активных: {active_users}\n"
                    f"🚫 Заблокированных: {blocked_users}"
                )
            except:
                text = "👥 <b>Управление пользователями</b>\n\n❌ Ошибка загрузки статистики"
            
            await callback.message.edit_text(text, reply_markup=create_users_panel().as_markup(), parse_mode="HTML")

        elif action == "staff_menu":
            admin_users = await db.get_setting("admin_users", [])
            operator_users = await db.get_setting("operator_users", [])
            
            try:
                from handlers.operator import get_operators_list
                operator_file_list = get_operators_list()
            except:
                operator_file_list = []
            
            text = (
                f"🔧 <b>Персонал системы</b>\n\n"
                f"👑 Администраторов: {len(admin_users) + 1}\n"
                f"🔧 Операторов (БД): {len(operator_users)}\n"
                f"🔧 Операторов (файл): {len(operator_file_list)}"
            )
            await callback.message.edit_text(text, reply_markup=create_staff_panel().as_markup(), parse_mode="HTML")

        elif action == "orders_menu":
            stats = await db.get_statistics()
            text = (
                f"📋 <b>Управление заявками</b>\n\n"
                f"📊 Всего: {stats['total_orders']}\n"
                f"✅ Завершено: {stats['completed_orders']}\n"
                f"⏳ В ожидании: {stats['total_orders'] - stats['completed_orders']}\n"
                f"💰 Общий оборот: {stats['total_volume']:,.0f} ₽"
            )
            await callback.message.edit_text(text, reply_markup=create_orders_panel().as_markup(), parse_mode="HTML")

        elif action == "broadcast_menu":
            text = "📢 <b>Рассылка сообщений</b>\n\nВыберите тип рассылки:"
            await callback.message.edit_text(text, reply_markup=create_broadcast_panel().as_markup(), parse_mode="HTML")

        elif action == "system_menu":
            text = "🛠 <b>Системные функции</b>\n\nВыберите действие:"
            await callback.message.edit_text(text, reply_markup=create_system_panel().as_markup(), parse_mode="HTML")

        elif action == "system_info":
            try:
                                            
                process = psutil.Process(os.getpid())
                mem_info = process.memory_info()
                cpu_usage_proc = process.cpu_percent(interval=0.5)

                
                cpu_usage_sys = psutil.cpu_percent(interval=0.5)
                ram = psutil.virtual_memory()
                uptime_seconds = (datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()
                uptime = str(timedelta(seconds=int(uptime_seconds)))

                
                db_size = 0
                if hasattr(db, "db_path") and db.db_path and os.path.exists(db.db_path):
                    db_size = os.path.getsize(db.db_path)

                text = (
                    f"📊 <b>Системная информация</b>\n\n"
                    f"🌐 ОС: {platform.system()} {platform.release()} ({platform.machine()})\n"
                    f"🕐 Аптайм системы: {uptime}\n\n"
                    f"🖥 CPU процесса: {cpu_usage_proc:.1f}%\n"
                    f"🖥 CPU системы: {cpu_usage_sys:.1f}%\n"
                    f"💾 Память процесса: {format_size(mem_info.rss)}\n"
                    f"💾 Используется ОЗУ: {ram.percent}% из {format_size(ram.total)}\n"
                    f"📂 Размер БД: {format_size(db_size)}\n\n"
                    f"🕐 Время сервера: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
                )

                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_system_info"),
                    InlineKeyboardButton(text="◶️ Назад", callback_data="admin_system_menu")
                )
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "view_logs":
            try:
                log_files = []
                for file in os.listdir('.'):
                    if file.endswith('.log'):
                        log_files.append(file)
                
                if log_files:
                    text = "📋 <b>Доступные лог-файлы:</b>\n\n"
                    for log_file in log_files:
                        size = os.path.getsize(log_file) / 1024
                        text += f"📄 {log_file} ({size:.1f} KB)\n"
                    text += "\n💡 Используйте команду /get_log filename для просмотра"
                else:
                    text = "📋 <b>Логи</b>\n\n❌ Лог-файлы не найдены"
                
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_system_menu"))
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "mirrors_menu":
            builder = create_mirror_management_panel()
            text = "🪞 <b>Управление зеркалами</b>\n\nВыберите действие:"
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

        elif action == "mirrors_stats":
            try:
                all_mirrors_stats = await db.get_all_mirrors_turnover()
                
                text = "📊 <b>Статистика по зеркалам:</b>\n\n"
                
                if not all_mirrors_stats:
                    text += "❌ Нет данных по оборотам зеркал"
                else:
                    total_amount = 0
                    total_orders = 0
                    
                    for mirror_stat in all_mirrors_stats:
                        mirror_id = mirror_stat['mirror_id']
                        amount = mirror_stat['total']
                        orders = mirror_stat['orders']
                        
                        total_amount += amount
                        total_orders += orders
                        
                        text += f"🪞 <b>{mirror_id}</b>:\n"
                        text += f"  💰 Оборот: {amount:,.0f} ₽\n"
                        text += f"  📋 Заявок: {orders}\n\n"
                    
                    text += f"📈 <b>Общий оборот:</b> {total_amount:,.0f} ₽\n"
                    text += f"📊 <b>Всего заявок:</b> {total_orders}"
                
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_mirrors_stats"),
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_menu")
                )
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "mirrors_list":
            try:
                text = "📋 <b>Список зеркал:</b>\n\n"
                
                
                text += f"🔹 <b>main (основной)</b>:\n"
                text += f"  📱 @{config.BOT_USERNAME}\n"
                text += f"  🏢 {config.EXCHANGE_NAME}\n"
                text += f"  👨‍💼 {config.SUPPORT_MANAGER}\n\n"
                
                
                if config.MIRROR_BOT_TOKENS:
                    for i, token in enumerate(config.MIRROR_BOT_TOKENS):
                        mirror_id = f"mirror_{i+1}"
                        mirror_config = config.get_mirror_config(mirror_id)
                        
                        text += f"🔹 <b>{mirror_id}</b>:\n"
                        text += f"  📱 @{mirror_config.get('BOT_USERNAME', 'Не настроен')}\n"
                        text += f"  🏢 {mirror_config.get('EXCHANGE_NAME', 'Не настроен')}\n"
                        text += f"  👨‍💼 {mirror_config.get('SUPPORT_MANAGER', 'Не настроен')}\n\n"
                else:
                    text += "❌ Зеркальные боты не настроены"
                
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_menu"))
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
     
        elif action == "mirrors_create":
            text = (
                "🔧 <b>Создаём новое зеркало</b>\n\n"
                "1️⃣ Создай нового бота через @BotFather.\n"
                "   Отправь команду <code>/newbot</code> и следуй инструкциям.\n\n"
                "2️⃣ Скопируй токен бота.\n\n"
                "3️⃣ Добавь его в переменные окружения:\n"
                "   <code>MIRROR_BOT_TOKENS=токен1,токен2,новый_токен</code>\n\n"
                "4️⃣ В файле <code>.env</code> пропиши данные зеркала:\n"
                "   <code>MIRROR_X_BOT_USERNAME=имя_бота</code>\n"
                "   <code>MIRROR_X_EXCHANGE_NAME=название</code>\n"
                "   <code>MIRROR_X_SUPPORT_MANAGER=@поддержка</code>\n"
                "   <code>MIRROR_X_NEWS_CHANNEL=@канал</code>\n"
                "   X — это номер зеркала (например, 3).\n\n"
                "5️⃣ Перезапусти бота.\n\n"
                "📝 Пример для зеркала №3:\n"
                "   <code>MIRROR_3_BOT_USERNAME=MyExchanger3_bot</code>\n"
                "   <code>MIRROR_3_EXCHANGE_NAME=My Exchanger 3</code>\n"
                "   <code>MIRROR_3_SUPPORT_MANAGER=@support3</code>\n"
                "   <code>MIRROR_3_NEWS_CHANNEL=@news3</code>\n"
            )

            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="📋 Проверить конфигурацию", callback_data="admin_mirrors_check"))
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_menu"))
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

        elif action == "mirrors_check":
            try:
                text = "🔍 <b>Проверка конфигурации зеркал:</b>\n\n"
                
                
                text += f"🔹 <b>Основной бот:</b>\n"
                text += f"  {'✅' if config.BOT_TOKEN else '❌'} Токен: {'Настроен' if config.BOT_TOKEN else 'Не настроен'}\n"
                text += f"  ✅ Username: {config.BOT_USERNAME}\n\n"
                
                
                if config.MIRROR_BOT_TOKENS:
                    text += f"🪞 <b>Зеркальные боты:</b> {len(config.MIRROR_BOT_TOKENS)}\n\n"
                    
                    for i, token in enumerate(config.MIRROR_BOT_TOKENS):
                        mirror_id = f"mirror_{i+1}"
                        mirror_config = config.get_mirror_config(mirror_id)
                        
                        text += f"🔹 <b>Зеркало #{i+1}:</b>\n"
                        text += f"  {'✅' if token else '❌'} Токен: {'Настроен' if token else 'Не настроен'}\n"
                        text += f"  {'✅' if mirror_config.get('BOT_USERNAME') else '❌'} Username: {mirror_config.get('BOT_USERNAME', 'Не настроен')}\n"
                        text += f"  {'✅' if mirror_config.get('EXCHANGE_NAME') else '❌'} Название: {mirror_config.get('EXCHANGE_NAME', 'Не настроено')}\n\n"
                else:
                    text += "❌ <b>Зеркальные боты не настроены</b>\n"
                    text += "Добавьте MIRROR_BOT_TOKENS в .env файл"
                
                builder = InlineKeyboardBuilder()
                builder.row(
                    InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_mirrors_check"),
                    InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_create")
                )
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "mirrors_settings":
            text = (
                "⚙️ <b>Настройки зеркал</b>\n\n"
                "Используй эти переменные в файле <code>.env</code>, чтобы настроить зеркало X.\n\n"

                "🔧 <b>Основные параметры:</b>\n"
                "• <code>MIRROR_X_BOT_USERNAME</code> — имя бота\n"
                "• <code>MIRROR_X_EXCHANGE_NAME</code> — название обменника\n"
                "• <code>MIRROR_X_SUPPORT_CHAT</code> — чат поддержки\n"
                "• <code>MIRROR_X_SUPPORT_MANAGER</code> — менеджер поддержки\n"
                "• <code>MIRROR_X_NEWS_CHANNEL</code> — канал новостей\n"
                "• <code>MIRROR_X_REVIEWS_CHANNEL</code> — канал отзывов\n\n"

                "🆔 <b>ID чатов:</b>\n"
                "• <code>MIRROR_X_ADMIN_USER_ID</code> — ID администратора\n"
                "• <code>MIRROR_X_ADMIN_CHAT_ID</code> — ID админ-чата\n"
                "• <code>MIRROR_X_OPERATOR_CHAT_ID</code> — ID чата операторов\n"
                "• <code>MIRROR_X_REVIEWS_CHANNEL_ID</code> — ID канала отзывов\n\n"

                "💡 Если параметр не указан — используется значение из основного бота.\n"
            )

            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_menu"))
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    
        elif action == "mirrors_update":
            text = (
                "🔄 <b>Обновление токенов зеркал</b>\n\n"
                "1️⃣ Останови бота.\n"
                "2️⃣ В файле <code>.env</code> измени строку:\n"
                "   <code>MIRROR_BOT_TOKENS=токен1,токен2,токен3</code>\n"
                "   (пиши токены через запятую, без пробелов)\n"
                "3️⃣ Запусти бота снова.\n\n"
                "⚠️ <b>Важно:</b>\n"
                "• Разделяй токены только запятой\n"
                "• Без пробелов между токенами\n"
                "• Каждый токен должен быть рабочим\n"
                "• После изменения нужен перезапуск\n\n"
                f"📝 <b>Текущие токены:</b> {len(config.MIRROR_BOT_TOKENS) if config.MIRROR_BOT_TOKENS else 0}\n"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_menu"))
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

        elif action == "mirrors_delete":
            text = (
                "🗑️ <b>Удаление зеркала</b>\n\n"
                "1️⃣ Останови всех ботов.\n"
                "2️⃣ Удали токен зеркала из <code>MIRROR_BOT_TOKENS</code> в .env.\n"
                "3️⃣ Убери параметры зеркала:\n"
                "   - <code>MIRROR_X_BOT_USERNAME</code>\n"
                "   - <code>MIRROR_X_EXCHANGE_NAME</code>\n"
                "   - и другие связанные переменные\n"
                "4️⃣ Запусти бота заново.\n\n"
                "⚠️ <b>Важно:</b>\n"
                "• Данные пользователей этого зеркала сохранятся в базе.\n"
                "• Все заявки тоже сохранятся.\n"
                "• Перед удалением желательно сделать бэкап.\n\n"
                "❗ <i>После удаления вернуть зеркало можно только через повторную настройку.</i>\n"
            )

            
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_mirrors_menu"))
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

        elif action == "cleanup_db":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    await database.execute('DELETE FROM orders WHERE status = "cancelled" AND created_at < datetime("now", "-30 days")')
                    await database.execute('DELETE FROM captcha_sessions WHERE created_at < datetime("now", "-1 day")')
                    await database.execute('VACUUM')
                    await database.commit()
                
                await callback.answer("✅ База данных очищена", show_alert=True)
                await admin_callback_handler(callback.model_copy(update={"data": "admin_system_menu"}), state)
            except Exception as e:
                await callback.answer(f"❌ Ошибка очистки БД: {e}", show_alert=True)

        elif action == "recent_orders":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('''
                        SELECT id, user_id, total_amount, status, created_at, personal_id
                        FROM orders ORDER BY created_at DESC LIMIT 10
                    ''') as cursor:
                        orders = await cursor.fetchall()
                
                status_emoji_map = {
                    "waiting": "⏳",
                    "paid_by_client": "💰",
                    "completed": "✅",
                    "cancelled": "❌",
                    "problem": "⚠️"
                }

                if orders:
                    text = "📋 <b>Последние 10 заявок:</b>\n\n"
                    for order in orders:
                        order_id, user_id, amount, status, created_at, personal_id = order
                        emoji = status_emoji_map.get(status, "❓")
                        display_id = personal_id or order_id
                        text += f"{emoji} #{display_id} | {amount:,.0f}₽ | {user_id}\n{created_at[:16]}\n\n"
                else:
                    text = "📋 <b>Заявки</b>\n\n❌ Заявки не найдены"
                
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_orders_menu"))
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "pending_orders":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('''
                        SELECT id, user_id, total_amount, created_at, personal_id
                        FROM orders WHERE status IN ("waiting", "paid_by_client") ORDER BY created_at DESC
                    ''') as cursor:
                        orders = await cursor.fetchall()
                
                if orders:
                    text = f"⏳ <b>Ожидающие заявки ({len(orders)}):</b>\n\n"
                    for order in orders[:10]:
                        order_id, user_id, amount, created_at, personal_id = order
                        display_id = personal_id or order_id
                        text += f"📋 #{display_id} | {amount:,.0f}₽ | {user_id}\n{created_at[:16]}\n\n"
                    
                    if len(orders) > 10:
                        text += f"... и еще {len(orders) - 10} заявок"
                else:
                    text = "⏳ <b>Ожидающие заявки</b>\n\n✅ Нет ожидающих заявок"
                
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_orders_menu"))
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "completed_orders":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('''
                        SELECT id, user_id, total_amount, created_at, personal_id
                        FROM orders WHERE status = "completed" ORDER BY created_at DESC LIMIT 10
                    ''') as cursor:
                        orders = await cursor.fetchall()
                
                if orders:
                    text = "✅ <b>Завершенные заявки (последние 10):</b>\n\n"
                    for order in orders:
                        order_id, user_id, amount, created_at, personal_id = order
                        display_id = personal_id or order_id
                        text += f"✅ #{display_id} | {amount:,.0f}₽ | {user_id}\n{created_at[:16]}\n\n"
                else:
                    text = "✅ <b>Завершенные заявки</b>\n\n❌ Завершенных заявок нет"
                
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_orders_menu"))
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "cancelled_orders":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('''
                        SELECT id, user_id, total_amount, created_at, personal_id
                        FROM orders WHERE status = "cancelled" ORDER BY created_at DESC LIMIT 10
                    ''') as cursor:
                        orders = await cursor.fetchall()
                
                if orders:
                    text = "❌ <b>Отмененные заявки (последние 10):</b>\n\n"
                    for order in orders:
                        order_id, user_id, amount, created_at, personal_id = order
                        display_id = personal_id or order_id
                        text += f"❌ #{display_id} | {amount:,.0f}₽ | {user_id}\n{created_at[:16]}\n\n"
                else:
                    text = "❌ <b>Отмененные заявки</b>\n\n✅ Отмененных заявок нет"
                
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_orders_menu"))
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "problem_orders":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('''
                        SELECT id, user_id, total_amount, created_at, personal_id
                        FROM orders WHERE status = "problem" ORDER BY created_at DESC
                    ''') as cursor:
                        orders = await cursor.fetchall()
                
                if orders:
                    text = f"⚠️ <b>Проблемные заявки ({len(orders)}):</b>\n\n"
                    for order in orders:
                        order_id, user_id, amount, created_at, personal_id = order
                        display_id = personal_id or order_id
                        text += f"⚠️ #{display_id} | {amount:,.0f}₽ | {user_id}\n{created_at[:16]}\n\n"
                else:
                    text = "⚠️ <b>Проблемные заявки</b>\n\n✅ Проблемных заявок нет"
                
                builder = InlineKeyboardBuilder()
                builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_orders_menu"))
                await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "find_order":
            await callback.message.edit_text(
                "🔍 <b>Поиск заявки</b>\n\n"
                "Введите ID заявки:",
                parse_mode="HTML"
            )
            await state.update_data(action="find_order")
            await state.set_state(AdminStates.waiting_for_order_id)

        elif action == "broadcast_active":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('SELECT user_id FROM users WHERE total_operations > 0') as cursor:
                        users = [row[0] for row in await cursor.fetchall()]
                
                await callback.message.edit_text(
                    f"📤 <b>Рассылка активным пользователям</b>\n\n"
                    f"Найдено активных пользователей: {len(users)}\n\n"
                    "Отправьте сообщение для рассылки:",
                    parse_mode="HTML"
                )
                await state.update_data(action="broadcast_active", target_users=users)
                await state.set_state(AdminStates.waiting_for_broadcast_message)
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "broadcast_new":
            try:
                week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('SELECT user_id FROM users WHERE registration_date > ?', (week_ago,)) as cursor:
                        users = [row[0] for row in await cursor.fetchall()]
                
                await callback.message.edit_text(
                    f"📤 <b>Рассылка новым пользователям</b>\n\n"
                    f"Найдено новых пользователей (за неделю): {len(users)}\n\n"
                    "Отправьте сообщение для рассылки:",
                    parse_mode="HTML"
                )
                await state.update_data(action="broadcast_new", target_users=users)
                await state.set_state(AdminStates.waiting_for_broadcast_message)
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action == "broadcast_traders":
            try:
                async with aiosqlite.connect(db.db_path) as database:
                    async with database.execute('SELECT user_id FROM users WHERE total_operations >= 1') as cursor:
                        users = [row[0] for row in await cursor.fetchall()]
                
                await callback.message.edit_text(
                    f"📤 <b>Рассылка пользователям с операциями</b>\n\n"
                    f"Найдено пользователей с операциями: {len(users)}\n\n"
                    "Отправьте сообщение для рассылки:",
                    parse_mode="HTML"
                )
                await state.update_data(action="broadcast_traders", target_users=users)
                await state.set_state(AdminStates.waiting_for_broadcast_message)
            except Exception as e:
                await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

        elif action in ["toggle_captcha", "change_percentage", "change_limits", "change_welcome",
                        "find_user", "message_user", "block_user", "unblock_user",
                        "add_admin", "remove_admin", "add_operator", "remove_operator",
                        "staff_list", "broadcast_all", "user_stats", "recent_users",
                        "mirrors_stats", "mirrors_list", "mirrors_create", "mirrors_check",
                        "mirrors_settings", "mirrors_update", "mirrors_delete"]:

            await handle_settings_and_management(callback, state, action)

        else:
            await callback.answer("❌ Неизвестная команда", show_alert=True)
    
    except Exception as e:
        logger.error(f"Admin callback error: {e}")
        await callback.answer("❌ Произошла ошибка", show_alert=True)

async def handle_settings_and_management(callback: CallbackQuery, state: FSMContext, action: str):
    if action == "toggle_captcha":
        current_status = normalize_bool(await db.get_setting("captcha_enabled", config.CAPTCHA_ENABLED))
        new_status = not current_status
        await db.set_setting("captcha_enabled", new_status)
        status_text = "✅ Включена" if new_status else "❌ Отключена"
        await callback.answer(f"Капча: {status_text}")
        await admin_callback_handler(callback.model_copy(update={"data": "admin_settings"}), state)
    
    elif action == "change_percentage":
        commission_percentage = await db.get_setting("commission_percentage", float(os.getenv('COMMISSION_PERCENT', '20.0')))
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin_settings")
        )
        
        await callback.message.edit_text(
            f"💸 <b>Изменение комиссии сервиса</b>\n\n"
            f"📊 Текущая комиссия: <b>{commission_percentage}%</b>\n\n"
            f"Введите новую комиссию (от 0 до 50):\n"
            f"Например: 16.67",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.update_data(action="change_percentage")
        await state.set_state(AdminStates.waiting_for_percentage)
    
    elif action == "change_limits":
        min_amount = await db.get_setting("min_amount", config.MIN_AMOUNT)
        max_amount = await db.get_setting("max_amount", config.MAX_AMOUNT)
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin_settings")
        )
        
        await callback.message.edit_text(
            f"💰 <b>Изменение лимитов</b>\n\n"
            f"📊 Текущие лимиты: <b>{min_amount:,} - {max_amount:,} ₽</b>\n\n"
            f"Введите новые лимиты через пробел:\n"
            f"Например: 1000 500000",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.update_data(action="change_limits")
        await state.set_state(AdminStates.waiting_for_limits)
    
    elif action == "change_welcome":
        current_welcome = await db.get_setting("welcome_message", "Не установлено")
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin_settings")
        )
        
        await callback.message.edit_text(
            f"📝 <b>Изменение приветственного сообщения</b>\n\n"
            f"📊 Текущее сообщение:\n<i>{current_welcome[:200]}{'...' if len(current_welcome) > 200 else ''}</i>\n\n"
            f"Отправьте новое приветственное сообщение:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.update_data(action="change_welcome")
        await state.set_state(AdminStates.waiting_for_welcome_message)
    
    elif action in ["find_user", "message_user", "block_user", "unblock_user",
                    "add_admin", "remove_admin", "add_operator", "remove_operator"]:
        builder = InlineKeyboardBuilder()
        
        if action in ["find_user", "message_user", "block_user", "unblock_user"]:
            cancel_callback = "admin_users_menu"
        else:
            cancel_callback = "admin_staff_menu"
        
        builder.row(
            InlineKeyboardButton(text="❌ Отменить", callback_data=cancel_callback)
        )
        
        await callback.message.edit_text(
            f"👤 <b>{get_action_title(action)}</b>\n\n"
            f"Введите ID или @username пользователя:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.update_data(action=action)
        await state.set_state(AdminStates.waiting_for_user_id)
    
    elif action == "staff_list":
        await show_staff_list(callback)
    
    elif action == "broadcast_all":
        users = await db.get_all_users()
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="❌ Отменить", callback_data="admin_broadcast_menu")
        )
        
        await callback.message.edit_text(
            f"📤 <b>Рассылка всем пользователям</b>\n\n"
            f"Найдено пользователей: {len(users)}\n\n"
            f"Отправьте сообщение для рассылки:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.update_data(action="broadcast_all", target_users=users)
        await state.set_state(AdminStates.waiting_for_broadcast_message)
    
    elif action == "user_stats":
        await show_detailed_user_stats(callback)
    
    elif action == "recent_users":
        await show_recent_users(callback)

def get_action_title(action: str) -> str:
    titles = {
        "find_user": "Поиск пользователя",
        "message_user": "Отправка сообщения пользователю",
        "block_user": "Блокировка пользователя",
        "unblock_user": "Разблокировка пользователя",
        "add_admin": "Добавление администратора",
        "remove_admin": "Удаление администратора",
        "add_operator": "Добавление оператора",
        "remove_operator": "Удаление оператора"
    }
    return titles.get(action, action)

async def show_staff_list(callback: CallbackQuery):
    admin_users = await db.get_setting("admin_users", [])
    operator_users = await db.get_setting("operator_users", [])
    
    try:
        from handlers.operator import get_operators_list
        operator_file_list = get_operators_list()
    except:
        operator_file_list = []
    
    text = "👥 <b>Список персонала</b>\n\n"
    text += "👑 <b>Администраторы:</b>\n"
    text += f"• {config.ADMIN_USER_ID} (супер-админ)\n"
    for user_id in admin_users:
        text += f"• {user_id}\n"
    
    text += "\n🔧 <b>Операторы (БД):</b>\n"
    for user_id in operator_users:
        text += f"• {user_id}\n"
    
    text += "\n🔧 <b>Операторы (файл):</b>\n"
    for user_id in operator_file_list:
        text += f"• {user_id}\n"
    
    if not admin_users and not operator_users and not operator_file_list:
        text += "\nНет дополнительного персонала"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_staff_menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

async def show_detailed_user_stats(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(db.db_path) as database:
            async with database.execute('SELECT COUNT(*) FROM users') as cursor:
                total_users = (await cursor.fetchone())[0]
            async with database.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1') as cursor:
                blocked_users = (await cursor.fetchone())[0]
            async with database.execute('SELECT COUNT(*) FROM users WHERE DATE(registration_date) = DATE("now")') as cursor:
                today_registrations = (await cursor.fetchone())[0]
            async with database.execute('SELECT COUNT(*) FROM users WHERE total_operations > 0') as cursor:
                active_users = (await cursor.fetchone())[0]
            async with database.execute('SELECT COUNT(*) FROM users WHERE DATE(registration_date) >= DATE("now", "-7 days")') as cursor:
                week_registrations = (await cursor.fetchone())[0]
                
        activity_rate = (active_users/total_users*100) if total_users > 0 else 0
        
        text = (
            f"📊 <b>Детальная статистика пользователей</b>\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"🚫 Заблокированных: {blocked_users}\n"
            f"⚡ Активных: {active_users}\n"
            f"📅 Регистраций сегодня: {today_registrations}\n"
            f"📅 Регистраций за неделю: {week_registrations}\n"
            f"📈 Процент активности: {activity_rate:.1f}%"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_user_stats"),
            InlineKeyboardButton(text="◶️ Назад", callback_data="admin_users_menu")
        )
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

async def show_recent_users(callback: CallbackQuery):
    try:
        async with aiosqlite.connect(db.db_path) as database:
            async with database.execute('''
                SELECT user_id, username, first_name, registration_date, total_operations
                FROM users ORDER BY registration_date DESC LIMIT 10
            ''') as cursor:
                rows = await cursor.fetchall()
        
        if not rows:
            text = "❌ Пользователи не найдены"
        else:
            text = f"👥 <b>Последние 10 пользователей:</b>\n\n"
            for user_id, username, first_name, reg_date, operations in rows:
                text += f"🆔 {user_id} | @{username or 'нет'}\n{first_name} | {reg_date[:16]} | {operations or 0} операций\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="◶️ Назад", callback_data="admin_users_menu"))
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.message(AdminStates.waiting_for_percentage)
async def process_percentage_change(message: Message, state: FSMContext):
    try:
        percentage = float(message.text)
        if not 0 <= percentage <= 50:
            await message.answer("❌ Комиссия должна быть от 0 до 50")
            return
        
        await db.set_setting("commission_percentage", percentage)
        await message.answer(f"✅ Комиссия сервиса изменена на {percentage}%")
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректное число")

@router.message(AdminStates.waiting_for_limits)
async def process_limits_change(message: Message, state: FSMContext):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            await message.answer("❌ Введите два числа через пробел")
            return
        
        min_amount = int(parts[0])
        max_amount = int(parts[1])
        
        if min_amount >= max_amount or min_amount < 100:
            await message.answer("❌ Минимальная сумма должна быть меньше максимальной и больше 100")
            return
        
        await db.set_setting("min_amount", min_amount)
        await db.set_setting("max_amount", max_amount)
        await message.answer(f"✅ Лимиты изменены: {min_amount:,} - {max_amount:,} ₽")
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
    except ValueError:
        await message.answer("❌ Введите корректные числа")

@router.message(AdminStates.waiting_for_welcome_message)
async def process_welcome_change(message: Message, state: FSMContext):
    try:
        await db.set_setting("welcome_message", message.text)
        await message.answer("✅ Приветственное сообщение обновлено")
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(AdminStates.waiting_for_order_id)
async def process_order_search(message: Message, state: FSMContext):
    try:
        order_id = message.text.strip()
        
        async with aiosqlite.connect(db.db_path) as database:
            async with database.execute('''
                SELECT id, user_id, amount_rub, amount_btc, btc_address, total_amount, status, 
                       created_at, personal_id, payment_type, rate
                FROM orders 
                WHERE id = ? OR personal_id = ?
            ''', (order_id, order_id)) as cursor:
                order = await cursor.fetchone()
        
        if not order:
            await message.answer("❌ Заявка не найдена")
            return
        
        (internal_id, user_id, amount_rub, amount_btc, btc_address, total_amount, 
         status, created_at, personal_id, payment_type, rate) = order
        
        display_id = personal_id or internal_id
        status_text = {
            "waiting": "⏳ Ожидание",
            "paid_by_client": "💰 Оплачена клиентом",
            "completed": "✅ Завершена", 
            "cancelled": "❌ Отменена",
            "problem": "⚠️ Проблемная"
        }.get(status, status)
        
        
        commission = total_amount - amount_rub
        
        text = (
            f"🔍 <b>Заявка #{display_id}</b>\n\n"
            f"🆔 Внутренний ID: {internal_id}\n"
            f"👤 Пользователь: {user_id}\n"
            f"💰 Сумма: {amount_rub:,.0f} ₽\n"
            f"₿ Bitcoin: {amount_btc:.8f} BTC\n"
            f"💸 К оплате: {total_amount:,.0f} ₽\n"
            f"🏛 Комиссия сервиса: {commission:,.0f} ₽\n"
            f"💱 Курс: {rate:,.0f} ₽\n"
            f"📱 Тип оплаты: {payment_type or 'Не указан'}\n"
            f"📊 Статус: {status_text}\n"
            f"📅 Создана: {created_at}\n\n"
            f"₿ <b>Bitcoin адрес:</b>\n<code>{btc_address}</code>"
        )
        
        await message.answer(text, parse_mode="HTML")
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
        
    except Exception as e:
        await message.answer(f"❌ Ошибка поиска: {e}")

@router.message(AdminStates.waiting_for_user_id)
async def process_user_id_input(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("action")
    
    try:
        user_input = message.text.strip()
        if user_input.startswith("@"):
            user_id = await find_user_by_username(user_input[1:])
            if not user_id:
                await message.answer("❌ Пользователь с таким username не найден")
                return
        else:
            user_id = int(user_input)
        
        if action == "find_user":
            await show_user_info(message, user_id)
        elif action == "message_user":
            await state.update_data(target_user_id=user_id, action="message_user_step2")
            await message.answer(
                f"💬 <b>Отправка сообщения пользователю {user_id}</b>\n\n"
                "Введите текст сообщения:",
                parse_mode="HTML"
            )
            await state.set_state(AdminStates.waiting_for_message_to_user)
            return
        elif action == "block_user":
            await state.update_data(target_user_id=user_id, action="block_user_step2")
            await message.answer(
                f"🚫 <b>Блокировка пользователя {user_id}</b>\n\n"
                "Введите причину блокировки:",
                parse_mode="HTML"
            )
            await state.set_state(AdminStates.waiting_for_block_reason)
            return
        else:
            await handle_user_management(message, user_id, action)
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите корректный ID пользователя")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

async def show_user_info(message: Message, user_id: int):
    user = await db.get_user(user_id)
    if not user:
        await message.answer("❌ Пользователь не найден")
        return
    
    orders = await db.get_user_orders(user_id, 5)
    text = (
        f"👤 <b>Информация о пользователе</b>\n\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👨‍💼 Имя: {user['first_name'] or 'Не указано'}\n"
        f"📝 Username: @{user['username'] or 'Не указан'}\n"
        f"📅 Регистрация: {user['registration_date'][:16]}\n"
        f"🚫 Заблокирован: {'Да' if user.get('is_blocked') else 'Нет'}\n"
        f"📊 Операций: {user.get('total_operations', 0)}\n"
        f"💰 Общая сумма: {user.get('total_amount', 0):,.0f} ₽\n"
        f"👥 Рефералов: {user.get('referral_count', 0)}"
    )
    
    status_emoji_map = {
        'waiting': '⏳',
        'paid_by_client': '💰',
        'completed': '✅',
        'cancelled': '❌',
        'problem': '⚠️'
    }

    if orders:
        text += "\n\n📋 <b>Последние заявки:</b>\n"
        for order in orders:
            emoji = status_emoji_map.get(order['status'], '❓')
            text += f"{emoji} #{order['id']} - {order['total_amount']:,.0f} ₽\n"
    
    await message.answer(text, parse_mode="HTML")

async def handle_user_management(message: Message, user_id: int, action: str):
    if action == "unblock_user":
        user = await db.get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if not user.get('is_blocked'):
            await message.answer("❌ Пользователь не заблокирован")
            return
        
        await db.update_user(user_id, is_blocked=False)
        await message.answer(f"✅ Пользователь {user_id} разблокирован")
        
        try:
            await message.bot.send_message(
                user_id,
                "✅ <b>Ваш аккаунт разблокирован</b>\n\n"
                "Вы можете продолжить использование бота.",
                parse_mode="HTML"
            )
        except:
            pass

    elif action == "add_admin":
        admin_users = await db.get_setting("admin_users", [])
        if user_id not in admin_users:
            admin_users.append(user_id)
            await db.set_setting("admin_users", admin_users)
            await message.answer(f"✅ Пользователь {user_id} назначен администратором")
            try:
                await message.bot.send_message(user_id, "🎉 Вам выданы права администратора!")
            except:
                pass
        else:
            await message.answer("❌ Пользователь уже является администратором")

    elif action == "remove_admin":
        admin_users = await db.get_setting("admin_users", [])
        if user_id in admin_users:
            admin_users.remove(user_id)
            await db.set_setting("admin_users", admin_users)
            await message.answer(f"✅ Права администратора отозваны у пользователя {user_id}")
            try:
                await message.bot.send_message(user_id, "❌ Ваши права администратора отозваны")
            except:
                pass
        else:
            await message.answer("❌ Пользователь не является администратором")

    elif action == "add_operator":
        operator_users = await db.get_setting("operator_users", [])
        if user_id not in operator_users:
            operator_users.append(user_id)
            await db.set_setting("operator_users", operator_users)
            await message.answer(f"✅ Пользователь {user_id} назначен оператором")
            try:
                await message.bot.send_message(
                    user_id,
                    f"🎉 Вам выданы права оператора!\n"
                    f"Операторский чат: {config.OPERATOR_CHAT_ID}"
                )
            except:
                pass
        else:
            await message.answer("❌ Пользователь уже является оператором")

    elif action == "remove_operator":
        operator_users = await db.get_setting("operator_users", [])
        if user_id in operator_users:
            operator_users.remove(user_id)
            await db.set_setting("operator_users", operator_users)
            await message.answer(f"✅ Права оператора отозваны у пользователя {user_id}")
            try:
                await message.bot.send_message(user_id, "❌ Ваши права оператора отозваны")
            except:
                pass
        else:
            await message.answer("❌ Пользователь не является оператором")

@router.message(AdminStates.waiting_for_message_to_user)
async def process_user_message(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("target_user_id")
    
    try:
        full_message = (
            f"📨 <b>Сообщение от администрации</b>\n\n"
            f"{message.text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📞 Поддержка: {config.SUPPORT_MANAGER}"
        )
        
        await message.bot.send_message(user_id, full_message, parse_mode="HTML")
        await message.answer(f"✅ Сообщение отправлено пользователю {user_id}")
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

@router.message(AdminStates.waiting_for_block_reason)
async def process_block_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("target_user_id")
    reason = message.text
    
    try:
        user = await db.get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден")
            return
        
        if user.get('is_blocked'):
            await message.answer("❌ Пользователь уже заблокирован")
            return
        
        await db.update_user(user_id, is_blocked=True)
        await message.answer(f"✅ Пользователь {user_id} заблокирован\nПричина: {reason}")
        
        try:
            await message.bot.send_message(
                user_id,
                f"🚫 <b>Ваш аккаунт заблокирован</b>\n\n"
                f"📝 Причина: {reason}\n"
                f"📞 Для разблокировки обратитесь в поддержку: {config.SUPPORT_MANAGER}",
                parse_mode="HTML"
            )
        except:
            pass
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.message(AdminStates.waiting_for_broadcast_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    data = await state.get_data()
    action = data.get("action")
    target_users = data.get("target_users", [])
    
    if not target_users and action == "broadcast_all":
        target_users = await db.get_all_users()
    
    try:
        sent_count = failed_count = 0
        
        await message.answer(f"📤 Начинаю рассылку для {len(target_users)} пользователей...")
        
        for user_id in target_users:
            try:
                await message.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Failed to send broadcast to {user_id}: {e}")
        
        await message.answer(
            f"✅ <b>Рассылка завершена!</b>\n\n"
            f"📤 Отправлено: {sent_count}\n"
            f"❌ Ошибок: {failed_count}",
            parse_mode="HTML"
        )
        
        builder = create_main_admin_panel()
        await message.answer("👑 <b>Панель администратора</b>", reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка рассылки: {e}")

async def find_user_by_username(username: str) -> int:
    try:
        async with aiosqlite.connect(db.db_path) as database:
            async with database.execute(
                'SELECT user_id FROM users WHERE username = ? COLLATE NOCASE',
                (username,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    except:
        return None
    
import html
from aiogram.types import FSInputFile



@router.message(Command("get_log"))
async def get_log_command(message: Message):
    if not await is_admin_extended(message.from_user.id):
        return

    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.answer(
                "❌ <b>Как использовать:</b>\n"
                "<code>/get_log filename.log</code>",
                parse_mode="HTML"
            )
            return

        filename = parts[1]
        if not filename.endswith('.log'):
            filename += '.log'

        if not os.path.exists(filename):
            await message.answer(f"❌ Файл <b>{html.escape(filename)}</b> не найден.", parse_mode="HTML")
            return

        file_size = os.path.getsize(filename)
        last_modified = datetime.fromtimestamp(os.path.getmtime(filename)).strftime('%d.%m.%Y %H:%M')
        size_mb = file_size / 1024 / 1024

        
        with open(filename, encoding='utf-8', errors='replace') as f:
            content = f.read()

        if len(content) > 3800:
            preview = "...\n" + content[-3800:]
        else:
            preview = content

        preview = html.escape(preview)

        
        head = (
            f"📋 <b>Лог-файл: {html.escape(filename)}</b>\n"
            f"🗂️ Размер: {size_mb:.2f} MB\n"
            f"🕑 Обновлён: {last_modified}\n"
        )

        if file_size > 4096:                                             
            await message.answer(
                f"{head}\n"
                f"Показаны последние строки:\n\n"
                f"<code>{preview}</code>\n\n",
                parse_mode="HTML"
            )
            await message.answer_document(FSInputFile(filename))
        else:
            await message.answer(
                f"{head}\n"
                f"<code>{preview}</code>",
                parse_mode="HTML"
            )

    except Exception as e:
        await message.answer(
            f"❌ <b>Ошибка при чтении лога:</b>\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("review_"))
async def review_moderation(callback: CallbackQuery):
    if not await is_admin_extended(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    action, review_id = callback.data.split("_")[1:]
    
    try:
        if action == "approve":
            await db.update_review_status(review_id, "approved")
            await callback.answer("✅ Отзыв одобрен")
            
            review_data = await db.get_review(review_id)
            if review_data:
                channel_text = (
                    f"⭐️ <b>Отзыв о работе {config.EXCHANGE_NAME}</b>\n\n"
                    f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
                    f"💬 <b>Текст отзыва:</b>\n"
                    f"{review_data['text']}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"💰 {config.EXCHANGE_NAME} - надежный обмен криптовалют\n"
                    f"🤖 @{config.BOT_USERNAME}"
                )
                
                try:
                    await callback.bot.send_message(
                        config.REVIEWS_CHANNEL_ID,
                        channel_text,
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Failed to send review to channel: {e}")
            
            await callback.message.edit_text(
                f"{callback.message.text}\n\n✅ <b>ОДОБРЕН И ОПУБЛИКОВАН</b>",
                parse_mode="HTML"
            )
        
        elif action == "reject":
            await db.update_review_status(review_id, "rejected")
            await callback.answer("❌ Отзыв отклонен")
            await callback.message.edit_text(
                f"{callback.message.text}\n\n❌ <b>ОТКЛОНЕН</b>",
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Review moderation error: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)

from aiogram import F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

@router.callback_query(F.data == "view_turnover")
async def view_turnover_stats(callback: CallbackQuery):
    if not await is_admin_extended(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    total_stats = await db.get_total_turnover_by_mirror()
    today_stats = await db.get_turnover_by_period(1)
    week_stats = await db.get_turnover_by_period(7)
    month_stats = await db.get_turnover_by_period(30)
    mirrors_stats = await db.get_all_mirrors_turnover()
    
    text = f"📊 <b>СТАТИСТИКА ОБОРОТА</b>\n\n"
    text += f"🔥 <b>ОБЩИЙ ОБОРОТ ВСЕХ ЗЕРКАЛ:</b>\n"
    text += f"💰 Всего: {total_stats['total_amount']:,.0f} ₽\n"
    text += f"📋 Заказов: {total_stats['total_orders']}\n\n"
    
    text += f"📅 <b>ПО ПЕРИОДАМ:</b>\n"
    text += f"🌅 Сегодня: {today_stats['total_amount']:,.0f} ₽ ({today_stats['total_orders']} заказов)\n"
    text += f"📅 Неделя: {week_stats['total_amount']:,.0f} ₽ ({week_stats['total_orders']} заказов)\n"
    text += f"📊 Месяц: {month_stats['total_amount']:,.0f} ₽ ({month_stats['total_orders']} заказов)\n\n"
    
    if mirrors_stats:
        text += f"🪞 <b>ПО ЗЕРКАЛАМ:</b>\n"
        for mirror in mirrors_stats:
            text += f"• {mirror['mirror_id']}: {mirror['total']:,.0f} ₽ ({mirror['orders']} заказов)\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="detailed_turnover")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data="view_turnover")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_main_panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(F.data == "detailed_turnover")
async def detailed_turnover_stats(callback: CallbackQuery):
    if not await is_admin_extended(callback.from_user.id):
        await callback.answer("❌ Нет прав", show_alert=True)
        return
    
    current_mirror = config.MIRROR_ID
    current_stats = await db.get_total_turnover_by_mirror(current_mirror)
    
    text = f"📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА</b>\n\n"
    text += f"🪞 <b>ТЕКУЩЕЕ ЗЕРКАЛО: {current_mirror}</b>\n"
    text += f"💰 Оборот: {current_stats['total_amount']:,.0f} ₽\n"
    text += f"📋 Заказов: {current_stats['total_orders']}\n\n"
    
    
    today = await db.get_turnover_by_period(1, current_mirror)
    week = await db.get_turnover_by_period(7, current_mirror)
    month = await db.get_turnover_by_period(30, current_mirror)
    
    text += f"📅 <b>ПО ПЕРИОДАМ (текущее зеркало):</b>\n"
    text += f"🌅 Сегодня: {today['total_amount']:,.0f} ₽\n"
    text += f"📅 Неделя: {week['total_amount']:,.0f} ₽\n"
    text += f"📊 Месяц: {month['total_amount']:,.0f} ₽\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К общей статистике", callback_data="view_turnover")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
