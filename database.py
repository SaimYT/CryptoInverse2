import sqlite3
from contextlib import closing

DB_NAME = "bot.db"


def init_db():
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    referrer_id INTEGER,
                    balance_rub REAL DEFAULT 0,
                    balance_usd REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    order_number TEXT PRIMARY KEY,
                    user_id INTEGER,
                    direction TEXT,
                    currency TEXT,
                    amount REAL,
                    total_rub REAL,
                    total_usd REAL,
                    wallet_address TEXT,
                    payment_method TEXT,
                    status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur = conn.execute("PRAGMA table_info(users)")
            cols = [row[1] for row in cur.fetchall()]
            if "balance_rub" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN balance_rub REAL DEFAULT 0")
            if "balance_usd" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN balance_usd REAL DEFAULT 0")


# ========== ПОЛЬЗОВАТЕЛИ ==========
def get_user(user_id: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone()


def create_user(user_id: int, username: str = "", referrer_id: int = None) -> bool:
    existing = get_user(user_id)
    if existing:
        with closing(sqlite3.connect(DB_NAME)) as conn:
            with conn:
                conn.execute(
                    "UPDATE users SET username = ? WHERE user_id = ?",
                    (username, user_id)
                )
        return False

    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                "INSERT INTO users (user_id, username, referrer_id) VALUES (?, ?, ?)",
                (user_id, username, referrer_id)
            )
    return True


def count_referrals(user_id: int) -> int:
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.execute(
            "SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,)
        )
        return cur.fetchone()[0]


def get_referrals(user_id: int):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT user_id, username FROM users WHERE referrer_id = ?",
            (user_id,)
        )
        return cur.fetchall()


def get_referrer(user_id: int):
    user = get_user(user_id)
    if user and user["referrer_id"]:
        return user["referrer_id"]
    return None


def add_balance(user_id: int, amount_rub: float = 0, amount_usd: float = 0):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                "UPDATE users SET balance_rub = balance_rub + ?, balance_usd = balance_usd + ? WHERE user_id = ?",
                (amount_rub, amount_usd, user_id)
            )


def get_balance(user_id: int):
    user = get_user(user_id)
    if user:
        return (user["balance_rub"] or 0, user["balance_usd"] or 0)
    return (0, 0)


# ========== ЗАКАЗЫ ==========
def create_order(
    order_number: str,
    user_id: int,
    direction: str,
    currency: str,
    amount: float,
    total_rub: float = 0,
    total_usd: float = 0,
    wallet_address: str = "",
    payment_method: str = "",
    status: str = "waiting_payment"
):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO orders
                (order_number, user_id, direction, currency, amount, total_rub, total_usd,
                 wallet_address, payment_method, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_number, user_id, direction, currency, amount,
                total_rub, total_usd, wallet_address, payment_method, status
            ))


def update_order_status(order_number: str, status: str):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(
                "UPDATE orders SET status = ? WHERE order_number = ?",
                (status, order_number)
            )


def update_order_data(order_number: str, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [order_number]
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute(f"UPDATE orders SET {fields} WHERE order_number = ?", values)


def get_order(order_number: str):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM orders WHERE order_number = ?", (order_number,)
        )
        return cur.fetchone()


def get_user_orders(user_id: int, limit: int = 20):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return cur.fetchall()


def delete_order(order_number: str):
    with closing(sqlite3.connect(DB_NAME)) as conn:
        with conn:
            conn.execute("DELETE FROM orders WHERE order_number = ?", (order_number,))

def get_all_user_ids():
    """Возвращает Telegram ID пользователей для рассылки."""
    with closing(sqlite3.connect(DB_NAME)) as conn:
        cur = conn.execute("SELECT user_id FROM users")
        return [row[0] for row in cur.fetchall()]
