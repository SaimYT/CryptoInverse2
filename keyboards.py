from aiogram.utils.keyboard import InlineKeyboardBuilder
from reviews import TOTAL_REVIEWS
from config import REVIEWS_PER_PAGE


def main_menu():
    builder = InlineKeyboardBuilder()
    builder.button(text="🛒 Купить криптовалюту", callback_data="buy_crypto", style="success")
    builder.button(text="⭐ Отзывы", callback_data="reviews_page_0")
    builder.button(text="💰 Продать криптовалюту", callback_data="sell_crypto", style="danger")
    builder.button(text="📄 Пользовательское соглашение", callback_data="terms")
    builder.button(text="👤 Профиль пользователя", callback_data="ref_profile")
    builder.button(text="📢 Обновления", callback_data="updates")
    builder.button(text="⭐ Купить ЗВЕЗДЫ TELEGRAM!", callback_data="stars_shop")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def crypto_list_sell():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 SOLANA", callback_data="sell_select_SOL")
    builder.button(text="💎 TRON", callback_data="sell_select_TRX")
    builder.button(text="💵 USDT (TRC20)", callback_data="sell_select_USDT_TRC20")
    builder.button(text="💠 TON", callback_data="sell_select_TON")
    builder.button(text="⟠ ETHEREUM", callback_data="sell_select_ETH")
    builder.button(text="🟡 BNB", callback_data="sell_select_BNB")
    builder.button(text="⚡ HYPERLIQUID", callback_data="sell_select_HYPE")
    builder.button(text="🔵 BASE", callback_data="sell_select_BASE")
    builder.button(text="🔷 ARBITRUM", callback_data="sell_select_ARB")
    builder.button(text="🟣 POLYGON", callback_data="sell_select_MATIC")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def crypto_list_buy():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 SOLANA", callback_data="buy_select_SOL")
    builder.button(text="💎 TRON", callback_data="buy_select_TRX")
    builder.button(text="💵 USDT (TRC20)", callback_data="buy_select_USDT_TRC20")
    builder.button(text="💠 TON", callback_data="buy_select_TON")
    builder.button(text="⟠ ETHEREUM", callback_data="buy_select_ETH")
    builder.button(text="🟡 BNB", callback_data="buy_select_BNB")
    builder.button(text="⚡ HYPERLIQUID", callback_data="buy_select_HYPE")
    builder.button(text="🔵 BASE", callback_data="buy_select_BASE")
    builder.button(text="🔷 ARBITRUM", callback_data="buy_select_ARB")
    builder.button(text="🟣 POLYGON", callback_data="buy_select_MATIC")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def payment_methods():
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 СБП", callback_data="pay_СБП")
    builder.button(text="🟨 Т-Банк (T-Pay)", callback_data="pay_SberPay")
    builder.button(text="💳 Банковская карта", callback_data="pay_Карта")
    builder.button(text="🪙 Криптовалюта", callback_data="pay_Криптовалюта")
    builder.button(text="🔙 Отмена", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def paid_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data="buy_paid")
    builder.button(text="🆘 Поддержка", url="https://t.me/cryptoinversesup")
    builder.adjust(1)
    return builder.as_markup()


def sell_paid_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я отправил крипту", callback_data="sell_paid")
    builder.button(text="🆘 Поддержка", url="https://t.me/cryptoinversesup")
    builder.adjust(1)
    return builder.as_markup()


def profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Ваши заказы", callback_data="orders_list")
    builder.button(text="💳 Пополнить баланс", callback_data="topup_start")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def topup_cancel():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="back_to_main")
    return builder.as_markup()


def orders_list_keyboard(orders):
    builder = InlineKeyboardBuilder()
    for order in orders:
        emoji = _status_emoji(order["status"])
        text = f"{emoji} {order['order_number']} | {_status_label(order['status'])}"
        builder.button(text=text, callback_data=f"order_view_{order['order_number']}")
    builder.button(text="🔙 Назад в профиль", callback_data="ref_profile")
    layout = [1] * len(orders) + [1]
    builder.adjust(*layout)
    return builder.as_markup()


def order_detail_keyboard(order_number: str):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data=f"order_view_{order_number}")
    builder.button(text="🗑 Удалить", callback_data=f"order_delete_{order_number}")
    builder.button(text="🔙 К заказам", callback_data="orders_list")
    builder.adjust(2, 1)
    return builder.as_markup()


def _status_emoji(status: str) -> str:
    return {
        "waiting_data": "📝",
        "waiting_payment": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "cancelled": "❌",
    }.get(status, "❔")


def _status_label(status: str) -> str:
    return {
        "waiting_data": "Ожидает данных",
        "waiting_payment": "Ожидает оплату",
        "processing": "В обработке",
        "completed": "Завершён",
        "cancelled": "Отменён",
    }.get(status, "Неизвестно")


def reviews_keyboard(page: int):
    total_pages = (TOTAL_REVIEWS + REVIEWS_PER_PAGE - 1) // REVIEWS_PER_PAGE
    builder = InlineKeyboardBuilder()
    start = page * REVIEWS_PER_PAGE
    end = min(start + REVIEWS_PER_PAGE, TOTAL_REVIEWS)
    for i in range(start, end):
        from reviews import REVIEWS
        r = REVIEWS[i]
        stars = "⭐" * r["stars"]
        builder.button(text=f"{r['name']} | {stars}", callback_data=f"review_{i}")
    prev_page = (page - 1) % total_pages
    next_page = (page + 1) % total_pages
    builder.button(text="«", callback_data=f"reviews_page_{prev_page}")
    builder.button(text=f"{page + 1} / {total_pages}", callback_data="reviews_nop")
    builder.button(text="»", callback_data=f"reviews_page_{next_page}")
    layout = [1] * (end - start) + [3, 1]
    builder.adjust(*layout)
    return builder.as_markup()


def back_to_main():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    return builder.as_markup()


def support_button():
    builder = InlineKeyboardBuilder()
    builder.button(text="🆘 Поддержка", url="https://t.me/cryptoinversesup")
    return builder.as_markup()

def updates_keyboard():
    """Клавиатура обновлений: покупка, продажа и возврат."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🟢 Купить криптовалюту", callback_data="buy_crypto")
    builder.button(text="🔴 Продать криптовалюту", callback_data="sell_crypto")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def stars_delivery_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔥 Через Username", callback_data="stars_method_username")
    builder.button(text="🎁 Через подарки", callback_data="stars_method_gifts")
    builder.adjust(2)
    return builder.as_markup()


def stars_payment_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил", callback_data="stars_paid")
    builder.button(text="🆘 Поддержка", url="https://t.me/cryptoinversesup")
    builder.adjust(1)
    return builder.as_markup()
