                    
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

class ReplyKeyboards:
    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
                           
        builder = ReplyKeyboardBuilder()
        
                       
        builder.row(
            KeyboardButton(text="Купить"),
        )
        
                       
        builder.row(
            KeyboardButton(text="О сервисе ℹ️"),
            KeyboardButton(text="Калькулятор валют"),
        )
        
                       
        builder.row(
            KeyboardButton(text="Оставить отзыв"),
            KeyboardButton(text="Как сделать обмен?")
        )
        
                          
        builder.row(
            KeyboardButton(text="Друзья"),
            KeyboardButton(text="📊 Мои заявки"),
        )
        
        return builder.as_markup(
            resize_keyboard=True,
            persistent=True
        )
    
    @staticmethod
    def back_to_main() -> ReplyKeyboardMarkup:
                                            
        builder = ReplyKeyboardBuilder()
        builder.row(KeyboardButton(text="◀️ Главное меню"))
        
        return builder.as_markup(
            resize_keyboard=True,
            one_time_keyboard=True
        )
  
    
    @staticmethod
    def payment_methods() -> ReplyKeyboardMarkup:
                            
        builder = ReplyKeyboardBuilder()
        
        builder.row(
            KeyboardButton(text="💳 Банковская карта"),
                                          
        )
        builder.row(
            KeyboardButton(text="◀️ Назад"),
            KeyboardButton(text="◀️ Главное меню")
        )
        
        return builder.as_markup(resize_keyboard=True)
    
    @staticmethod
    def order_menu(is_nicepay: bool = False) -> ReplyKeyboardMarkup:
                         
        builder = ReplyKeyboardBuilder()
        
        if not is_nicepay:                                                
            builder.row(
                                                              
                KeyboardButton(text="❌ Отменить заявку")
            )
        
        builder.row(
            KeyboardButton(text="🔄 Проверить статус")
        )
        
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
        builder.row(
            KeyboardButton(text="◀️ Выйти из админки")
        )
        
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
        builder.row(
            KeyboardButton(text="❌ Скрыть панель")
        )
        
        return builder.as_markup(
            resize_keyboard=True,
            persistent=True
        )
    
    @staticmethod
    def remove_keyboard() -> ReplyKeyboardMarkup:
                                 
        from aiogram.types import ReplyKeyboardRemove
        return ReplyKeyboardRemove()


                                                     
class InlineKeyboards:
    @staticmethod
    def order_actions(order_id: int):
                                                
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_order_{order_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_order_{order_id}")
        )
        return builder.as_markup()
    
    @staticmethod
    def operator_panel(order_id: int):
                                                
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Оплачено", callback_data=f"op_paid_{order_id}"),
            InlineKeyboardButton(text="❌ Не оплачено", callback_data=f"op_not_paid_{order_id}")
        )
        builder.row(
            InlineKeyboardButton(text="⚠️ Проблема", callback_data=f"op_problem_{order_id}"),
            InlineKeyboardButton(text="📝 Заметка", callback_data=f"op_note_{order_id}")
        )
        return builder.as_markup()
    
    @staticmethod
    def confirmation(action: str, data: str = ""):
                                    
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_{action}_{data}"),
            InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_{action}_{data}")
        )
        return builder.as_markup()
    
    @staticmethod
    def admin_chat_quick_menu():
                                              
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")
        )
        builder.row(
            InlineKeyboardButton(text="📋 Заявки", callback_data="admin_orders"),
            InlineKeyboardButton(text="💰 Баланс", callback_data="admin_balance")
        )
        builder.row(
            InlineKeyboardButton(text="👥 Персонал", callback_data="admin_staff"),
            InlineKeyboardButton(text="🔧 Управление", callback_data="admin_management")
        )
        return builder.as_markup()