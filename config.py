# ========== ТОКЕН БОТА ==========
BOT_TOKEN = "8007003546:AAHia0symgO0YU3RK3q8qpeH8I_3D56S3gs"

# ========== ПОДДЕРЖКА ==========
SUPPORT_USERNAME = "cryptoinversesup"

# ========== БОТ ==========
BOT_USERNAME = "CryptoInverseBot"

# ========== КОШЕЛЬКИ ДЛЯ ПРИЁМА (продажа крипты) ==========
WALLETS = {
    "SOL":        {"address": "AThEtgivdpE2bGtgE21xXLhmyWoE9kqxfJhHSBrvZdzG", "network": "Solana"},
    "TRX":        {"address": "TYB215Cs6d1mkgKG69njSFmRcaS3cDWwmj",            "network": "Tron"},
    "USDT_TRC20": {"address": "TYB215Cs6d1mkgKG69njSFmRcaS3cDWwmj",            "network": "Tron (TRC20)"},
    "TON":        {"address": "UQDmeq7F1sfl4lyBQOEoPbtZEiCxAamtiGZOg-4t3IotjTMW", "network": "TON"},
    "ETH":        {"address": "0x24Fc474493C7C4876F2CCfDdeD975F20BeB13c04",    "network": "Ethereum (ERC20)"},
    "BNB":        {"address": "0x24Fc474493C7C4876F2CCfDdeD975F20BeB13c04",    "network": "BNB Smart Chain (BEP20)"},
    "HYPE":       {"address": "0x24Fc474493C7C4876F2CCfDdeD975F20BeB13c04",    "network": "HyperLiquid"},
    "BASE":       {"address": "0x24Fc474493C7C4876F2CCfDdeD975F20BeB13c04",    "network": "Base"},
    "ARB":        {"address": "0x24Fc474493C7C4876F2CCfDdeD975F20BeB13c04",    "network": "Arbitrum"},
    "MATIC":      {"address": "0x24Fc474493C7C4876F2CCfDdeD975F20BeB13c04",    "network": "Polygon"},
}

# ========== НАЗВАНИЯ МОНЕТ ==========
COIN_NAMES = {
    "SOL": "Solana",
    "TRX": "Tron",
    "USDT_TRC20": "USDT (TRC20)",
    "TON": "Toncoin",
    "ETH": "Ethereum",
    "BNB": "BNB",
    "HYPE": "HyperLiquid",
    "BASE": "Base",
    "ARB": "Arbitrum",
    "MATIC": "Polygon (MATIC)",
}

# ========== РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ (покупка + пополнение) ==========
PAYMENT_DETAILS = {
    "СБП": {
        "title": "🟢 СБП (Система быстрых платежей)",
        "info": "📱 Телефон: <code>+79495724176</code>\n🏦 Банк: Т-Банк"
    },
    "SberPay": {
        "title": "🟨 Т-Банк (T-Pay)",
        "info": "📱 Телефон: <code>+79495724176</code>\n🏦 Банк: Т-Банк"
    },
    "Карта": {
        "title": "💳 Банковская карта",
        "info": "📱 Телефон для перевода: <code>+79495724176</code>\n🏦 Банк: Т-Банк"
    },
    "Криптовалюта": {
        "title": "🪙 Криптовалюта",
        "info": (
            "USDT (TRC20): <code>TYB215Cs6d1mkgKG69njSFmRcaS3cDWwmj</code>\n"
            "SOL: <code>AThEtgivdpE2bGtgE21xXLhmyWoE9kqxfJhHSBrvZdzG</code>\n"
            "ETH/BNB/ARB/MATIC/BASE: <code>0x24Fc474493C7C4876F2CCfDdeD975F20BeB13c04</code>"
        )
    },
}

# ========== ВРЕМЕННЫЕ ИНТЕРВАЛЫ ==========
PRICE_UPDATE_INTERVAL = 300
PAYMENT_TIMEOUT = 300
PAYMENT_CHECK_INTERVAL = 10

# ========== МИНИМАЛЬНАЯ СУММА ==========
MIN_USD = 10
MIN_RUB = 1000

# ========== НАЦЕНКИ И СКИДКИ ==========
SELL_MULTIPLIER = 0.85
BUY_MULTIPLIER = 0.95

# ========== РЕФЕРАЛЬНАЯ СИСТЕМА ==========
REFERRAL_SIGNUP_BONUS = 15
REFERRAL_BONUS_PERCENT = 0.05

# ========== ОТЗЫВЫ ==========
REVIEWS_PER_PAGE = 10

# Укажи числовые Telegram ID администраторов, которым разрешена /broadcast.
ADMIN_IDS = set()

# Telegram usernames администраторов (без символа @), сравнение без учёта регистра.
ADMIN_USERNAMES = {"a111mp180"}
