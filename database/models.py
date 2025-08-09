from asyncio.log import logger
import aiosqlite
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from config import config
import os
import asyncio

async def schedule_order_deletion(order_id: int, db_path: str):
    await asyncio.sleep(1800)
    try:
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('''
                DELETE FROM orders
                WHERE id = ? AND status = 'waiting'
            ''', (order_id,))
            await conn.commit()
        logger.info(f"Order {order_id} deleted after 30 minutes")
    except Exception as e:
        logger.error(f"Error deleting order {order_id}: {e}")

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def get_commission_percentage(self):
        return await self.get_setting("commission_percentage", float(os.getenv('COMMISSION_PERCENT', '20.0')))

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone_number TEXT,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_blocked BOOLEAN DEFAULT FALSE,
                    referral_code TEXT,
                    referred_by INTEGER,
                    total_operations INTEGER DEFAULT 0,
                    total_amount REAL DEFAULT 0
                )
            ''')
            await self._migrate_users_table(db)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    onlypays_id TEXT,
                    pspware_id TEXT,
                    nicepay_id TEXT,
                    greengo_id TEXT,
                    amount_rub REAL NOT NULL,
                    amount_btc REAL,
                    btc_address TEXT NOT NULL,
                    rate REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    payment_type TEXT NOT NULL,
                    status TEXT DEFAULT 'waiting',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    requisites TEXT,
                    is_problematic BOOLEAN DEFAULT FALSE,
                    operator_notes TEXT,
                    personal_id TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS captcha_sessions (
                    user_id INTEGER PRIMARY KEY,
                    answer TEXT NOT NULL,
                    attempts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS referral_bonuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            await db.commit()

    async def _migrate_users_table(self, db):
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        if 'referral_count' not in column_names:
            await db.execute('ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0')
            await db.commit()

    async def add_user(self, user_id: int, username: str = None,
                      first_name: str = None, last_name: str = None) -> bool:
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''
                    INSERT INTO users (user_id, username, first_name, last_name)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, username, first_name, last_name))
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                return False

    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_user(self, user_id: int, **kwargs):
        if not kwargs:
            return
        fields = ', '.join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values()) + [user_id]
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f'UPDATE users SET {fields} WHERE user_id = ?', values)
            await db.commit()

    async def create_order(self, user_id: int, amount_rub: float, amount_btc: float,
                          btc_address: str, rate: float, total_amount: float,
                          payment_type: str) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO orders (user_id, amount_rub, amount_btc, btc_address, rate, total_amount, payment_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, amount_rub, amount_btc, btc_address, rate, total_amount, payment_type))
            await db.commit()
            order_id = cursor.lastrowid
            asyncio.create_task(schedule_order_deletion(order_id, self.db_path))
            return order_id

    async def get_order_total_amount(self, order_id: int) -> Optional[float]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT total_amount FROM orders WHERE id = ?', (order_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
                return None

    async def get_order(self, order_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM orders WHERE id = ?', (order_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def save_review(self, user_id: int, text: str):
        async with aiosqlite.connect(self.db_path) as db:
            current_time = datetime.now().isoformat()
            cursor = await db.execute(
                'INSERT INTO reviews (user_id, text, created_at, status) VALUES (?, ?, ?, ?)',
                (user_id, text, current_time, 'pending')
            )
            await db.commit()
            return cursor.lastrowid

    async def get_last_review_time(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT created_at FROM reviews WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return datetime.fromisoformat(row[0])
                return None

    async def update_review_status(self, review_id: int, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE reviews SET status = ? WHERE id = ?',
                (status, review_id)
            )
            await db.commit()

    async def update_order(self, order_id: int, **kwargs):
        if not kwargs:
            return
        allowed_fields = [
            'onlypays_id', 'pspware_id', 'nicepay_id', 'greengo_id', 'status', 'requisites',
            'personal_id', 'received_sum', 'note', 'operator_notes',
            'btc_address', 'completed_at', 'is_problematic'
        ]
        set_clause = []
        values = []
        for field, value in kwargs.items():
            if field in allowed_fields:
                set_clause.append(f"{field} = ?")
                values.append(value)
            else:
                logger.warning(f"Attempt to update forbidden field '{field}' in orders table ignored")
        if set_clause:
            values.append(order_id)
            query = f"UPDATE orders SET {', '.join(set_clause)} WHERE id = ?"
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(query, tuple(values))
                await db.commit()

    async def init_turnover_db(self):
        central_db_path = config.CENTRAL_DB_PATH
        async with aiosqlite.connect(central_db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS mirror_turnover (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mirror_id TEXT NOT NULL,
                    order_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await db.commit()
            logger.info(f"Turnover database initialized for mirror: {config.MIRROR_ID}")

    async def add_turnover_record(self, order_id: int, user_id: int, amount: float, status: str):
        central_db_path = config.CENTRAL_DB_PATH
        mirror_id = config.MIRROR_ID
        try:
            async with aiosqlite.connect(central_db_path) as db:
                await db.execute('''
                    INSERT INTO mirror_turnover (mirror_id, order_id, user_id, amount, status)
                    VALUES (?, ?, ?, ?, ?)
                ''', (mirror_id, order_id, user_id, amount, status))
                await db.commit()
                logger.info(f"Turnover recorded: {mirror_id} - Order {order_id} - {amount} RUB - Status: {status}")
        except Exception as e:
            logger.error(f"Failed to record turnover: {e}")

    async def get_total_turnover_by_mirror(self, mirror_id: str = None):
        central_db_path = config.CENTRAL_DB_PATH
        try:
            async with aiosqlite.connect(central_db_path) as db:
                if mirror_id:
                    query = '''
                        SELECT SUM(amount) as total, COUNT(*) as orders
                        FROM mirror_turnover
                        WHERE mirror_id = ? AND status = 'paid'
                    '''
                    params = (mirror_id,)
                else:
                    query = '''
                        SELECT SUM(amount) as total, COUNT(*) as orders
                        FROM mirror_turnover
                        WHERE status = 'paid'
                    '''
                    params = ()
                async with db.execute(query, params) as cursor:
                    result = await cursor.fetchone()
                    return {
                        'total_amount': result[0] if result[0] else 0,
                        'total_orders': result[1] if result[1] else 0
                    }
        except Exception as e:
            logger.error(f"Error getting turnover: {e}")
            return {'total_amount': 0, 'total_orders': 0}

    async def get_all_mirrors_turnover(self):
        central_db_path = config.CENTRAL_DB_PATH
        try:
            async with aiosqlite.connect(central_db_path) as db:
                db.row_factory = aiosqlite.Row
                query = '''
                    SELECT mirror_id, SUM(amount) as total, COUNT(*) as orders
                    FROM mirror_turnover
                    WHERE status = 'paid'
                    GROUP BY mirror_id
                    ORDER BY total DESC
                '''
                async with db.execute(query) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting mirrors turnover: {e}")
            return []

    async def get_turnover_by_period(self, days: int, mirror_id: str = None):
        central_db_path = config.CENTRAL_DB_PATH
        try:
            async with aiosqlite.connect(central_db_path) as db:
                if mirror_id:
                    query = '''
                        SELECT SUM(amount) as total, COUNT(*) as orders
                        FROM mirror_turnover
                        WHERE mirror_id = ? AND status = 'paid'
                        AND created_at >= datetime('now', '-{} days')
                    '''.format(days)
                    params = (mirror_id,)
                else:
                    query = '''
                        SELECT SUM(amount) as total, COUNT(*) as orders
                        FROM mirror_turnover
                        WHERE status = 'paid'
                        AND created_at >= datetime('now', '-{} days')
                    '''.format(days)
                    params = ()
                async with db.execute(query, params) as cursor:
                    result = await cursor.fetchone()
                    return {
                        'total_amount': result[0] if result[0] else 0,
                        'total_orders': result[1] if result[1] else 0
                    }
        except Exception as e:
            logger.error(f"Error getting period turnover: {e}")
            return {'total_amount': 0, 'total_orders': 0}

    async def mark_order_as_paid(self, order_id: int):
        try:
            await self.update_order(order_id, status='paid_by_client')
            order = await self.get_order(order_id)
            if order:
                await self.add_turnover_record(
                    order_id=order_id,
                    user_id=order['user_id'],
                    amount=order['total_amount'],
                    status="paid"
                )
                logger.info(f"Order {order_id} marked as paid and recorded in turnover")
        except Exception as e:
            logger.error(f"Error marking order as paid: {e}")

    async def get_user_orders(self, user_id: int, limit: int = 5) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?
            ''', (user_id, limit)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_setting(self, key: str, default: Any = None) -> Any:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT value FROM settings WHERE key = ?', (key,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    try:
                        return json.loads(row[0])
                    except:
                        return row[0]
                return default

    async def set_setting(self, key: str, value: Any):
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        else:
            value = str(value)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)
            ''', (key, value))
            await db.commit()

    async def get_all_users(self) -> List[int]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT user_id FROM users WHERE is_blocked = FALSE') as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def create_captcha_session(self, user_id: int, answer: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO captcha_sessions (user_id, answer, attempts)
                VALUES (?, ?, 0)
            ''', (user_id, answer))
            await db.commit()

    async def get_captcha_session(self, user_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM captcha_sessions WHERE user_id = ?', (user_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def delete_captcha_session(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM captcha_sessions WHERE user_id = ?', (user_id,))
            await db.commit()

    async def update_referral_count(self, user_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            try:
                async with db.execute(
                    'SELECT COUNT(*) FROM users WHERE referred_by = ?',
                    (user_id,)
                ) as cursor:
                    count = (await cursor.fetchone())[0]
                    logger.info(f"Referral bonus for user {user_id}")
                    await db.execute(
                        'UPDATE users SET referral_count = ? WHERE user_id = ?',
                        (count, user_id)
                    )
                    await db.commit()
                    return count
            except:
                return 0

    async def get_referral_stats(self, user_id: int):
        try:
            query1 = "SELECT COUNT(*) as count FROM users WHERE referred_by = ?"
            result1 = await self.execute_query(query1, (user_id,))
            referral_count = 0
            if result1 and len(result1) > 0:
                referral_count = result1[0]['count'] if 'count' in result1[0] else result1[0][0]
            referral_balance = 0
            return {
                'referral_count': referral_count,
                'referral_balance': referral_balance
            }
        except Exception as e:
            logger.error(f"Get referral stats error: {e}")
            return {
                'referral_count': 0,
                'referral_balance': 0
            }

    async def add_referral_bonus(self, user_id: int, amount: float):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR IGNORE INTO referral_bonuses
                (user_id, amount, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, amount))
            await db.commit()

    async def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                await db.commit()
                return [dict(row) for row in rows]

    async def get_statistics(self) -> Dict:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute('SELECT COUNT(*) FROM users') as cursor:
                total_users = (await cursor.fetchone())[0]
            async with db.execute('SELECT COUNT(*) FROM orders') as cursor:
                total_orders = (await cursor.fetchone())[0]
            async with db.execute('SELECT COUNT(*) FROM orders WHERE status = "completed"') as cursor:
                completed_orders = (await cursor.fetchone())[0]
            async with db.execute('SELECT SUM(total_amount) FROM orders WHERE status = "completed"') as cursor:
                total_volume = (await cursor.fetchone())[0] or 0
            async with db.execute('SELECT COUNT(*) FROM orders WHERE DATE(created_at) = DATE("now")') as cursor:
                today_orders = (await cursor.fetchone())[0]
            async with db.execute('SELECT SUM(total_amount) FROM orders WHERE DATE(created_at) = DATE("now") AND status = "completed"') as cursor:
                today_volume = (await cursor.fetchone())[0] or 0
            completion_rate = (completed_orders / total_orders * 100) if total_orders > 0 else 0
            return {
                'total_users': total_users,
                'total_orders': total_orders,
                'completed_orders': completed_orders,
                'total_volume': total_volume,
                'today_orders': today_orders,
                'today_volume': today_volume,
                'completion_rate': completion_rate
            }

    async def is_chat_admin(self, chat_id: int, user_id: int) -> bool:
        try:
            admin_chats = [config.ADMIN_CHAT_ID, config.OPERATOR_CHAT_ID]
            return chat_id in admin_chats and await self.has_admin_rights(user_id)
        except:
            return False

    async def has_admin_rights(self, user_id: int) -> bool:
        if user_id == config.ADMIN_CHAT_ID:
            return True
        admin_users = await self.get_setting("admin_users", [])
        operator_users = await self.get_setting("operator_users", [])
        return user_id in admin_users or user_id in operator_users

    async def add_admin_chat(self, chat_id: int, chat_title: str = ""):
        admin_chats = await self.get_setting("admin_chats", [])
        if chat_id not in admin_chats:
            admin_chats.append(chat_id)
            await self.set_setting("admin_chats", admin_chats)
            await self.set_setting(f"chat_{chat_id}_title", chat_title)

    async def get_review(self, review_id: int) -> Optional[Dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM reviews WHERE id = ?', (review_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
