from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

class InlineKeyboards:
    @staticmethod
    def currency_calculator() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="RUB → BTC", callback_data="calc_rub_btc"))
        builder.row(InlineKeyboardButton(text="BTC → RUB", callback_data="calc_btc_rub"))
        builder.row(InlineKeyboardButton(text="Главная", callback_data="calc_main_menu"))
        return builder.as_markup()

    @staticmethod
    def calculator_amount_input(pair: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if "rub" in pair.lower():
            amounts = ["1000", "5000", "10000", "50000", "100000", "500000"]
        else:
            amounts = ["0.001", "0.01", "0.1", "1", "5", "10"]

        for i in range(0, len(amounts), 3):
            row_buttons = []
            for j in range(3):
                if i + j < len(amounts):
                    amount = amounts[i + j]
                    row_buttons.append(
                        InlineKeyboardButton(
                            text=amount,
                            callback_data=f"calc_amount_{pair}_{amount}"
                        )
                    )
            if row_buttons:
                builder.row(*row_buttons)

        builder.row(
            InlineKeyboardButton(text="↔️ Наоборот", callback_data=f"calc_reverse_{pair}"),
            InlineKeyboardButton(text="🔄 Обновить курс", callback_data=f"calc_refresh_{pair}")
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data="calc_back"),
            InlineKeyboardButton(text="🏠 Главная", callback_data="calc_main_menu")
        )
        return builder.as_markup()

    @staticmethod
    def calculator_result(pair: str, amount: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔄 Пересчитать", callback_data=f"calc_recalc_{pair}"))
        builder.row(
            InlineKeyboardButton(text="↔️ Наоборот", callback_data=f"calc_reverse_{pair}"),
            InlineKeyboardButton(text="📊 Новый расчет", callback_data="calc_back")
        )
        builder.row(InlineKeyboardButton(text="🏠 Главная", callback_data="calc_main_menu"))
        return builder.as_markup()

    @staticmethod
    def buy_crypto_selection() -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="BTC", callback_data="buy_btc"))
        builder.row(InlineKeyboardButton(text="Главная", callback_data="buy_main_menu"))
        return builder.as_markup()

    @staticmethod
    def exchange_type_selection(crypto: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=f"₽ → {crypto.upper()}",
                callback_data=f"exchange_rub_to_{crypto.lower()}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text=f"{crypto.upper()} → ₽",
                callback_data=f"exchange_{crypto.lower()}_to_rub"
            )
        )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data="exchange_back"),
            InlineKeyboardButton(text="🏠 Главная", callback_data="exchange_main_menu")
        )
        return builder.as_markup()

    @staticmethod
    def amount_input_keyboard(crypto: str, direction: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if direction == "rub_to_crypto":
            amounts = ["2000", "5000", "10000", "50000", "100000"]
            currency_symbol = "₽"
        else:
            crypto_upper = crypto.upper()
            if crypto_upper == "BTC":
                amounts = ["0.001", "0.01", "0.1", "0.5", "1", "5"]
            elif crypto_upper in ["LTC", "XMR"]:
                amounts = ["0.1", "1", "5", "10", "50", "100"]
            else:
                amounts = ["100", "500", "1000", "5000", "10000", "50000"]
            currency_symbol = crypto_upper

        for i in range(0, len(amounts), 3):
            row_buttons = []
            for j in range(3):
                if i + j < len(amounts):
                    amount = amounts[i + j]
                    row_buttons.append(
                        InlineKeyboardButton(
                            text=f"{amount} {currency_symbol}",
                            callback_data=f"amount_{crypto}_{direction}_{amount}"
                        )
                    )
            if row_buttons:
                builder.row(*row_buttons)

        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"amount_back_{crypto}"),
            InlineKeyboardButton(text="🏠 Главная", callback_data="amount_main_menu")
        )
        return builder.as_markup()

    @staticmethod
    def payment_methods_for_crypto(crypto: str, amount: str, direction: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        if direction == "rub_to_crypto":
            builder.row(
                InlineKeyboardButton(
                    text="💳 Банковская карта",
                    callback_data=f"payment_{crypto}_{direction}_{amount}_card"
                )
            )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"payment_back_{crypto}_{direction}"),
            InlineKeyboardButton(text="🏠 Главная", callback_data="payment_main_menu")
        )
        return builder.as_markup()

    @staticmethod
    def order_confirmation(order_id: int) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_order_{order_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_order_{order_id}")
        )
        return builder.as_markup()

    @staticmethod
    def order_actions(order_id: int) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить", callback_data=f"refresh_order_{order_id}"),
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_order_{order_id}")
        )
        return builder.as_markup()

    @staticmethod
    def operator_panel(order_id: int) -> InlineKeyboardMarkup:
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
