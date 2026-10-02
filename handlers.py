from pathlib import Path
import html as htmlmod
import asyncio
import random
import string
import re
from datetime import datetime, timedelta
from decimal import Decimal
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, FSInputFile

from keyboards import (
    main_menu, crypto_list_sell, crypto_list_buy, payment_methods,
    paid_button, sell_paid_button, back_to_main, support_button,
    profile_keyboard, topup_cancel, reviews_keyboard,
    orders_list_keyboard, order_detail_keyboard, updates_keyboard, stars_delivery_keyboard, stars_payment_confirm_keyboard
)
from utils import (
    get_crypto_prices, get_sol_balance, get_trc20_balance, get_ton_balance
)
from database import (
    create_user, count_referrals, get_referrals, get_referrer,
    add_balance, get_balance, create_order, update_order_status,
    update_order_data, get_order, get_user_orders, delete_order, get_all_user_ids
)
from reviews import REVIEWS, TOTAL_REVIEWS, get_review_by_id
from config import (
    WALLETS, COIN_NAMES, PAYMENT_DETAILS, PAYMENT_TIMEOUT, PAYMENT_CHECK_INTERVAL,
    SUPPORT_USERNAME, MIN_USD, MIN_RUB, SELL_MULTIPLIER, BUY_MULTIPLIER,
    BOT_USERNAME, REFERRAL_BONUS_PERCENT, REFERRAL_SIGNUP_BONUS,
    REVIEWS_PER_PAGE, ADMIN_IDS, ADMIN_USERNAMES
)

router = Router()

AUTO_CHECK = {"SOL", "USDT_TRC20", "TON"}


class SellStates(StatesGroup):
    waiting_amount = State()
    waiting_address = State()
    waiting_payment = State()


class BuyStates(StatesGroup):
    waiting_amount = State()
    waiting_address = State()
    waiting_payment_method = State()
    waiting_payment_confirm = State()


class TopUpStates(StatesGroup):
    waiting_amount = State()


class StarsStates(StatesGroup):
    waiting_amount = State()
    waiting_username = State()
    waiting_payment = State()
    waiting_payment_confirm = State()


async def safe_delete(message: Message):
    try:
        await message.delete()
    except Exception:
        pass


async def show_loading(message: Message, seconds: int = 2):
    try:
        loading_msg = await message.answer("⌛")
    except Exception:
        return
    await asyncio.sleep(seconds)
    try:
        await loading_msg.delete()
    except Exception:
        pass


def generate_number() -> str:
    digits = "".join(random.choices(string.digits, k=10))
    return f"CI-{digits}"


def status_emoji(status: str) -> str:
    return {
        "waiting_data": "📝",
        "waiting_payment": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "cancelled": "❌",
    }.get(status, "❔")


def status_label(status: str) -> str:
    return {
        "waiting_data": "Ожидает данных",
        "waiting_payment": "Ожидает оплату",
        "processing": "В обработке",
        "completed": "Завершён",
        "cancelled": "Отменён",
    }.get(status, "Неизвестно")


def credit_referral(user_id: int, amount_rub: float):
    referrer_id = get_referrer(user_id)
    if not referrer_id:
        return None, 0
    bonus_rub = amount_rub * REFERRAL_BONUS_PERCENT
    add_balance(referrer_id, amount_rub=bonus_rub)
    return referrer_id, bonus_rub


def fmt_price(usd: Decimal, rub: Decimal) -> str:
    return f"${usd:,.2f} | {rub:,.2f} ₽"


def build_payment_receipt(
    order_number, purchase, total_usd=None, total_rub=None,
    payment_method="—", recipient_label="Кошелёк получателя",
    recipient="—", support_text="Для получения криптовалюты напишите в поддержку"
):
    """Build a consistent HTML receipt for every payment method."""
    safe = lambda value: htmlmod.escape(str(value if value not in (None, "") else "—"))
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    lines = [
        "✅ <b>Чек об оплате</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        f"🧾 Номер заказа: <code>{safe(order_number)}</code>",
        f"📅 Дата: {now_str}",
        f"🛒 Покупка: <b>{safe(purchase)}</b>",
    ]
    if total_usd is not None:
        lines.append(f"💵 ${float(total_usd):,.2f}")
    if total_rub is not None:
        lines.append(f"💴 {float(total_rub):,.2f} ₽")
    lines.extend([
        f"💳 Способ оплаты: <b>{safe(payment_method)}</b>",
        f"📍 {safe(recipient_label)}:",
        f"<code>{safe(recipient)}</code>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💬 <b>{safe(support_text)}:</b>",
        f"👉 @{safe(SUPPORT_USERNAME.lstrip('@'))}",
    ])
    return "\n".join(lines)


async def send_payment_receipt(bot: Bot, chat_id: int, caption: str):
    """Send the receipt with the branded banner; fall back to text if absent."""
    image_path = Path(__file__).resolve().parent / "images" / "check.png"
    if image_path.is_file():
        await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(str(image_path)),
            caption=caption,
            parse_mode="HTML",
        )
    else:
        await bot.send_message(chat_id=chat_id, text=caption, parse_mode="HTML")


def build_crypto_text(prices, multiplier):
    lines = []
    order = ["SOL", "TRX", "USDT_TRC20", "TON", "ETH", "BNB", "HYPE", "BASE", "ARB", "MATIC"]
    for coin in order:
        usd = prices[coin]["usd"] * Decimal(str(multiplier))
        rub = prices[coin]["rub"] * Decimal(str(multiplier))
        name = COIN_NAMES[coin]
        lines.append(f"• <b>{name}</b> — {fmt_price(usd, rub)}")
    return "\n".join(lines)


# ========== СТАРТ ==========
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or ""

    referrer_id = None
    args = command.args if command else None
    if args and args.startswith("ref_"):
        try:
            ref_id = int(args.replace("ref_", ""))
            if ref_id != user_id:
                referrer_id = ref_id
        except ValueError:
            referrer_id = None

    is_new = create_user(user_id, username, referrer_id)

    referral_notice = ""
    if is_new and referrer_id:
        add_balance(referrer_id, amount_rub=REFERRAL_SIGNUP_BONUS)
        try:
            await message.bot.send_message(
                referrer_id,
                f"🎉 <b>По вашей ссылке зарегистрировался новый реферал!</b>\n\n"
                f"👤 Имя: {username or 'Скрыто'}\n"
                f"🆔 ID: <code>{user_id}</code>\n\n"
                f"💰 Вам начислено <b>{REFERRAL_SIGNUP_BONUS} ₽</b> на баланс!"
            )
        except Exception:
            pass

        referral_notice = (
            "🎁 <b>Реферал засчитан!</b>\n"
            "Вы были приглашены по реферальной ссылке.\n\n"
        )

    welcome_text = (
        f"{referral_notice}"
        "Ха-Ха! Добро пожаловать в CryptoInverseBot 👋\n\n"
        "Данный бот создан для продажи и покупки криптовалюты, у нас самый лучший курс среди конкурентов! 🔥\n\n"
        "Быстрая тех.поддержка 🤖\n\n"
        "Так же, у нас действуют скидки 20% на все товары в честь <b>ЖУТКОГО МЕСЯЦА</b> 🎃\n\n"
        "Работаем 24/7, нажимайте на кнопку ниже и следуйте инструкции! 🤑"
    )

    try:
        photo = FSInputFile("images/hello.png")
        await message.answer_photo(photo, caption=welcome_text, reply_markup=main_menu())
    except FileNotFoundError:
        await message.answer(welcome_text, reply_markup=main_menu())


@router.callback_query(F.data == "updates")
async def show_updates(callback: CallbackQuery):
    text = (
        "📢 <b>Обновления CryptoInverseBot</b>\n\n"
        "<b>02.10.2026:</b>\n\n"
        "• Обновление: Жуткий месяц! 🎃\n"
        "• Скидки 20%!\n"
        "• Исправлена система оплаты\n"
        "• Исправлена авто-выдача криптовалюты\n"
        "• Создан официальный Telegram-Канал."
    )
    await callback.message.answer(text, reply_markup=updates_keyboard())
    await callback.answer()

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if (message.from_user.id not in ADMIN_IDS and
            (message.from_user.username or "").casefold() not in ADMIN_USERNAMES):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return

    source = message.reply_to_message or message
    raw = message.caption if message.caption is not None else message.text or ""
    broadcast_text = raw.partition(" ")[2].strip() if raw.startswith("/broadcast") else raw.strip()
    if source is message and not message.photo and not message.document and not message.video and not broadcast_text:
        await message.answer("Использование: /broadcast Текст или отправьте фото с подписью /broadcast Текст. Можно также ответить командой на медиа.")
        return

    user_ids = get_all_user_ids()
    status = await message.answer(f"📤 Начинаю рассылку для {len(user_ids)} пользователей...")
    sent = failed = 0
    for user_id in user_ids:
        try:
            if source.photo:
                await message.bot.send_photo(user_id, source.photo[-1].file_id, caption=broadcast_text or None)
            elif source.document:
                await message.bot.send_document(user_id, source.document.file_id, caption=broadcast_text or None)
            elif source is not message and source.content_type != "text":
                await message.bot.copy_message(user_id, source.chat.id, source.message_id, caption=broadcast_text or None)
            else:
                await message.bot.send_message(user_id, broadcast_text)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ Рассылка завершена.\nУспешно: {sent}\nНе доставлено: {failed}")


@router.message(Command("terms"))
async def cmd_terms(message: Message, state: FSMContext):
    await state.clear()
    terms_text = (
        "📄 <b>Пользовательское соглашение</b>\n\n"
        "1. Отправляя криптовалюту, вы подтверждаете, что она принадлежит вам.\n"
        "2. Курс фиксируется в момент создания заявки.\n"
        "3. Средства зачисляются после подтверждения сети.\n"
        f"4. Поддержка: @{SUPPORT_USERNAME}"
    )
    await message.answer(terms_text, reply_markup=back_to_main())


@router.message(Command("sell"))
async def cmd_sell(message: Message, state: FSMContext):
    await state.clear()
    prices = await get_crypto_prices()
    text = (
        "💸 <b>Продажа криптовалюты</b>\n\n"
        "📊 <b>Актуальные курсы</b>:\n\n"
        f"{build_crypto_text(prices, SELL_MULTIPLIER)}\n\n"
        "Выберите криптовалюту для продажи:"
    )
    try:
        photo = FSInputFile("images/crypto.png")
        await message.answer_photo(photo, caption=text, reply_markup=crypto_list_sell())
    except FileNotFoundError:
        await message.answer(text, reply_markup=crypto_list_sell())


@router.message(Command("buy"))
async def cmd_buy(message: Message, state: FSMContext):
    await state.clear()
    prices = await get_crypto_prices()
    text = (
        "🛒 <b>Покупка криптовалюты</b>\n\n"
        "📊 <b>Актуальные курсы</b>:\n\n"
        f"{build_crypto_text(prices, BUY_MULTIPLIER)}\n\n"
        "Выберите криптовалюту для покупки:"
    )
    try:
        photo = FSInputFile("images/crypto.png")
        await message.answer_photo(photo, caption=text, reply_markup=crypto_list_buy())
    except FileNotFoundError:
        await message.answer(text, reply_markup=crypto_list_buy())


@router.callback_query(F.data == "back_to_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await safe_delete(callback.message)
    welcome_text = (
        "Ха-Ха! Добро пожаловать в CryptoInverseBot 👋\n\n"
        "Данный бот создан для продажи и покупки криптовалюты, у нас самый лучший курс среди конкурентов! 🔥\n\n"
        "Быстрая тех.поддержка 🤖\n\n"
        "Так же, у нас действуют скидки 20% на все товары в честь <b>ЖУТКОГО МЕСЯЦА</b> 🎃\n\n"
        "Работаем 24/7, нажимайте на кнопку ниже и следуйте инструкции! 🤑"
    )
    try:
        photo = FSInputFile("images/hello.png")
        await callback.message.answer_photo(photo, caption=welcome_text, reply_markup=main_menu())
    except FileNotFoundError:
        await callback.message.answer(welcome_text, reply_markup=main_menu())
    await callback.answer()


@router.callback_query(F.data == "terms")
async def show_terms(callback: CallbackQuery):
    await safe_delete(callback.message)
    terms_text = (
        "📄 <b>Пользовательское соглашение</b>\n\n"
        "1. Отправляя криптовалюту, вы подтверждаете, что она принадлежит вам.\n"
        "2. Курс фиксируется в момент создания заявки.\n"
        "3. Средства зачисляются после подтверждения сети.\n"
        f"4. Поддержка: @{SUPPORT_USERNAME}"
    )
    await callback.message.answer(terms_text, reply_markup=back_to_main())
    await callback.answer()


# ========== ПРОФИЛЬ ==========
@router.callback_query(F.data == "ref_profile")
async def ref_profile(callback: CallbackQuery):
    await safe_delete(callback.message)
    user_id = callback.from_user.id
    total_referrals = count_referrals(user_id)
    referrals = get_referrals(user_id)
    balance_rub, balance_usd = get_balance(user_id)

    prices = await get_crypto_prices()
    usdt_rub = prices.get("USDT_TRC20", {}).get("rub", Decimal("95"))
    if usdt_rub == 0:
        usdt_rub = Decimal("95")
    balance_usd_calc = Decimal(str(balance_rub)) / usdt_rub

    referrals_list = ""
    if referrals:
        for i, ref in enumerate(referrals[:10], 1):
            name = ref["username"] if ref["username"] else f"ID {ref['user_id']}"
            referrals_list += f"  {i}. {name}\n"
        if total_referrals > 10:
            referrals_list += f"  ... и ещё {total_referrals - 10}\n"

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

    ref_text = (
        "👤 <b>Профиль пользователя</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 <b>Баланс:</b>\n"
        f"  💴 {balance_rub:,.2f} ₽\n"
        f"  💵 ${balance_usd_calc:,.2f}\n\n"
        "🔗 <b>Ваша реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "🎁 <b>Награды за рефералов:</b>\n"
        f"  💵 {REFERRAL_SIGNUP_BONUS} ₽ за каждого нового реферала\n"
        f"  📈 {int(REFERRAL_BONUS_PERCENT * 100)}% от его сделок\n\n"
        f"👥 <b>Всего рефералов:</b> <b>{total_referrals}</b>\n"
    )
    if referrals_list:
        ref_text += f"\n📋 <b>Ваши рефералы:</b>\n{referrals_list}"
    ref_text += "\n💡 Приглашайте друзей — и получайте пассивный доход!"

    try:
        photo = FSInputFile("images/referal.png")
        await callback.message.answer_photo(photo, caption=ref_text, reply_markup=profile_keyboard())
    except FileNotFoundError:
        await callback.message.answer(ref_text, reply_markup=profile_keyboard())
    await callback.answer()


# ========== ЗАКАЗЫ ==========
@router.callback_query(F.data == "orders_list")
async def orders_list(callback: CallbackQuery):
    await safe_delete(callback.message)
    user_id = callback.from_user.id
    orders = get_user_orders(user_id, limit=20)
    if not orders:
        text = (
            "📋 <b>Ваши заказы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "У вас пока нет заказов.\n\n"
            "💡 Создайте первый заказ!"
        )
        await callback.message.answer(text, reply_markup=profile_keyboard())
        await callback.answer()
        return
    text = (
        "📋 <b>Ваши заказы</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Всего заказов: <b>{len(orders)}</b>\n\n"
        "Нажмите на заказ, чтобы посмотреть детали 👇"
    )
    await callback.message.answer(text, reply_markup=orders_list_keyboard(orders))
    await callback.answer()


@router.callback_query(F.data.startswith("order_view_"))
async def order_view(callback: CallbackQuery):
    order_number = callback.data.replace("order_view_", "")
    order = get_order(order_number)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    if order["user_id"] != callback.from_user.id:
        await callback.answer("Это не ваш заказ", show_alert=True)
        return

    status = order["status"]
    emoji = status_emoji(status)
    label = status_label(status)
    direction = "Продажа" if order["direction"] == "sell" else "Покупка"
    created = order["created_at"] or "—"

    hints = {
        "waiting_data": "📝 <b>Что делать:</b>\nВам нужно завершить заполнение заявки.",
        "waiting_payment": f"⏳ <b>Что делать:</b>\nОжидаем оплату.\n🆘 Если что — @{SUPPORT_USERNAME}.",
        "processing": f"🔄 <b>Что делать:</b>\nЗаказ в обработке.\n🆘 Если долго — @{SUPPORT_USERNAME}.",
        "completed": f"✅ <b>Что делать:</b>\nЗаказ завершён. Спасибо!\n🆘 Вопросы — @{SUPPORT_USERNAME}.",
        "cancelled": f"❌ <b>Что делать:</b>\nЗаказ отменён.\n🆘 Поддержка: @{SUPPORT_USERNAME}.",
    }
    hint = hints.get(status, "Неизвестный статус.")

    text = (
        f"{emoji} <b>Заказ {order['order_number']}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 Статус: <b>{label}</b>\n"
        f"🔀 Тип: <b>{direction}</b>\n"
        f"💱 Криптовалюта: <b>{COIN_NAMES.get(order['currency'], order['currency'])}</b>\n"
        f"🔢 Количество: <b>{order['amount']}</b>\n"
        f"💰 Сумма: <b>{order['total_rub']:,.2f} ₽</b> / <b>${order['total_usd']:,.2f}</b>\n"
    )
    if order["wallet_address"]:
        text += f"📍 Кошелёк: <code>{order['wallet_address']}</code>\n"
    if order["payment_method"]:
        text += f"💳 Способ оплаты: <b>{order['payment_method']}</b>\n"
    text += f"📅 Дата: <b>{created}</b>\n━━━━━━━━━━━━━━━━━━━━\n{hint}"

    await safe_delete(callback.message)
    await callback.message.answer(text, reply_markup=order_detail_keyboard(order_number))
    await callback.answer()


@router.callback_query(F.data.startswith("order_delete_"))
async def order_delete(callback: CallbackQuery):
    order_number = callback.data.replace("order_delete_", "")
    order = get_order(order_number)
    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    delete_order(order_number)
    await callback.answer("Заказ удалён", show_alert=True)
    user_id = callback.from_user.id
    orders = get_user_orders(user_id, limit=20)
    await safe_delete(callback.message)
    if not orders:
        text = "📋 <b>Ваши заказы</b>\n\nУ вас пока нет заказов."
        await callback.message.answer(text, reply_markup=profile_keyboard())
    else:
        text = (
            "📋 <b>Ваши заказы</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Всего заказов: <b>{len(orders)}</b>\n\n"
            "Нажмите на заказ:"
        )
        await callback.message.answer(text, reply_markup=orders_list_keyboard(orders))


# ========== ПОПОЛНЕНИЕ ==========
@router.callback_query(F.data == "topup_start")
async def topup_start(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await callback.message.answer(
        "💳 <b>Пополнение баланса</b>\n\n"
        "Введите сумму в рублях, на которую хотите пополнить баланс.\n"
        "Например: <code>1000</code>",
        reply_markup=topup_cancel()
    )
    await state.set_state(TopUpStates.waiting_amount)
    await callback.answer()


@router.message(TopUpStates.waiting_amount)
async def topup_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введите корректное число (например, <code>1000</code>).")
        return
    await show_loading(message, 2)
    text = (
        "💳 <b>Реквизиты для пополнения</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Сумма: <b>{amount:,.2f} ₽</b>\n\n"
        "📱 Телефон: <code>+79495724176</code>\n"
        "🏦 Банк: <b>Т-Банк</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ После перевода отправьте чек в поддержку:\n"
        f"👉 @{SUPPORT_USERNAME}"
    )
    await message.answer(text, reply_markup=back_to_main())
    await state.clear()


# ========== ОТЗЫВЫ ==========
@router.callback_query(F.data.startswith("reviews_page_"))
async def reviews_page(callback: CallbackQuery):
    try:
        page = int(callback.data.replace("reviews_page_", ""))
    except ValueError:
        page = 0
    total_pages = (TOTAL_REVIEWS + REVIEWS_PER_PAGE - 1) // REVIEWS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    text = (
        "⭐ <b>Отзывы наших клиентов</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Всего отзывов: <b>{TOTAL_REVIEWS}</b>\n"
        f"📄 Страница: <b>{page + 1} / {total_pages}</b>\n\n"
        "Нажмите на отзыв, чтобы прочитать полностью 👇"
    )
    await safe_delete(callback.message)
    await callback.message.answer(text, reply_markup=reviews_keyboard(page))
    await callback.answer()


@router.callback_query(F.data.startswith("review_") & ~F.data.startswith("reviews_"))
async def review_click(callback: CallbackQuery):
    try:
        review_id = int(callback.data.replace("review_", ""))
    except ValueError:
        await callback.answer("Ошибка", show_alert=True)
        return
    review = get_review_by_id(review_id)
    if not review:
        await callback.answer("Отзыв не найден", show_alert=True)
        return
    stars = "⭐" * review["stars"]
    await callback.answer(f"{review['name']} | {stars}\n\n{review['text']}", show_alert=True)


@router.callback_query(F.data == "reviews_nop")
async def reviews_nop(callback: CallbackQuery):
    await callback.answer()


# ============================================================
#                    ПРОДАЖА КРИПТОВАЛЮТЫ
# ============================================================
@router.callback_query(F.data == "sell_crypto")
async def sell_crypto(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    prices = await get_crypto_prices()
    text = (
        "💸 <b>Продажа криптовалюты</b>\n\n"
        "📊 <b>Актуальные курсы</b>:\n\n"
        f"{build_crypto_text(prices, SELL_MULTIPLIER)}\n\n"
        "Выберите криптовалюту для продажи:"
    )
    try:
        photo = FSInputFile("images/crypto.png")
        await callback.message.answer_photo(photo, caption=text, reply_markup=crypto_list_sell())
    except FileNotFoundError:
        await callback.message.answer(text, reply_markup=crypto_list_sell())
    await callback.answer()


@router.callback_query(F.data.startswith("sell_select_"))
async def sell_select(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    currency = callback.data.replace("sell_select_", "")
    await state.update_data(currency=currency, direction="sell")
    await callback.message.answer(
        f"Вы выбрали <b>{COIN_NAMES.get(currency, currency)}</b>.\n\n"
        f"Введите количество криптовалюты, которое хотите продать (например, <code>0.001</code>):"
    )
    await state.set_state(SellStates.waiting_amount)
    await callback.answer()


@router.message(SellStates.waiting_amount)
async def sell_process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введите корректное число (например, <code>0.001</code>).")
        return

    data = await state.get_data()
    currency = data.get("currency", "")

    prices = await get_crypto_prices()
    price_usd = prices.get(currency, {}).get("usd", Decimal("0")) * Decimal(str(SELL_MULTIPLIER))
    price_rub = prices.get(currency, {}).get("rub", Decimal("0")) * Decimal(str(SELL_MULTIPLIER))
    total_usd = price_usd * Decimal(str(amount))
    total_rub = price_rub * Decimal(str(amount))

    if total_usd < Decimal(str(MIN_USD)) or total_rub < Decimal(str(MIN_RUB)):
        await message.answer(
            "⚠️ <b>Минимальная сумма продажи</b>\n\n"
            f"Вы пытаетесь продать <b>{amount} {currency}</b>, что составляет:\n"
            f"💵 ${total_usd:,.2f}\n💴 {total_rub:,.2f} ₽\n\n"
            f"❌ Минимум: <b>${MIN_USD}</b> или <b>{MIN_RUB} ₽</b>\n\n"
            f"Введите другое количество:"
        )
        return

    await state.update_data(amount=amount, total_rub=float(total_rub), total_usd=float(total_usd))

    try:
        photo = FSInputFile("images/dann.png")
        await message.answer_photo(
            photo,
            caption=(
                "📝 <b>Заполнение данных</b>\n\n"
                f"Отправьте адрес вашего кошелька <b>{currency}</b> "
                f"с которого поступит оплата."
            )
        )
    except FileNotFoundError:
        await message.answer(
            "📝 <b>Заполнение данных</b>\n\n"
            f"Отправьте адрес вашего кошелька <b>{currency}</b> "
            f"с которого поступит оплата."
        )

    await state.set_state(SellStates.waiting_address)


@router.message(SellStates.waiting_address)
async def sell_process_address(message: Message, state: FSMContext, bot: Bot):
    address = message.text.strip()
    if not address or len(address) < 10:
        await message.answer("❌ Адрес выглядит некорректным. Попробуйте снова.")
        return

    data = await state.get_data()
    currency = data.get("currency")
    amount = data.get("amount")
    total_rub = data.get("total_rub", 0)
    total_usd = data.get("total_usd", 0)
    user_id = message.from_user.id

    await state.update_data(address=address)

    order_number = generate_number()
    create_order(
        order_number=order_number,
        user_id=user_id,
        direction="sell",
        currency=currency,
        amount=amount,
        total_rub=total_rub,
        total_usd=total_usd,
        wallet_address=address,
        status="waiting_payment"
    )
    await state.update_data(order_number=order_number)

    await show_loading(message, 2)

    wallet_info = WALLETS.get(currency, {})
    wallet_address = wallet_info.get("address", "Не указан")
    network = wallet_info.get("network", "—")

    await state.set_state(SellStates.waiting_payment)

    payment_text = (
        f"💳 <b>Оплата</b>\n"
        f"🧾 Заказ: <b>{order_number}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"📤 Отправьте <b>{amount} {currency}</b>\n"
        f"🌐 Сеть: <b>{network}</b>\n"
        f"📍 Адрес:\n<code>{wallet_address}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Вы получите:</b>\n"
        f"   💵 ${total_usd:,.2f}\n"
        f"   💴 {total_rub:,.2f} ₽\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Ожидание поступления средств...\n"
        f"У вас есть <b>5 минут</b>.\n\n"
        f"🆘 Если оплата не поступит или возникнут проблемы — @{SUPPORT_USERNAME}."
    )

    if currency in AUTO_CHECK:
        await message.answer(payment_text, reply_markup=support_button())
        asyncio.create_task(
            check_sell_payment(user_id, currency, amount, address, bot, state, order_number)
        )
    else:
        await message.answer(payment_text, reply_markup=sell_paid_button())
        asyncio.create_task(check_sell_payment_manual(user_id, order_number, bot, state))


async def check_sell_payment(user_id, currency, amount, user_address, bot, state, order_number):
    start_time = datetime.now()
    wallet = WALLETS.get(currency, {}).get("address", "")

    if currency == "SOL":
        start_balance = await get_sol_balance(wallet)
    elif currency == "USDT_TRC20":
        start_balance = await get_trc20_balance(wallet)
    elif currency == "TON":
        start_balance = await get_ton_balance(wallet)
    else:
        start_balance = 0

    while datetime.now() - start_time < timedelta(seconds=PAYMENT_TIMEOUT):
        await asyncio.sleep(PAYMENT_CHECK_INTERVAL)
        try:
            if currency == "SOL":
                current = await get_sol_balance(wallet)
            elif currency == "USDT_TRC20":
                current = await get_trc20_balance(wallet)
            elif currency == "TON":
                current = await get_ton_balance(wallet)
            else:
                current = 0

            if current - start_balance >= float(amount):
                update_order_status(order_number, "completed")
                data = await state.get_data()
                total_rub = data.get("total_rub", 0)
                ref_id, bonus = credit_referral(user_id, total_rub)
                if ref_id:
                    try:
                        await bot.send_message(
                            ref_id,
                            f"💸 <b>Реферальный бонус!</b>\n\n💰 Начислено: <b>{bonus:,.2f} ₽</b>"
                        )
                    except Exception:
                        pass

                try:
                    loading_msg = await bot.send_message(user_id, "⌛")
                    await asyncio.sleep(2)
                    await loading_msg.delete()
                except Exception:
                    pass

                now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
                caption = (
                    "✅ <b>Чек об оплате</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🧾 Номер заказа: <code>{order_number}</code>\n"
                    f"📅 Дата: {now_str}\n"
                    f"💰 Сумма: <b>{amount} {currency}</b>\n"
                    f"📍 Адрес отправителя:\n<code>{user_address}</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"💬 <b>Для получения средств напишите в поддержку:</b>\n👉 @{SUPPORT_USERNAME}"
                )
                try:
                    photo = FSInputFile("images/check.png")
                    await bot.send_photo(user_id, photo, caption=caption)
                except FileNotFoundError:
                    await bot.send_message(user_id, caption)
                await state.clear()
                return
        except Exception as e:
            print(f"[SELL CHECK] Ошибка: {e}")

    update_order_status(order_number, "cancelled")
    await bot.send_message(
        user_id,
        f"⌛ <b>Оплата не поступила за 5 минут.</b>\n\n"
        f"🧾 Заказ <b>{order_number}</b> отменён.\n\n"
        f"Если вы отправили средства — напишите в поддержку: @{SUPPORT_USERNAME}",
        reply_markup=support_button()
    )
    await state.clear()


async def check_sell_payment_manual(user_id, order_number, bot, state):
    start_time = datetime.now()
    while datetime.now() - start_time < timedelta(seconds=PAYMENT_TIMEOUT):
        await asyncio.sleep(5)
        order = get_order(order_number)
        if order and order["status"] == "completed":
            return
    order = get_order(order_number)
    if order and order["status"] == "waiting_payment":
        update_order_status(order_number, "cancelled")
        await bot.send_message(
            user_id,
            f"⌛ <b>Оплата не поступила за 5 минут.</b>\n\n"
            f"🧾 Заказ <b>{order_number}</b> отменён.\n\n"
            f"Если вы отправили средства — напишите в поддержку: @{SUPPORT_USERNAME}",
            reply_markup=support_button()
        )
        await state.clear()


@router.callback_query(F.data == "sell_paid")
async def sell_paid(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await safe_delete(callback.message)
    data = await state.get_data()
    order_number = data.get("order_number")
    currency = data.get("currency")
    amount = data.get("amount")
    total_rub = data.get("total_rub", 0)
    total_usd = data.get("total_usd", 0)
    user_id = callback.from_user.id

    if order_number:
        update_order_status(order_number, "completed")

    ref_id, bonus = credit_referral(user_id, total_rub)
    if ref_id:
        try:
            await bot.send_message(
                ref_id,
                f"💸 <b>Реферальный бонус!</b>\n\n💰 Начислено: <b>{bonus:,.2f} ₽</b>"
            )
        except Exception:
            pass

    try:
        loading_msg = await bot.send_message(user_id, "⌛")
        await asyncio.sleep(2)
        await loading_msg.delete()
    except Exception:
        pass

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    caption = (
        "✅ <b>Чек об оплате</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🧾 Номер заказа: <code>{order_number}</code>\n"
        f"📅 Дата: {now_str}\n"
        f"💰 Сумма: <b>{amount} {currency}</b>\n"
        f"💵 ${total_usd:,.2f}\n"
        f"💴 {total_rub:,.2f} ₽\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💬 <b>Для получения средств напишите в поддержку:</b>\n👉 @{SUPPORT_USERNAME}"
    )
    try:
        photo = FSInputFile("images/check.png")
        await bot.send_photo(user_id, photo, caption=caption)
    except FileNotFoundError:
        await bot.send_message(user_id, caption)

    await state.clear()
    await callback.answer("Спасибо!")


# ============================================================
#                    ПОКУПКА TELEGRAM STARS
# ============================================================
@router.callback_query(F.data == "stars_shop")
async def stars_shop(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = ("Покупка Звезд Telegram! ⭐\n"
            "В честь ЖУТКОГО МЕСЯЦА скидки! 🎃\n\n"
            "🔥 Передача через Username - 1 рубль = 1 звезда 🔥\n"
            "🎁 Передача через подарки - 1.2 рубля = 1 звезда 🎁\n\n"
            "Звезды передаются в течении 3-х часов из за большой нагруженности!\n"
            "Выберите ниже способ передачи, от него будет зависеть курс: ⬇️")
    try:
        await callback.message.answer_photo(FSInputFile("images/zvezdi.png"), caption=text, reply_markup=stars_delivery_keyboard())
    except FileNotFoundError:
        await callback.message.answer(text, reply_markup=stars_delivery_keyboard())
    await callback.answer()


@router.callback_query(F.data.in_({"stars_method_username", "stars_method_gifts"}))
async def stars_choose_method(callback: CallbackQuery, state: FSMContext):
    method = "username" if callback.data.endswith("username") else "gifts"
    rate = 1.0 if method == "username" else 1.2
    await state.update_data(stars_method=method, stars_rate=rate)
    await callback.answer()
    loading = await callback.message.answer("⌛")
    await asyncio.sleep(2)
    await safe_delete(loading)
    await callback.message.answer(
        "Введите количество Telegram Stars, которое хотите купить "
        "(целое число, минимум 1000):"
    )
    await state.set_state(StarsStates.waiting_amount)


@router.message(StarsStates.waiting_amount)
async def stars_amount(message: Message, state: FSMContext):
    try:
        amount = int((message.text or "").strip())
        if amount < 1000 or amount > 1000000:
            raise ValueError
    except ValueError:
        await message.answer("Минимальный заказ — 1000 звёзд. Введите целое число от 1000 до 1 000 000.")
        return
    data = await state.get_data()
    total = amount * float(data["stars_rate"])
    await state.update_data(stars_amount=amount, stars_total=total)
    await message.answer(f"Укажите Telegram username получателя (например, @username):")
    await state.set_state(StarsStates.waiting_username)


@router.message(StarsStates.waiting_username)
async def stars_username(message: Message, state: FSMContext):
    username = (message.text or "").strip().lstrip("@")
    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", username):
        await message.answer("Введите корректный Telegram username (5–32 символа, латиница, цифры и _).")
        return
    await state.update_data(stars_username="@" + username)
    data = await state.get_data()
    order_number = generate_number()
    create_order(order_number=order_number, user_id=message.from_user.id, direction="buy",
                 currency="TG_STARS_" + data["stars_method"].upper(), amount=data["stars_amount"],
                 total_rub=data["stars_total"], total_usd=0, wallet_address="@" + username,
                 status="waiting_payment")
    await state.update_data(stars_order=order_number)
    loading = await message.answer("⌛")
    await asyncio.sleep(2)
    try:
        await loading.delete()
    except Exception:
        pass
    order_text = (
        f"🧾 <b>Заказ Telegram Stars {order_number}</b>\n"
        f"⭐️ Количество: <b>{data['stars_amount']} звёзд</b>\n"
        f"📨 Получатель: <b>@{username}</b>\n"
        f"🚚 Передача: <b>{data['stars_method']}</b>\n"
        f"💰 К оплате: <b>{data['stars_total']:.2f} ₽</b>\n\n"
        "Выберите способ оплаты:"
    )
    oplata_path = Path(__file__).resolve().parent / "images" / "oplata.png"
    if oplata_path.is_file():
        await message.answer_photo(
            photo=FSInputFile(str(oplata_path)),
            caption=order_text,
            parse_mode="HTML",
            reply_markup=payment_methods()
        )
    else:
        await message.answer(
            "⚠️ Не найден файл images/oplata.png.\n\n" + order_text,
            parse_mode="HTML",
            reply_markup=payment_methods()
        )
    await state.set_state(StarsStates.waiting_payment)


@router.callback_query(F.data == "stars_paid")
async def stars_paid(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    order_number = data.get("stars_order")
    order = get_order(order_number) if order_number else None
    if order is None:
        for candidate in get_user_orders(callback.from_user.id, limit=50):
            currency = str(candidate["currency"] or "")
            if (candidate["direction"] == "buy" and currency.startswith("TG_STARS_")
                    and candidate["status"] in ("waiting_payment", "processing")):
                order, order_number = candidate, candidate["order_number"]
                break
    if order is None or int(order["user_id"]) != callback.from_user.id:
        await callback.answer("Не удалось найти ваш заказ Telegram Stars. Создайте заказ заново.", show_alert=True)
        return
    stars_amount = int(float(order["amount"] or 0))
    total_rub = float(order["total_rub"] or 0)
    recipient = order["wallet_address"] or data.get("stars_username") or "—"
    method = order["payment_method"] or data.get("payment_method") or "—"
    update_order_status(order_number, "processing")
    caption = build_payment_receipt(
        order_number, f"{stars_amount} звёзд Telegram", total_usd=None, total_rub=total_rub,
        payment_method=method, recipient_label="Username получателя", recipient=recipient,
        support_text="Для получения звёзд отправьте чек в поддержку"
    )
    await send_payment_receipt(bot, callback.from_user.id, caption)
    await state.clear()
    await callback.answer("Чек отправлен")


# ============================================================
#                    ПОКУПКА КРИПТОВАЛЮТЫ
# ============================================================
@router.callback_query(F.data == "buy_crypto")
async def buy_crypto(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    prices = await get_crypto_prices()
    text = (
        "🛒 <b>Покупка криптовалюты</b>\n\n"
        "📊 <b>Актуальные курсы</b>:\n\n"
        f"{build_crypto_text(prices, BUY_MULTIPLIER)}\n\n"
        "Выберите криптовалюту для покупки:"
    )
    try:
        photo = FSInputFile("images/crypto.png")
        await callback.message.answer_photo(photo, caption=text, reply_markup=crypto_list_buy())
    except FileNotFoundError:
        await callback.message.answer(text, reply_markup=crypto_list_buy())
    await callback.answer()


@router.callback_query(F.data.startswith("buy_select_"))
async def buy_select(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    currency = callback.data.replace("buy_select_", "")
    await state.update_data(currency=currency, direction="buy")
    await callback.message.answer(
        f"Вы выбрали <b>{COIN_NAMES.get(currency, currency)}</b>.\n\n"
        f"Введите количество криптовалюты, которое хотите купить (например, <code>0.5</code>):"
    )
    await state.set_state(BuyStates.waiting_amount)
    await callback.answer()


@router.message(BuyStates.waiting_amount)
async def buy_process_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("❌ Введите корректное число (например, <code>0.5</code>).")
        return

    data = await state.get_data()
    currency = data.get("currency", "")

    prices = await get_crypto_prices()
    price_usd = prices.get(currency, {}).get("usd", Decimal("0")) * Decimal(str(BUY_MULTIPLIER))
    price_rub = prices.get(currency, {}).get("rub", Decimal("0")) * Decimal(str(BUY_MULTIPLIER))
    total_usd = price_usd * Decimal(str(amount))
    total_rub = price_rub * Decimal(str(amount))

    if total_usd < Decimal(str(MIN_USD)) or total_rub < Decimal(str(MIN_RUB)):
        await message.answer(
            "⚠️ <b>Минимальная сумма покупки</b>\n\n"
            f"Вы пытаетесь купить <b>{amount} {currency}</b>, что составляет:\n"
            f"💵 ${total_usd:,.2f}\n💴 {total_rub:,.2f} ₽\n\n"
            f"❌ Минимум: <b>${MIN_USD}</b> или <b>{MIN_RUB} ₽</b>\n\n"
            f"Введите другое количество:"
        )
        return

    await state.update_data(
        amount=amount,
        total_usd=float(total_usd),
        total_rub=float(total_rub),
        price_usd=float(price_usd),
        price_rub=float(price_rub)
    )

    try:
        photo = FSInputFile("images/dann.png")
        await message.answer_photo(
            photo,
            caption=(
                "📝 <b>Заполнение данных</b>\n\n"
                f"Отправьте адрес вашего кошелька <b>{currency}</b>, "
                f"на который вы хотите получить криптовалюту."
            )
        )
    except FileNotFoundError:
        await message.answer(
            "📝 <b>Заполнение данных</b>\n\n"
            f"Отправьте адрес вашего кошелька <b>{currency}</b>."
        )

    await state.set_state(BuyStates.waiting_address)


@router.message(BuyStates.waiting_address)
async def buy_process_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if not address or len(address) < 10:
        await message.answer("❌ Адрес выглядит некорректным. Попробуйте снова.")
        return

    await state.update_data(address=address)
    data = await state.get_data()
    currency = data.get("currency")
    amount = data.get("amount")
    total_usd = data.get("total_usd")
    total_rub = data.get("total_rub")

    order_number = generate_number()
    user_id = message.from_user.id

    create_order(
        order_number=order_number,
        user_id=user_id,
        direction="buy",
        currency=currency,
        amount=amount,
        total_rub=total_rub,
        total_usd=total_usd,
        wallet_address=address,
        status="waiting_data"
    )
    await state.update_data(order_number=order_number)

    text = (
        "💳 <b>Выбор способа оплаты</b>\n"
        f"🧾 Заказ: <b>{order_number}</b>\n\n"
        f"🧾 К покупке: <b>{amount} {currency}</b>\n"
        f"💵 ${total_usd:,.2f}\n💴 {total_rub:,.2f} ₽\n\n"
        "Выберите удобный способ оплаты:"
    )
    oplata_path = Path(__file__).resolve().parent / "images" / "oplata.png"
    if oplata_path.is_file():
        await message.answer_photo(
            photo=FSInputFile(str(oplata_path)),
            caption=text,
            parse_mode="HTML",
            reply_markup=payment_methods()
        )
    else:
        await message.answer(
            "⚠️ Не найден файл images/oplata.png.\n\n" + text,
            parse_mode="HTML",
            reply_markup=payment_methods()
        )
    await state.set_state(BuyStates.waiting_payment_method)


@router.callback_query(F.data.startswith("pay_"))
async def buy_process_payment(callback: CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    method = callback.data.replace("pay_", "")
    await state.update_data(payment_method=method)
    state_data = await state.get_data()
    if state_data.get("stars_order"):
        method_info = PAYMENT_DETAILS.get(method, {})
        update_order_data(state_data["stars_order"], payment_method=method_info.get("title", method))
        await callback.answer()
        loading = await callback.message.answer("⌛")
        await asyncio.sleep(2)
        try:
            await loading.delete()
        except Exception:
            pass

        payment_text = (
            f"💳 <b>Оплата заказа Telegram Stars {state_data['stars_order']}</b>\n"
            f"⭐ Количество: {state_data['stars_amount']}\n"
            f"📨 Получатель: {state_data['stars_username']}\n"
            f"💰 К оплате: {state_data['stars_total']:.2f} ₽\n\n"
            f"<b>Реквизиты:</b>\n{method_info.get('info', 'Реквизиты не указаны.')}\n\n"
            "После оплаты нажмите «Я оплатил»."
        )
        clock_path = Path(__file__).resolve().parent / "images" / "clock.png"
        if clock_path.is_file():
            await callback.message.answer_photo(
                FSInputFile(str(clock_path)),
                caption=payment_text,
                parse_mode="HTML",
                reply_markup=stars_payment_confirm_keyboard()
            )
        else:
            await callback.message.answer(
                "⚠️ Не найден файл images/clock.png.\n\n" + payment_text,
                parse_mode="HTML",
                reply_markup=stars_payment_confirm_keyboard()
            )
        await state.set_state(StarsStates.waiting_payment_confirm)
        return

    data = await state.get_data()
    currency = data.get("currency")
    amount = data.get("amount")
    total_usd = data.get("total_usd")
    total_rub = data.get("total_rub")
    address = data.get("address")
    order_number = data.get("order_number")

    if order_number:
        update_order_data(order_number, payment_method=method, status="waiting_payment")

    loading_msg = await callback.message.answer("⌛")
    await asyncio.sleep(2)
    try:
        await loading_msg.delete()
    except Exception:
        pass

    method_info = PAYMENT_DETAILS.get(method, {})
    method_title = method_info.get("title", method)
    method_text = method_info.get("info", "Реквизиты не указаны.")

    text = (
        f"💳 <b>Оплата через {method_title}</b>\n"
        f"🧾 Заказ: <b>{order_number}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🛒 Покупка: <b>{amount} {COIN_NAMES.get(currency, currency)}</b>\n"
        f"📍 Ваш кошелёк для получения:\n<code>{address}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>К оплате:</b>\n"
        f"   💵 ${total_usd:,.2f}\n"
        f"   💴 {total_rub:,.2f} ₽\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Реквизиты:</b>\n{method_text}\n\n"
        "⚠️ После оплаты нажмите кнопку «✅ Я оплатил»."
    )

    await callback.message.answer(text, reply_markup=paid_button())
    await state.set_state(BuyStates.waiting_payment_confirm)
    await callback.answer()


@router.callback_query(F.data == "buy_paid")
async def buy_paid(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await safe_delete(callback.message)
    data = await state.get_data()
    order_number = data.get("order_number")
    order = get_order(order_number) if order_number else None
    if order is None or int(order["user_id"]) != callback.from_user.id:
        await callback.answer("Не удалось найти ваш заказ. Откройте покупку заново.", show_alert=True)
        return
    currency = str(order["currency"] or data.get("currency") or "")
    amount = order["amount"] if order["amount"] is not None else data.get("amount")
    total_rub = float(order["total_rub"] or data.get("total_rub") or 0)
    total_usd = float(order["total_usd"] or data.get("total_usd") or 0)
    address = order["wallet_address"] or data.get("address") or "—"
    method = order["payment_method"] or data.get("payment_method") or "—"
    # User-submitted payment is pending verification, not a completed transaction.
    update_order_status(order_number, "processing")
    caption = build_payment_receipt(
        order_number, f"{amount} {COIN_NAMES.get(currency, currency)}",
        total_usd=total_usd if total_usd > 0 else None, total_rub=total_rub,
        payment_method=method, recipient_label="Кошелёк получателя", recipient=address,
        support_text="Для получения криптовалюты напишите в поддержку"
    )
    await send_payment_receipt(bot, callback.from_user.id, caption)
    await state.clear()
    await callback.answer("Чек отправлен на проверку")
