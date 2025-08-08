from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder

class ReplyKeyboards:
    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="Купить"))
        builder.row(
            KeyboardButton(text="О сервисе ℹ️"),
            KeyboardButton(text="Калькулятор валют")
        )
        builder.row(
            KeyboardButton(text="Оставить отзыв"),
            KeyboardButton(text="Как сделать обмен?")
        )
        builder.row(
            KeyboardButton(text="Друзья"),
            KeyboardButton(text="📊 Мои заявки")
        )
        return builder.as_markup(resize_keyboard=True, persistent=True)

    @staticmethod
    def back_to_main() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="◀️ Главное меню"))
        return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

    @staticmethod
    def payment_methods() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="💳 Банковская карта"))
        builder.row(
            KeyboardButton(text="◀️ Назад"),
            KeyboardButton(text="◀️ Главное меню")
        )
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def order_menu(is_nicepay: bool = False) -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        if not is_nicepay:
            builder.row(KeyboardButton(text="❌ Отменить заявку"))
        builder.row(KeyboardButton(text="🔄 Проверить статус"))
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def admin_menu() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.row(
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="⚙️ Настройки")
        )
        builder.row(
            KeyboardButton(text="📢 Рассылка"),
            KeyboardButton(text="💰 Баланс")
        )
        builder.row(
            KeyboardButton(text="👥 Пользователи"),
            KeyboardButton(text="📋 Заявки")
        )
        builder.row(KeyboardButton(text="◀️ Выйти из админки"))
        return builder.as_markup(resize_keyboard=True)

    @staticmethod
    def admin_chat_menu() -> ReplyKeyboardMarkup:
        builder = ReplyKeyboardBuilder()
        builder.row(
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="⚙️ Настройки")
        )
        builder.row(
            KeyboardButton(text="📋 Заявки"),
            KeyboardButton(text="💰 Баланс")
        )
        builder.row(
            KeyboardButton(text="👥 Персонал"),
            KeyboardButton(text="🔧 Управление")
        )
        builder.row(KeyboardButton(text="❌ Скрыть панель"))
        return builder.as_markup(resize_keyboard=True, persistent=True)

    @staticmethod
    def remove_keyboard() -> ReplyKeyboardRemove:
        return ReplyKeyboardRemove()
