#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ربات فروشگاه RedHotMafia - نسخه نهایی
با قابلیت‌های:
- تحویل خودکار لایسنس
- گارانتی بازگشت وجه
- 10 سکه رایگان بعد عضویت در کانال
- تایمر خودکار برای تایید پرداخت
- کارت‌های گرافیکی در جدول رتبه‌بندی
- رفع تمامی خطاها
- راهنمای کامل تمام بخش‌ها
"""

import logging
import os
import uuid
import random
import re
import hashlib
import aiosqlite
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont
import textwrap
import asyncio
import io
import math

from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    ReplyKeyboardRemove
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# *********************** تنظیمات اولیه ***********************
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# *********************** ثابت‌های برنامه ***********************
(
    SELECTING_ACTION,
    CONFIRM_PAYMENT,
    ADMIN_ACTIONS,
    SUPPORT_CHAT,
    VIEWING_ORDERS,
    REGISTER_EMAIL,
    REGISTER_PASSWORD,
    LOGIN_EMAIL,
    LOGIN_PASSWORD,
    WALLET_ACTIONS,
    REFERRAL_MENU,
    CHANNEL_CHECK,
    AVATAR_SELECTION,
    WHEEL_OF_FORTUNE,
    ADMIN_ADD_COINS,
    ADMIN_MANAGE_PRODUCTS,
) = range(16)

DB_PATH = "data/orders.db"
STATS_DB_PATH = "data/stats.db"
USERS_DB_PATH = "data/users.db"
WALLET_DB_PATH = "data/wallet.db"
COINS_DB_PATH = "data/coins.db"

# فونت‌های مورد استفاده
try:
    MONO_FONT = ImageFont.truetype("DejaVuSansMono.ttf", 14)
    TITLE_FONT = ImageFont.truetype("DejaVuSansMono-Bold.ttf", 18)
    DIGITAL_FONT = ImageFont.truetype("digital.ttf", 24) if os.path.exists("digital.ttf") else None
except:
    MONO_FONT = ImageFont.load_default()
    TITLE_FONT = ImageFont.load_default()
    DIGITAL_FONT = None

HACKING_ANIMATIONS = [
    "🖥️ در حال اتصال به سرور امن...",
    "🔍 در حال یافتن محصول...",
    "📡 در حال برقراری ارتباط...",
    "🔑 در حال تأمین امنیت...",
    "💾 در حال پردازش اطلاعات...",
    "📶 در حال برقراری ارتباط امن...",
    "⚡ در حال انجام عملیات...",
    "🛡️ در حال تأمین حریم خصوصی...",
]

BATTERY_ANIMATIONS = [
    "⌛ : 1%...",
    "⏳ : 15%...",
    "⌛ : 30%...",
    "⏳ : 45%...",
    "⌛ : 60%...",
    "⏳ : 75%...",
    "⌛ : 90%...",
    "⏳ : 100%!",
]

LOADING_ANIMATIONS = [
    "⏳ در حال بارگذاری...",
    "⏳ کمی صبر کنید...",
    "🌀 عملیات در حال انجام است...",
    "📶 اتصال در حال برقراری...",
    "⚙️ سیستم در حال پردازش...",
]

# آواتارهای قابل انتخاب
AVATARS = {
    "mafia": "🕴️ مافیا",
    "hacker": "👨‍💻 هکر",
    "zodiac": "♌ زودیاک",
    "ninja": "🥷 نینجا",
    "ghost": "👻 روح",
    "king": "🤴 پادشاه",
    "queen": "👸 ملکه",
    "detective": "🕵️ کارآگاه"
}

# آواتارهای قفل شده و سطح مورد نیاز برای آنها
LOCKED_AVATARS = {
    "ninja": "فعال",    # نیاز به سطح فعال (101 سکه)
    "hacker": "حرفه‌ای", # نیاز به سطح حرفه‌ای (301 سکه)
    "king": "VIP"       # نیاز به سطح VIP (701 سکه)
}

# *********************** کلاس‌های کمکی ***********************
class Product:
    """کلاس محصولات فروشگاه"""

    def __init__(
        self,
        name: str,
        price: str,
        description: str,
        features: List[str],
        btc_address: str,
        stock: int = 5  # موجودی اولیه
    ):
        self.name = name
        self.price = price
        self.description = description
        self.features = features
        self.btc_address = btc_address
        self.stock = stock
        self.last_restock = datetime.now()

    def get_info(self) -> str:
        """نمایش اطلاعات محصول"""
        features = "\n".join(self.features)
        return f"""
📦 *{self.name}*

💰 قیمت: {self.price}
📝 توضیحات: {self.description}
🛒 موجودی: {self.stock} عدد

✨ امکانات:
{features}

⚠️ توجه: جهت حفظ حریم خصوصی و امنیت کار در مقابل سازنده، تمامی فرایند پرداخت با بیت کوین صورت گرفته میشود.
₿ آدرس بیت کوین: 
`{self.btc_address}`
"""

    def update_stock(self):
        """به روزرسانی خودکار موجودی محصولات"""
        now = datetime.now()
        if (now - self.last_restock) >= timedelta(days=1):
            self.stock = 5
            self.last_restock = now
        return self.stock


class FakeStatsGenerator:
    """کلاس تولید آمار فیک برای ربات"""
    
    def __init__(self):
        self.last_update = datetime.now()
        self.last_online_count = self._generate_initial_online()
        self.last_successful_orders = 16  # مقدار اولیه
        
    def _generate_initial_online(self) -> int:
        """تولید تعداد اولیه کاربران آنلاین بر اساس ساعت"""
        now = datetime.now()
        hour = now.hour
        
        if 8 <= hour < 12:
            return random.randint(280, 320)
        elif 12 <= hour < 16:
            return random.randint(300, 350)
        elif 16 <= hour < 20:
            return random.randint(250, 300)
        elif 20 <= hour < 24:
            return random.randint(200, 250)
        else:
            return random.randint(150, 200)
    
    def get_online_users(self) -> int:
        """دریافت تعداد کاربران آنلاین با تغییرات تصادفی"""
        now = datetime.now()
        
        if (now - self.last_update) > timedelta(minutes=10):
            self.last_update = now
            change = random.randint(-15, 15)
            self.last_online_count = max(150, min(350, self.last_online_count + change))
        
        return self.last_online_count
    
    def get_successful_orders(self) -> int:
        """دریافت تعداد خریدهای موفق با افزایش روزانه"""
        now = datetime.now()
        
        if now.date() > self.last_update.date():
            self.last_update = now
            self.last_successful_orders += random.randint(5, 10)
        
        return self.last_successful_orders


class AuthManager:
    """مدیریت احراز هویت کاربران"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """هش کردن رمز عبور"""
        salt = os.getenv("PASSWORD_SALT", "default_salt")
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """اعتبارسنجی ایمیل"""
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_password(password: str) -> bool:
        """اعتبارسنجی رمز عبور"""
        return len(password) >= 8 and any(c.isdigit() for c in password) and any(c.isalpha() for c in password)


class WalletManager:
    """مدیریت کیف پول بیت کوین"""
    
    @staticmethod
    async def get_balance(user_id: int) -> float:
        """دریافت موجودی کیف پول"""
        async with aiosqlite.connect(WALLET_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT balance FROM wallets WHERE user_id = ?", 
                (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else 0.0
    
    @staticmethod
    async def deposit(user_id: int, amount: float) -> bool:
        """واریز به کیف پول"""
        if amount <= 0:
            return False
            
        try:
            async with aiosqlite.connect(WALLET_DB_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO wallets (user_id, balance)
                    VALUES (?, COALESCE((SELECT balance FROM wallets WHERE user_id = ?), 0) + ?)
                    """,
                    (user_id, user_id, amount),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطا در واریز کیف پول: {e}")
            return False
    
    @staticmethod
async def withdraw(user_id: int, amount: float, address: str) -> bool:
    """برداشت از کیف پول"""
    MIN_WITHDRAW = 0.0005  # معادل 1,250,000 تومان
    
    if amount < MIN_WITHDRAW:
        return False
        
    if not re.match(r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$', address):
        return False
        
    try:
        async with aiosqlite.connect(WALLET_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT balance FROM wallets WHERE user_id = ?", 
                (user_id,)
            )
            balance = (await cursor.fetchone())[0]
            
            if balance < amount:
                return False
                
            await db.execute(
                "UPDATE wallets SET balance = balance - ? WHERE user_id = ?",
                (amount, user_id)
            )
            
            await db.execute(
                """INSERT INTO transactions 
                (user_id, amount, address, type, status)
                VALUES (?, ?, ?, 'withdraw', 'pending')""",
                (user_id, amount, address)
            )
            await db.commit()
            return True
    except Exception as e:
        logger.error(f"خطا در برداشت از کیف پول: {e}")
        return False


class CoinManager:
    """مدیریت سکه‌های کاربران"""
    
    @staticmethod
    async def init_db() -> None:
        """تنظیمات دیتابیس سکه‌ها"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_coins (
                    user_id INTEGER PRIMARY KEY,
                    coins INTEGER DEFAULT 0,
                    last_daily_claim DATETIME,
                    dark_mode BOOLEAN DEFAULT FALSE,
                    avatar TEXT DEFAULT 'mafia',
                    last_wheel_spin DATETIME,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS leaderboard (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    coins INTEGER NOT NULL,
                    is_fake BOOLEAN DEFAULT TRUE,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS discount_codes (
                    code TEXT PRIMARY KEY,
                    user_id INTEGER,
                    discount_percent INTEGER DEFAULT 10,
                    expires_at DATETIME,
                    used BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )
            await db.commit()
            
            # ایجاد کاربران فیک برای جدول رتبه‌بندی
            fake_users = [
                ("𝙈𝙞𝙣𝙖", random.randint(100, 150)),
                ("Ⓢ Ⓢ", random.randint(100, 150)),
                ("𝕸𝖆𝖃𝖉𝖎", random.randint(100, 150)),
                ("𝓜𝓪𝓧𝓭𝓲", random.randint(100, 150)),
                ("𝕞𝕞𝕞", random.randint(100, 150)),
                ("𝕄𝕖𝕥𝕚", random.randint(100, 150)),
                ("3𝘼𝙞𝙙", random.randint(100, 150)),
                ("𝕗𝕒𝕥𝕚 𝕄𝔾", random.randint(100, 200)),
                ("𝟞𝟞𝟞", random.randint(100, 150)),
                ("𝔳𝔞𝔥𝔦𝔡", random.randint(100, 150)),
            ]
            
            for username, coins in fake_users:
                await db.execute(
                    """
                    INSERT OR IGNORE INTO leaderboard (username, coins, is_fake)
                    VALUES (?, ?, TRUE)
                    """,
                    (username, coins)
                )
            await db.commit()
    
    @staticmethod
    async def get_user_level(coins: int) -> str:
        """دریافت سطح کاربر بر اساس سکه‌ها"""
        if coins >= 701:
            return "VIP"
        elif coins >= 301:
            return "حرفه‌ای"
        elif coins >= 101:
            return "فعال"
        else:
            return "تازه کار"
    
    @staticmethod
    async def get_level_progress(coins: int) -> Tuple[int, int, int]:
        """دریافت پیشرفت به سطح بعدی"""
        if coins >= 701:  # VIP
            return (701, 1001, min(100, int((coins - 701) / 3)))
        elif coins >= 301:  # حرفه‌ای
            return (301, 701, min(100, int((coins - 301) / 4)))
        elif coins >= 101:  # فعال
            return (101, 301, min(100, int((coins - 101) / 2)))
        else:  # تازه کار
            return (0, 101, min(100, int(coins)))
    
    @staticmethod
    async def get_coins(user_id: int) -> int:
        """دریافت تعداد سکه‌های کاربر"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT coins FROM user_coins WHERE user_id = ?", (user_id,)
            result = await cursor.fetchone()
            return result[0] if result else 0
    
    @staticmethod
    async def add_coins(user_id: int, amount: int, reason: str) -> bool:
        """افزودن سکه به کاربر"""
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO user_coins (user_id, coins)
                    VALUES (?, COALESCE((SELECT coins FROM user_coins WHERE user_id = ?), 0) + ?)
                    """,
                    (user_id, user_id, amount),
                )
                await db.commit()
                
                # ثبت در تاریخچه
                await db.execute(
                    """
                    INSERT INTO coin_history (user_id, amount, reason, timestamp)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (user_id, amount, reason),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطا در افزودن سکه: {e}")
            return False
    
    @staticmethod
    async def admin_add_coins(user_id: int, amount: int) -> bool:
        """افزودن سکه به کاربر توسط ادمین"""
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO user_coins (user_id, coins)
                    VALUES (?, COALESCE((SELECT coins FROM user_coins WHERE user_id = ?), 0) + ?)
                    """,
                    (user_id, user_id, amount),
                )
                await db.commit()
                
                # ثبت در تاریخچه
                await db.execute(
                    """
                    INSERT INTO coin_history (user_id, amount, reason, timestamp)
                    VALUES (?, ?, 'ادمین', CURRENT_TIMESTAMP)
                    """,
                    (user_id, amount),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطا در افزودن سکه توسط ادمین: {e}")
            return False
    
    @staticmethod
    async def can_claim_daily(user_id: int) -> bool:
        """بررسی امکان دریافت پاداش روزانه"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT last_daily_claim FROM user_coins WHERE user_id = ?", (user_id,)
            result = await cursor.fetchone()
            
            if not result or not result[0]:
                return True
                
            last_claim = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - last_claim) >= timedelta(hours=24)
    
    @staticmethod
    async def claim_daily_coins(user_id: int) -> bool:
        """دریافت سکه روزانه"""
        if not await CoinManager.can_claim_daily(user_id):
            return False
            
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO user_coins (user_id, coins, last_daily_claim)
                    VALUES (?, COALESCE((SELECT coins FROM user_coins WHERE user_id = ?), 0) + 5, CURRENT_TIMESTAMP)
                    """,
                    (user_id, user_id),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطا در دریافت سکه روزانه: {e}")
            return False
    
    @staticmethod
    async def convert_coins_to_btc(user_id: int, coins: int) -> bool:
        """تبدیل سکه به بیت کوین"""
        MIN_COINS = 300  # حداقل سکه برای تبدیل
        COINS_PER_BTC = 300  # هر 300 سکه = 0.00002 BTC
        
        if coins < MIN_COINS:
            return False
            
        btc_amount = (coins // COINS_PER_BTC) * 0.00002
        
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                # کسر سکه‌ها
                await db.execute(
                    "UPDATE user_coins SET coins = coins - ? WHERE user_id = ? AND coins >= ?",
                    (coins, user_id, coins)
                await db.commit()
                
                # واریز بیت کوین
                await WalletManager.deposit(user_id, btc_amount)
                return True
        except Exception as e:
            logger.error(f"خطا در تبدیل سکه به بیت کوین: {e}")
            return False
    
    @staticmethod
    async def get_leaderboard(limit: int = 5) -> List[Tuple]:
        """دریافت جدول رتبه‌بندی"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            # به روزرسانی سکه‌های کاربران فیک
            await db.execute(
                """
                UPDATE leaderboard 
                SET coins = coins + ?, 
                    last_updated = CURRENT_TIMESTAMP 
                WHERE is_fake = TRUE
                """,
                (random.randint(10, 30),)
            await db.commit()
            
            cursor = await db.execute(
                """
                SELECT username, coins 
                FROM leaderboard 
                WHERE is_fake = TRUE
                ORDER BY coins DESC 
                LIMIT ?
                """,
                (limit,)
            )
            return await cursor.fetchall()
    
    @staticmethod
    async def get_user_rank(user_id: int) -> Optional[int]:
        """دریافت رتبه کاربر در جدول رتبه‌بندی"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*) + 1
                FROM (
                    SELECT user_id, coins 
                    FROM user_coins 
                    WHERE coins > (SELECT coins FROM user_coins WHERE user_id = ?)
                )
                """,
                (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else None
    
    @staticmethod
    async def toggle_dark_mode(user_id: int) -> bool:
        """تغییر حالت تاریک/روشن"""
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                await db.execute(
                    """
                    UPDATE user_coins 
                    SET dark_mode = NOT dark_mode 
                    WHERE user_id = ?
                    """,
                    (user_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطا در تغییر حالت تاریک/روشن: {e}")
            return False
    
    @staticmethod
    async def get_dark_mode(user_id: int) -> bool:
        """دریافت وضعیت حالت تاریک/روشن"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT dark_mode FROM user_coins WHERE user_id = ?", (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else False
    
    @staticmethod
    async def set_avatar(user_id: int, avatar: str) -> bool:
        """تنظیم آواتار کاربر"""
        if avatar not in AVATARS:
            return False
            
        # بررسی سطح کاربر برای آواتارهای قفل شده
        if avatar in LOCKED_AVATARS:
            coins = await CoinManager.get_coins(user_id)
            user_level = await CoinManager.get_user_level(coins)
            required_level = LOCKED_AVATARS[avatar]
            
            level_order = ["تازه کار", "فعال", "حرفه‌ای", "VIP"]
            current_index = level_order.index(user_level)
            required_index = level_order.index(required_level)
            
            if current_index < required_index:
                return False
            
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                await db.execute(
                    "UPDATE user_coins SET avatar = ? WHERE user_id = ?",
                    (avatar, user_id)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطا در تنظیم آواتار: {e}")
            return False
    
    @staticmethod
    async def get_avatar(user_id: int) -> str:
        """دریافت آواتار کاربر"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT avatar FROM user_coins WHERE user_id = ?", (user_id,)
            )
            result = await cursor.fetchone()
            return result[0] if result else "mafia"
    
    @staticmethod
    async def generate_discount_code(user_id: int) -> str:
        """تولید کد تخفیف"""
        code = f"DISCOUNT-{hashlib.md5(str(user_id + datetime.now().timestamp()).encode()).hexdigest()[:8].upper()}"
        
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                await db.execute(
                    """
                    INSERT INTO discount_codes (code, user_id, expires_at)
                    VALUES (?, ?, datetime('now', '+1 day'))
                    """,
                    (code, user_id)
                )
                await db.commit()
                return code
        except Exception as e:
            logger.error(f"خطا در تولید کد تخفیف: {e}")
            return ""
    
    @staticmethod
    async def validate_discount_code(user_id: int, code: str) -> bool:
        """اعتبارسنجی کد تخفیف"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT 1 FROM discount_codes 
                WHERE code = ? AND user_id = ? AND used = FALSE AND expires_at > datetime('now')
                """,
                (code, user_id)
            )
            return await cursor.fetchone() is not None
    
    @staticmethod
    async def use_discount_code(user_id: int, code: str) -> bool:
        """استفاده از کد تخفیف"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            await db.execute(
                "UPDATE discount_codes SET used = TRUE WHERE code = ? AND user_id = ?",
                (code, user_id)
            )
            await db.commit()
            return True


class ReferralSystem:
    """سیستم معرفی دوستان"""
    
    REFERRAL_BONUS = 0.0001  # معادل 50,000 تومان
    REQUIRED_REFERRALS = 10
    
    @staticmethod
    async def get_referral_code(user_id: int) -> str:
        """دریافت کد معرف کاربر"""
        return f"REF-{user_id}-{hashlib.md5(str(user_id).encode()).hexdigest()[:5]}"
    
    @staticmethod
    async def add_referral(referrer_id: int, referred_id: int) -> bool:
        """ثبت معرفی جدید"""
        if referrer_id == referred_id:
            return False
            
        try:
            async with aiosqlite.connect(USERS_DB_PATH) as db:
                # بررسی اینکه کاربر دعوت شده ثبت نام کرده است
                cursor = await db.execute(
                    "SELECT 1 FROM users WHERE user_id = ?", (referred_id,)
                )
                if not await cursor.fetchone():
                    return False
                
                # بررسی عدم وجود معرفی تکراری
                cursor = await db.execute(
                    "SELECT 1 FROM referrals WHERE referrer_id = ? AND referred_id = ?",
                    (referrer_id, referred_id)
                )
                if await cursor.fetchone():
                    return False
                
                await db.execute(
                    "INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)",
                    (referrer_id, referred_id),
                )
                await db.commit()
                
                # افزودن سکه به معرف
                await CoinManager.add_coins(referrer_id, 10, "معرفی دوست")
                
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
                    (referrer_id,),
                )
                count = (await cursor.fetchone())[0]
                
                if count >= ReferralSystem.REQUIRED_REFERRALS:
                    await WalletManager.deposit(referrer_id, ReferralSystem.REFERRAL_BONUS)
                    return True
                return True
        except Exception as e:
            logger.error(f"خطا در ثبت معرف: {e}")
            return False


class ShopBot:
    """کلاس اصلی ربات فروشگاه"""

    def __init__(self):
        self.products = self._load_products()
        self.bot_token = os.getenv("BOT_TOKEN")
        self.admin_id = int(os.getenv("ADMIN_ID", 0))
        self.support_username = os.getenv("SUPPORT_USERNAME")
        self.channel_username = os.getenv("CHANNEL_USERNAME")
        self.stats_generator = FakeStatsGenerator()
        self.admin_password = os.getenv("ADMIN_PASSWORD")
        self.auth_manager = AuthManager()
        self.wallet_manager = WalletManager()
        self.referral_system = ReferralSystem()
        self.coin_manager = CoinManager()
        self.daily_notification_task = None

    @staticmethod
    def _load_products() -> Dict[str, Product]:
        """بارگذاری محصولات"""
        return {
            "mafia": Product(
                name="چیت بازی شب های مافیا",
                price="0.00018 BTC (~450,000 تومان)",
                description="نمایش نقش‌های مخفی بازیکنان با قابلیت ضد بن",
                features=[
                    "✅ نمایش تمامی نقش‌های مخفی",
                    "✅ قابلیت ضد تشخیص",
                    "✅ پشتیبانی 24 ساعته",
                    "✅ تایم پنل 30 روزه",
                ],
                btc_address=os.getenv("BTC_MAFIA"),
            ),
            "zodiac": Product(
                name="چیت بازی شب های مافیا زودیاک",
                price="0.00022 BTC (~550,000 تومان)",
                description="پکیج ویژه زودیاک با امکانات پیشرفته",
                features=[
                    "✅ نمایش تمامی نقش‌های مخفی",
                    "✅ نمایش نقش زودیاک",
                    "✅ سیستم ضد بن پیشرفته",
                    "✅ تایم پنل 30 روزه",
                ],
                btc_address=os.getenv("BTC_ZODIAC"),
            ),
        }

    async def init_db(self) -> None:
        """تنظیمات دیتابیس"""
        os.makedirs("data", exist_ok=True)
        
        # دیتابیس سفارشات
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    full_name TEXT NOT NULL,
                    product TEXT NOT NULL,
                    price TEXT NOT NULL,
                    tracking_code TEXT UNIQUE NOT NULL,
                    tx_hash TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON orders (user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_status ON orders (status)")
            await db.commit()
        
        # دیتابیس آمار
        async with aiosqlite.connect(STATS_DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stat_name TEXT UNIQUE NOT NULL,
                    stat_value INTEGER NOT NULL,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO stats (stat_name, stat_value) VALUES (?, ?)",
                    ("online_users", 250),
                )
                await db.execute(
                    "INSERT OR IGNORE INTO stats (stat_name, stat_value) VALUES (?, ?)",
                    ("successful_orders", 16),
                )
                await db.commit()
            except Exception as e:
                logger.error(f"خطا در مقداردهی اولیه آمار: {e}")

        # دیتابیس کاربران
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    full_name TEXT,
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                    FOREIGN KEY (referred_id) REFERENCES users (user_id)
                )
                """
            )
            await db.commit()
        
        # دیتابیس کیف پول
        async with aiosqlite.connect(WALLET_DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS wallets (
                    user_id INTEGER PRIMARY KEY,
                    balance REAL DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    address TEXT,
                    type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )
            await db.commit()
        
        # دیتابیس سکه‌ها
        await self.coin_manager.init_db()

    # *********************** متدهای دیتابیس ***********************
    @staticmethod
    async def save_order(
        user_id: int,
        full_name: str,
        product: Product,
        tracking_code: str,
        tx_hash: str,
        status: str = "pending",
    ) -> bool:
        """ذخیره سفارش جدید"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    """
                    INSERT INTO orders 
                    (user_id, full_name, product, price, tracking_code, tx_hash, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        full_name,
                        product.name,
                        product.price,
                        tracking_code,
                        tx_hash,
                        status,
                    ),
                )
                await db.commit()
                
                # افزودن سکه به کاربر برای خرید موفق
                await CoinManager.add_coins(user_id, 50, "خرید موفق")
                return True
        except Exception as e:
            logger.error(f"خطای دیتابیس: {e}", exc_info=True)
            return False

    @staticmethod
    async def get_order(order_id: int) -> Optional[Tuple]:
        """دریافت سفارش"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT * FROM orders WHERE id = ?", (order_id,)
            )
            return await cursor.fetchone()

    @staticmethod
    async def update_order_status(order_id: int, status: str) -> bool:
        """به‌روزرسانی وضعیت سفارش"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "UPDATE orders SET status = ? WHERE id = ?",
                    (status, order_id),
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطای دیتابیس: {e}")
            return False

    @staticmethod
    async def get_user_orders(user_id: int) -> List[Tuple]:
        """دریافت سفارشات کاربر"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT id, product, price, tracking_code, status, timestamp 
                FROM orders 
                WHERE user_id = ?
                ORDER BY timestamp DESC
                """,
                (user_id,),
            )
            return await cursor.fetchall()

    @staticmethod
    async def get_all_orders(limit: int = 50) -> List[Tuple]:
        """دریافت تمام سفارشات"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """
                SELECT id, user_id, full_name, product, price, tracking_code, status, timestamp
                FROM orders
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            return await cursor.fetchall()

    # *********************** متدهای کمکی ***********************
    @staticmethod
    def generate_tracking_code() -> str:
        """تولید کد لایسنس"""
        return f"RHMAF-{uuid.uuid4().hex[:8].upper()}"

    def is_admin(self, user_id: int) -> bool:
        """بررسی ادمین بودن کاربر"""
        return user_id == self.admin_id

    async def verify_admin_password(self, password: str) -> bool:
        """بررسی رمز عبور ادمین"""
        hashed_input = hashlib.sha256(password.encode()).hexdigest()
        return hashed_input == hashlib.sha256(self.admin_password.encode()).hexdigest()

    async def show_hacking_animation(self, update: Update, duration: int = 3) -> None:
        """نمایش انیمیشن"""
        message = await update.message.reply_text("🖥️ در حال اتصال به شبکه امن...")
        
        for _ in range(duration):
            animation = random.choice(HACKING_ANIMATIONS + BATTERY_ANIMATIONS + LOADING_ANIMATIONS)
            await message.edit_text(animation)
            await asyncio.sleep(1)
        
        await message.delete()

    async def show_battery_animation(self, update: Update) -> None:
        """نمایش انیمیشن باتری"""
        message = await update.message.reply_text("🔋 : 0%...")
        
        for anim in BATTERY_ANIMATIONS:
            await message.edit_text(anim)
            await asyncio.sleep(0.7)
        
        await message.delete()

    async def show_loading_animation(self, update: Update, text: str = "در حال پردازش...") -> None:
        """نمایش انیمیشن لودینگ"""
        message = await update.message.reply_text(f"⏳ {text}")
        
        for anim in LOADING_ANIMATIONS:
            await message.edit_text(anim)
            await asyncio.sleep(0.8)
        
        await message.delete()

    async def send_to_admin(self, context: ContextTypes.DEFAULT_TYPE, message: str) -> bool:
        """ارسال پیام به ادمین"""
        try:
            await context.bot.send_message(chat_id=self.admin_id, text=message)
            return True
        except Exception as e:
            logger.error(f"خطا در ارسال به ادمین: {e}")
            return False

    async def send_to_user(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str) -> bool:
        """ارسال پیام به کاربر"""
        try:
            await context.bot.send_message(chat_id=user_id, text=message)
            return True
        except Exception as e:
            logger.error(f"خطا در ارسال به کاربر {user_id}: {e}")
            return False

    async def get_stats_message(self) -> str:
        """دریافت پیام آمار فیک"""
        online_users = self.stats_generator.get_online_users()
        successful_orders = self.stats_generator.get_successful_orders()
        
        return f"""
📊 *آمار لحظه‌ای ربات*

👥 کاربران آنلاین: {online_users} نفر
✅ خریدهای موفق: {successful_orders} نفر

🔄 آمار هر 10 دقیقه به‌روز می‌شود.
"""

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """دستور نمایش آمار"""
        stats_msg = await self.get_stats_message()
        await update.message.reply_text(stats_msg, parse_mode='Markdown')

    # *********************** سیستم احراز هویت ***********************
    async def check_channel_membership(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بررسی عضویت کاربر در کانال"""
        if not self.channel_username:
            return REGISTER_EMAIL
            
        user = update.effective_user
        try:
            member = await context.bot.get_chat_member(f"@{self.channel_username}", user.id)
            if member.status not in ['left', 'kicked']:
                # اضافه کردن 10 سکه رایگان برای عضویت در کانال
                await self.coin_manager.add_coins(user.id, 10, "عضویت در کانال")
                return REGISTER_EMAIL
        except Exception as e:
            logger.error(f"خطا در بررسی عضویت کانال: {e}")
        return CHANNEL_CHECK

    async def start_auth(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """شروع فرآیند احراز هویت"""
        user = update.effective_user
        
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?", (user.id,)
            )
            if await cursor.fetchone():
                await update.message.reply_text(
                    "شما قبلاً ثبت‌نام کرده‌اید. لطفاً وارد شوید.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔐 ورود به حساب", callback_data="login")]
                    ])
                )
                return SELECTING_ACTION
            else:
                return await self.check_channel_membership(update, context)

    async def register_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """ثبت ایمیل کاربر"""
        email = update.message.text.strip()
        
        if not self.auth_manager.validate_email(email):
            await update.message.reply_text("ایمیل وارد شده معتبر نیست. لطفاً یک ایمیل صحیح وارد کنید:")
            return REGISTER_EMAIL
        
        # بررسی تکراری نبودن ایمیل
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE email = ?", (email,)
            )
            if await cursor.fetchone():
                await update.message.reply_text("این ایمیل قبلاً ثبت شده است. لطفاً ایمیل دیگری وارد کنید:")
                return REGISTER_EMAIL
        
        context.user_data['email'] = email
        await update.message.reply_text(
            "لطفاً یک رمز عبور حداقل ۸ رقمی وارد کنید (ترجیحاً شامل اعداد و حروف):"
        )
        return REGISTER_PASSWORD

    async def register_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """ثبت رمز عبور کاربر"""
        password = update.message.text.strip()
        
        if not self.auth_manager.validate_password(password):
            await update.message.reply_text(
                "رمز عبور باید حداقل ۸ کاراکتر و شامل اعداد و حروف باشد. لطفاً مجدداً وارد کنید:"
            )
            return REGISTER_PASSWORD
        
        user = update.effective_user
        hashed_password = self.auth_manager.hash_password(password)
        
        try:
            async with aiosqlite.connect(USERS_DB_PATH) as db:
                await db.execute(
                    """
                    INSERT INTO users (user_id, email, password, full_name)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user.id, context.user_data['email'], hashed_password, user.full_name),
                )
                await db.commit()
                
                async with aiosqlite.connect(WALLET_DB_PATH) as wallet_db:
                    await wallet_db.execute(
                        "INSERT OR IGNORE INTO wallets (user_id, balance) VALUES (?, 0)",
                        (user.id,),
                    )
                    await wallet_db.commit()
                
                # افزودن سکه برای ثبت نام
                await self.coin_manager.add_coins(user.id, 10, "ثبت نام")
                
                await update.message.reply_text(
                    "ثبت‌نام شما با موفقیت انجام شد! 🎉\n\n"
                    "اکنون می‌توانید از تمام امکانات ربات استفاده کنید.",
                )
                context.user_data.clear()
                return await self.show_main_menu(update, context)
        except Exception as e:
            logger.error(f"خطا در ثبت کاربر: {e}")
            await update.message.reply_text(
                "خطایی در ثبت‌نام رخ داد. لطفاً بعداً تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
            return ConversationHandler.END

    async def login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """شروع فرآیند ورود"""
        query = update.callback_query
        if query:
            await query.answer()
            await query.edit_message_text("لطفاً ایمیل خود را وارد کنید:")
        else:
            await update.message.reply_text("لطفاً ایمیل خود را وارد کنید:")
        return LOGIN_EMAIL

    async def login_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """دریافت ایمیل برای ورود"""
        email = update.message.text.strip()
        context.user_data['login_email'] = email
        await update.message.reply_text("لطفاً رمز عبور خود را وارد کنید:")
        return LOGIN_PASSWORD

    async def login_password(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """بررسی رمز عبور و ورود کاربر"""
        password = update.message.text.strip()
        email = context.user_data['login_email']
        hashed_password = self.auth_manager.hash_password(password)
        
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id FROM users WHERE email = ? AND password = ?",
                (email, hashed_password),
            )
            user = await cursor.fetchone()
            
            if user:
                # دریافت سکه روزانه
                if await self.coin_manager.can_claim_daily(user[0]):
                    await self.coin_manager.claim_daily_coins(user[0])
                    await update.message.reply_text(
                        "🎉 شما 5 سکه برای ورود امروز دریافت کردید!"
                    )
                
                await update.message.reply_text(
                    "ورود با موفقیت انجام شد! ✅",
                )
                context.user_data.clear()
                return await self.show_main_menu(update, context)
            else:
                await update.message.reply_text(
                    "ایمیل یا رمز عبور اشتباه است. لطفاً مجدداً تلاش کنید.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 تلاش مجدد", callback_data="login")],
                        [InlineKeyboardButton("📝 ثبت‌نام", callback_data="register")]
                    ])
                )
                return ConversationHandler.END

    # *********************** سیستم کیف پول و سکه‌ها ***********************
    async def generate_wallet_image(self, balance: float, coins: int) -> bytes:
        """تولید تصویر کیف پول دیجیتال"""
        img = Image.new('RGB', (600, 400), color=(20, 20, 40))
        draw = ImageDraw.Draw(img)
        
        # نمایش موجودی بیت کوین
        draw.text((50, 50), "💰 کیف پول بیت کوین", font=TITLE_FONT, fill=(255, 255, 255))
        draw.text((50, 90), f"موجودی: {balance:.8f} BTC", font=MONO_FONT, fill=(200, 255, 200))
        
        # نمایش سکه‌ها
        draw.text((50, 150), "🪙 سکه‌های شما", font=TITLE_FONT, fill=(255, 255, 255))
        draw.text((50, 190), f"تعداد: {coins} سکه", font=MONO_FONT, fill=(255, 215, 0))
        
        # اطلاعات تبدیل
        draw.text((50, 250), f"هر 300 سکه = 0.00002 BTC (~50,000 تومان)", font=MONO_FONT, fill=(200, 200, 255))
        
        # ذخیره تصویر در بایت
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()

    async def show_wallet(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش کیف پول کاربر"""
        user_id = update.effective_user.id
        balance = await self.wallet_manager.get_balance(user_id)
        coins = await self.coin_manager.get_coins(user_id)
        
        # تولید تصویر کیف پول
        wallet_image = await self.generate_wallet_image(balance, coins)
        
        keyboard = [
            [InlineKeyboardButton("💳 واریز بیت کوین", callback_data="deposit_btc")],
            [InlineKeyboardButton("💸 برداشت بیت کوین", callback_data="withdraw_btc")],
            [InlineKeyboardButton("🪙 تبدیل سکه به بیت کوین", callback_data="convert_coins")],
            [InlineKeyboardButton("📜 تاریخچه تراکنش‌ها", callback_data="transaction_history")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")],
        ]
        
        await update.callback_query.message.reply_photo(
            photo=wallet_image,
            caption=f"💰 *کیف پول شما*\n\n"
                   f"موجودی بیت کوین: `{balance:.8f} BTC`\n"
                   f"تعداد سکه‌ها: `{coins}`\n\n"
                   f"حداقل برداشت: 0.0005 BTC (~1,250,000 تومان)",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        await update.callback_query.message.delete()
        return WALLET_ACTIONS

    async def deposit_btc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """دریافت آدرس واریز بیت کوین"""
        user_id = update.effective_user.id
        deposit_address = os.getenv("BTC_DEPOSIT_ADDRESS")
        
        if not deposit_address:
            await update.callback_query.edit_message_text(
                "⚠️ آدرس واریز تنظیم نشده است. لطفاً با پشتیبانی تماس بگیرید."
            )
            return WALLET_ACTIONS
        
        if not re.match(r'^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$', deposit_address):
            await update.callback_query.edit_message_text(
                "⚠️ آدرس واریز نامعتبر است. لطفاً با پشتیبانی تماس بگیرید."
            )
            return WALLET_ACTIONS
        
        await update.callback_query.edit_message_text(
            f"📥 *واریز بیت کوین*\n\n"
            f"برای واریز، مبلغ مورد نظر را به آدرس زیر ارسال کنید:\n"
            f"`{deposit_address}`\n\n"
            f"⚠️ توجه: پس از واریز، حتماً هش تراکنش (TXID) را برای ما ارسال کنید تا موجودی شما شارژ شود.",
            parse_mode='Markdown'
        )
        return WALLET_ACTIONS

    async def withdraw_btc(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """درخواست برداشت بیت کوین"""
        await update.callback_query.edit_message_text(
            "📤 *برداشت بیت کوین*\n\n"
            "لطفاً آدرس بیت کوین مقصد و مبلغ مورد نظر برای برداشت را به فرمت زیر وارد کنید:\n\n"
            "مثال:\n"
            "`آدرس_مقصد مقدار`\n\n"
            "مثال:\n"
            "`bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq 0.005`",
            parse_mode='Markdown'
        )
        return WALLET_ACTIONS

    async def convert_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تبدیل سکه به بیت کوین"""
        user_id = update.effective_user.id
        coins = await self.coin_manager.get_coins(user_id)
        
        if coins < 300:
            await update.callback_query.edit_message_text(
                f"⚠️ شما فقط {coins} سکه دارید. حداقل 300 سکه برای تبدیل نیاز است."
            )
            return WALLET_ACTIONS
        
        btc_amount = (coins // 300) * 0.00002
        await update.callback_query.edit_message_text(
            f"🔄 *تبدیل سکه به بیت کوین*\n\n"
            f"شما می‌توانید {coins // 300 * 300} سکه خود را به {btc_amount:.3f} BTC تبدیل کنید.\n\n"
            f"آیا مطمئن هستید؟",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ بله، تبدیل کن", callback_data=f"confirm_convert_{coins // 300 * 300}")],
                [InlineKeyboardButton("❌ انصراف", callback_data="wallet")],
            ]),
            parse_mode='Markdown'
        )
        return WALLET_ACTIONS

    async def confirm_convert_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تأیید تبدیل سکه به بیت کوین"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        coins = int(query.data.split("_")[2])
        
        success = await self.coin_manager.convert_coins_to_btc(user_id, coins)
        if success:
            btc_amount = (coins // 300) * 0.00002
            await query.edit_message_text(
                f"✅ {coins} سکه شما با موفقیت به {btc_amount:.3f} BTC تبدیل شد!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به کیف پول", callback_data="wallet")],
                ])
            )
        else:
            await query.edit_message_text(
                "⚠️ خطایی در تبدیل سکه‌ها رخ داد. لطفاً بعداً تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به کیف پول", callback_data="wallet")],
                ])
            )
        return WALLET_ACTIONS

    async def process_withdrawal(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پردازش درخواست برداشت"""
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        try:
            parts = text.split()
            if len(parts) != 2:
                raise ValueError
            
            address, amount = parts
            amount = float(amount)
            
            if amount < 0.0005:
                await update.message.reply_text(
                    "حداقل مبلغ برداشت 0.0005 BTC (~1,250,000 تومان) می‌باشد."
                )
                return WALLET_ACTIONS
                
            success = await self.wallet_manager.withdraw(user_id, amount, address)
            
            if success:
                # افزودن سکه برای برداشت
                await self.coin_manager.add_coins(user_id, 20, "برداشت از کیف پول")
                
                await update.message.reply_text(
                    "✅ درخواست برداشت شما ثبت شد و پس از تأیید ادمین، به آدرس مشخص شده واریز خواهد شد."
                )
            else:
                await update.message.reply_text(
                    "❌ موجودی کیف پول شما کافی نیست یا آدرس بیت کوین نامعتبر است."
                )
        except ValueError:
            await update.message.reply_text(
                "فرمت وارد شده صحیح نیست. لطفاً مطابق مثال عمل کنید."
            )
        
        return await self.show_wallet(update, context)

    # *********************** سیستم معرفی دوستان ***********************
    async def generate_referral_image(self, referral_code: str, referral_count: int) -> bytes:
        """تولید تصویر سیستم معرفی"""
        img = Image.new('RGB', (600, 400), color=(30, 30, 60))
        draw = ImageDraw.Draw(img)
        
        # هدر
        draw.rectangle([(0, 0), (600, 60)], fill=(50, 50, 100))
        draw.text((150, 20), "سیستم معرفی دوستان", font=TITLE_FONT, fill=(255, 255, 255))
        
        # اطلاعات معرفی
        draw.text((50, 100), f"کد معرف شما:", font=MONO_FONT, fill=(200, 200, 255))
        draw.text((50, 130), referral_code, font=TITLE_FONT, fill=(0, 255, 255))
        
        draw.text((50, 180), f"تعداد معرفی‌های شما:", font=MONO_FONT, fill=(200, 200, 255))
        draw.text((50, 210), f"{referral_count}/10", font=TITLE_FONT, fill=(255, 255, 0))
        
        draw.text((50, 260), "پاداش: 50,000 تومان بیت کوین", font=MONO_FONT, fill=(200, 255, 200))
        draw.text((50, 290), "برای هر 10 معرفی موفق", font=MONO_FONT, fill=(200, 255, 200))
        
        # ذخیره تصویر در بایت
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()

    async def show_referral(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش بخش معرفی دوستان"""
        user_id = update.effective_user.id
        referral_code = await self.referral_system.get_referral_code(user_id)
        
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM referrals WHERE referrer_id = ?",
                (user_id,),
            )
            referral_count = (await cursor.fetchone())[0]
        
        remaining = max(0, 10 - referral_count)
        
        # تولید تصویر معرفی
        referral_image = await self.generate_referral_image(referral_code, referral_count)
        
        message = (
            "👥 *سیستم معرفی دوستان*\n\n"
            f"تا دریافت پاداش: {remaining} معرفی دیگر\n\n"
            "🎁 *پاداش:*\n"
            "با معرفی 10 دوست، کیف پول شما معادل 50,000 تومان بیت کوین شارژ می‌شود!\n\n"
            "📌 دوستان شما باید از لینک زیر برای عضویت استفاده کنند:\n"
            f"https://t.me/{context.bot.username}?start={referral_code}"
        )
        
        await update.callback_query.message.reply_photo(
            photo=referral_image,
            caption=message,
            parse_mode='Markdown'
        )
        await update.callback_query.message.delete()
        return REFERRAL_MENU

    async def handle_referral_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پردازش لینک معرفی دوستان"""
        user = update.effective_user
        args = context.args
        
        if args and args[0].startswith("REF-"):
            referrer_code = args[0]
            try:
                referrer_id = int(referrer_code.split('-')[1])
                
                # ذخیره اطلاعات دعوت در context برای استفاده پس از ثبت نام
                context.user_data['referrer_id'] = referrer_id
                
                await update.message.reply_text(
                    "👋 شما با کد معرف دوست ما وارد شدید!\n\n"
                    "پس از تکمیل ثبت‌نام، دوست شما یک قدم به دریافت پاداش نزدیک می‌شود."
                )
            except Exception as e:
                logger.error(f"خطا در پردازش کد معرف: {e}")
        
        return await self.start_auth(update, context)

    # *********************** گردونه شانس ***********************
    async def generate_wheel_image(self) -> bytes:
        """تولید تصویر گردونه شانس"""
        img = Image.new('RGB', (500, 500), color=(30, 30, 60))
        draw = ImageDraw.Draw(img)
        
        # رسم گردونه
        center = (250, 250)
        radius = 200
        prizes = ["1 سکه", "3 سکه", "5 سکه", "10 سکه", "کد تخفیف 10%"]
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)]
        
        for i in range(5):
            start_angle = i * 72
            end_angle = (i + 1) * 72
            draw.pieslice(
                [center[0]-radius, center[1]-radius, center[0]+radius, center[1]+radius],
                start_angle, end_angle, fill=colors[i]
            )
            
            # افزودن متن جایزه
            angle = math.radians(start_angle + 36)
            text_pos = (
                center[0] + (radius * 0.7) * math.cos(angle),
                center[1] + (radius * 0.7) * math.sin(angle)
            )
            draw.text(text_pos, prizes[i], font=TITLE_FONT, fill=(0, 0, 0))
        
        # افزودن نشانگر
        draw.polygon(
            [(center[0], center[1]-radius-20), (center[0]-15, center[1]-radius), 
             (center[0]+15, center[1]-radius)], fill=(255, 255, 255))
        
        # ذخیره تصویر در بایت
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()

    async def spin_wheel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """چرخاندن گردونه شانس"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # بررسی امکان چرخش گردونه
        last_spin = await self.get_last_wheel_spin(user_id)
        if last_spin and (datetime.now() - last_spin) < timedelta(hours=24):
            await query.edit_message_text(
                "⏳ شما امروز از گردونه شانس استفاده کرده‌اید. لطفاً فردا مجدداً تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
                ])
            )
            return WHEEL_OF_FORTUNE
        
        # نمایش انیمیشن چرخش
        wheel_image = await self.generate_wheel_image()
        message = await query.edit_message_media(
            InputMediaPhoto(wheel_image, caption="🌀 گردونه در حال چرخش...")
        )
        
        # شبیه‌سازی چرخش
        for _ in range(8):
            wheel_image = await self.generate_wheel_image()
            await message.edit_media(
                InputMediaPhoto(wheel_image, caption="🌀 گردونه در حال چرخش...")
            )
            await asyncio.sleep(0.5)
        
        # انتخاب جایزه تصادفی (با احتمال کمتر برای جایزه بزرگ)
        prize = random.choices(
            ["1 سکه", "3 سکه", "5 سکه", "10 سکه", "کد تخفیف 10%"],
            weights=[30, 25, 20, 15, 10],
            k=1
        )[0]
        
        # اعطای جایزه
        if prize == "1 سکه":
            await self.coin_manager.add_coins(user_id, 1, "گردونه شانس")
            prize_msg = "🎉 شما 1 سکه برنده شدید!"
        elif prize == "3 سکه":
            await self.coin_manager.add_coins(user_id, 3, "گردونه شانس")
            prize_msg = "🎉 شما 3 سکه برنده شدید!"
        elif prize == "5 سکه":
            await self.coin_manager.add_coins(user_id, 5, "گردونه شانس")
            prize_msg = "🎉 شما 5 سکه برنده شدید!"
        elif prize == "10 سکه":
            await self.coin_manager.add_coins(user_id, 10, "گردونه شانس")
            prize_msg = "🎉 شما 10 سکه برنده شدید!"
        else:  # کد تخفیف
            discount_code = await self.coin_manager.generate_discount_code(user_id)
            prize_msg = f"🎉 شما یک کد تخفیف 10% برنده شدید!\n\nکد: `{discount_code}`\n\nاین کد به مدت 24 ساعت معتبر است."
        
        # ذخیره زمان آخرین چرخش
        await self.save_wheel_spin(user_id)
        
        await message.edit_caption(
            f"🎡 *نتیجه گردونه شانس*\n\n{prize_msg}\n\n"
            "می‌توانید فردا دوباره گردونه را بچرخانید.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ])
        )
        return WHEEL_OF_FORTUNE

    async def get_last_wheel_spin(self, user_id: int) -> Optional[datetime]:
        """دریافت زمان آخرین چرخش گردونه"""
        async with aiosqlite.connect(COINS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT last_wheel_spin FROM user_coins WHERE user_id = ?", (user_id,)
            )
            result = await cursor.fetchone()
            if result and result[0]:
                return datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            return None

    async def save_wheel_spin(self, user_id: int) -> bool:
        """ذخیره زمان آخرین چرخش گردونه"""
        try:
            async with aiosqlite.connect(COINS_DB_PATH) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO user_coins (user_id, last_wheel_spin)
                    VALUES (?, CURRENT_TIMESTAMP)
                    """,
                    (user_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            logger.error(f"خطا در ذخیره زمان چرخش گردونه: {e}")
            return False

    async def show_wheel_of_fortune(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش گردونه شانس"""
        user_id = update.effective_user.id
        
        # بررسی امکان چرخش گردونه
        last_spin = await self.get_last_wheel_spin(user_id)
        if last_spin and (datetime.now() - last_spin) < timedelta(hours=24):
            remaining_time = 24 - (datetime.now() - last_spin).seconds // 3600
            await update.callback_query.edit_message_text(
                f"⏳ شما امروز از گردونه شانس استفاده کرده‌اید. {remaining_time} ساعت دیگر می‌توانید دوباره بچرخانید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
                ])
            )
            return WHEEL_OF_FORTUNE
        
        wheel_image = await self.generate_wheel_image()
        
        await update.callback_query.message.reply_photo(
            photo=wheel_image,
            caption="🎡 *گردونه شانس*\n\nهر 24 ساعت یک بار می‌توانید گردونه را بچرخانید و جایزه بگیرید!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🌀 بچرخون!", callback_data="spin_wheel")],
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")],
            ]),
            parse_mode='Markdown'
        )
        await update.callback_query.message.delete()
        return WHEEL_OF_FORTUNE

    # *********************** پروفایل کاربری ***********************
    async def generate_profile_image(self, user_id: int, username: str, coins: int, 
                                   join_date: str, avatar: str, dark_mode: bool) -> bytes:
        """تولید کارت پروفایل گرافیکی"""
        bg_color = (30, 30, 60) if dark_mode else (240, 240, 240)
        text_color = (255, 255, 255) if dark_mode else (0, 0, 0)
        secondary_color = (200, 200, 255) if dark_mode else (100, 100, 150)
        
        img = Image.new('RGB', (800, 600), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # هدر
        draw.rectangle([(0, 0), (800, 80)], fill=(50, 50, 100))
        draw.text((20, 20), "پروفایل کاربری RedHotMafia", font=TITLE_FONT, fill=(255, 255, 255))
        
        # آواتار
        avatar_emoji = AVATARS.get(avatar, "🕴️")
        draw.text((50, 120), avatar_emoji, font=ImageFont.load_default(size=72), fill=text_color)
        
        # اطلاعات کاربر
        y_position = 120
        level = await self.coin_manager.get_user_level(coins)
        _, _, progress = await self.coin_manager.get_level_progress(coins)
        
        draw.text((200, y_position), f"👤 نام کاربری: {username}", font=MONO_FONT, fill=text_color)
        y_position += 40
        draw.text((200, y_position), f"🆔 شناسه کاربری: {user_id}", font=MONO_FONT, fill=text_color)
        y_position += 40
        draw.text((200, y_position), f"📅 تاریخ عضویت: {join_date}", font=MONO_FONT, fill=text_color)
        y_position += 40
        draw.text((200, y_position), f"🪙 سکه‌ها: {coins}", font=MONO_FONT, fill=text_color)
        y_position += 40
        draw.text((200, y_position), f"🏆 سطح: {level}", font=MONO_FONT, fill=text_color)
        y_position += 40
        
        # نوار پیشرفت
        draw.rectangle([(200, y_position), (600, y_position + 20)], outline=secondary_color, width=2)
        draw.rectangle([(200, y_position), (200 + (400 * progress // 100), y_position + 20)], fill=(0, 255, 0))
        draw.text((610, y_position), f"{progress}%", font=MONO_FONT, fill=text_color)
        
        # ذخیره تصویر در بایت
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()

    async def show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش پروفایل کاربر"""
        user = update.effective_user
        user_id = user.id
        
        # دریافت اطلاعات کاربر
        coins = await self.coin_manager.get_coins(user_id)
        avatar = await self.coin_manager.get_avatar(user_id)
        dark_mode = await self.coin_manager.get_dark_mode(user_id)
        
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT registered_at FROM users WHERE user_id = ?", (user_id,)
            )
            join_date = (await cursor.fetchone())[0] if await cursor.fetchone() else "نامشخص"
        
        # تولید تصویر پروفایل
        profile_image = await self.generate_profile_image(
            user_id, user.full_name, coins, join_date, avatar, dark_mode
        )
        
        keyboard = [
            [InlineKeyboardButton("🎡 گردونه شانس", callback_data="wheel_of_fortune")],
            [InlineKeyboardButton("👥 جدول رتبه‌بندی", callback_data="leaderboard")],
            [InlineKeyboardButton(f"🌙 تغییر به حالت {'روشن' if dark_mode else 'تاریک'}", callback_data="toggle_dark_mode")],
            [InlineKeyboardButton("🖼️ تغییر آواتار", callback_data="change_avatar")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")],
        ]
        
        await update.callback_query.message.reply_photo(
            photo=profile_image,
            caption=f"👤 *پروفایل کاربری*\n\n"
                   f"🪙 سکه‌های شما: {coins}\n"
                   f"🏆 سطح فعلی: {await self.coin_manager.get_user_level(coins)}",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        await update.callback_query.message.delete()
        return SELECTING_ACTION

    async def toggle_dark_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تغییر حالت تاریک/روشن"""
        user_id = update.effective_user.id
        success = await self.coin_manager.toggle_dark_mode(user_id)
        
        if success:
            await update.callback_query.answer("حالت نمایش تغییر کرد!")
        else:
            await update.callback_query.answer("خطا در تغییر حالت نمایش!", show_alert=True)
        
        return await self.show_profile(update, context)

    async def show_avatar_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش انتخاب آواتار"""
        user_id = update.effective_user.id
        coins = await self.coin_manager.get_coins(user_id)
        user_level = await self.coin_manager.get_user_level(coins)
        
        keyboard = []
        row = []
        
        for i, (avatar_key, avatar_name) in enumerate(AVATARS.items()):
            # بررسی سطح کاربر برای آواتارهای قفل شده
            if avatar_key in LOCKED_AVATARS:
                required_level = LOCKED_AVATARS[avatar_key]
                level_order = ["تازه کار", "فعال", "حرفه‌ای", "VIP"]
                current_index = level_order.index(user_level)
                required_index = level_order.index(required_level)
                
                if current_index < required_index:
                    avatar_name = f"🔒 {avatar_name} (نیاز به سطح {required_level})"
                    callback_data = "locked_avatar"
                else:
                    callback_data = f"select_avatar_{avatar_key}"
            else:
                callback_data = f"select_avatar_{avatar_key}"
            
            row.append(InlineKeyboardButton(avatar_name, callback_data=callback_data))
            if (i + 1) % 2 == 0:
                keyboard.append(row)
                row = []
        
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="profile")])
        
        await update.callback_query.edit_message_text(
            "🖼️ *انتخاب آواتار*\n\nلطفاً یکی از آواتارهای زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return AVATAR_SELECTION

    async def select_avatar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """انتخاب آواتار توسط کاربر"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "locked_avatar":
            await query.answer("این آواتار برای سطح شما قفل شده است!", show_alert=True)
            return AVATAR_SELECTION
        
        avatar_key = query.data.split("_")[2]
        user_id = update.effective_user.id
        
        success = await self.coin_manager.set_avatar(user_id, avatar_key)
        if success:
            await query.answer("آواتار شما با موفقیت تغییر کرد!")
        else:
            await query.answer("خطا در تغییر آواتار!", show_alert=True)
        
        return await self.show_profile(update, context)

    async def generate_leaderboard_image(self, leaderboard: List[Tuple], user_rank: Optional[int]) -> bytes:
        """تولید تصویر جدول رتبه‌بندی"""
        img = Image.new('RGB', (800, 600), color=(30, 30, 60))
        draw = ImageDraw.Draw(img)
        
        # هدر
        draw.rectangle([(0, 0), (800, 80)], fill=(50, 50, 100))
        draw.text((250, 20), "جدول رتبه‌بندی", font=TITLE_FONT, fill=(255, 255, 255))
        
        # اطلاعات رتبه‌بندی
        y_position = 100
        for i, (username, coins) in enumerate(leaderboard[:5], start=1):
            draw.text((50, y_position), f"{i}. {username}", font=MONO_FONT, fill=(200, 200, 255))
            draw.text((600, y_position), f"{coins} سکه", font=MONO_FONT, fill=(255, 215, 0))
            y_position += 40
        
        # نمایش رتبه کاربر
        if user_rank:
            draw.text((50, 500), f"رتبه شما: {user_rank}", font=TITLE_FONT, fill=(0, 255, 255))
        
        # ذخیره تصویر در بایت
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()

    async def show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش جدول رتبه‌بندی"""
        leaderboard = await self.coin_manager.get_leaderboard()
        user_id = update.effective_user.id
        user_rank = await self.coin_manager.get_user_rank(user_id)
        
        # تولید تصویر جدول رتبه‌بندی
        leaderboard_image = await self.generate_leaderboard_image(leaderboard, user_rank)
        
        await update.callback_query.message.reply_photo(
            photo=leaderboard_image,
            caption="🏆 *جدول رتبه‌بندی*\n\n5 کاربر برتر بر اساس تعداد سکه‌ها",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="profile")],
            ]),
            parse_mode='Markdown'
        )
        await update.callback_query.message.delete()
        return SELECTING_ACTION

    # *********************** مدیریت محصولات توسط ادمین ***********************
    async def admin_manage_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """مدیریت محصولات توسط ادمین"""
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("➕ افزودن محصول جدید", callback_data="add_product")],
            [InlineKeyboardButton("✏️ ویرایش محصول", callback_data="edit_product")],
            [InlineKeyboardButton("🗑️ حذف محصول", callback_data="remove_product")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin")],
        ]
        
        await query.edit_message_text(
            "🛍️ *مدیریت محصولات*\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ADMIN_MANAGE_PRODUCTS

    async def add_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """افزودن محصول جدید"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "لطفاً اطلاعات محصول را به فرمت زیر ارسال کنید:\n\n"
            "نام محصول\nقیمت (مثال: 0.00018 BTC)\nتوضیحات\nامکانات (با خط جدید و - جدا کنید)\nآدرس بیت کوین\nموجودی\n\n"
            "مثال:\n"
            "چیت بازی مافیا\n0.00018 BTC\nنمایش نقش‌های مخفی\n- امکان ضد بن\n- پشتیبانی 24 ساعته\n1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa\n5"
        )
        return ADMIN_MANAGE_PRODUCTS

    async def edit_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """ویرایش محصول"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for product_key in self.products.keys():
            keyboard.append([InlineKeyboardButton(self.products[product_key].name, callback_data=f"edit_{product_key}")])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="manage_products")])
        
        await query.edit_message_text(
            "✏️ *ویرایش محصول*\n\nلطفاً محصولی را که می‌خواهید ویرایش کنید انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ADMIN_MANAGE_PRODUCTS

    async def remove_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """حذف محصول"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for product_key in self.products.keys():
            keyboard.append([InlineKeyboardButton(self.products[product_key].name, callback_data=f"remove_{product_key}")])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="manage_products")])
        
        await query.edit_message_text(
            "🗑️ *حذف محصول*\n\nلطفاً محصولی را که می‌خواهید حذف کنید انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ADMIN_MANAGE_PRODUCTS

    async def process_add_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پردازش افزودن محصول جدید"""
        try:
            parts = update.message.text.split('\n')
            if len(parts) < 6:
                raise ValueError
            
            name = parts[0].strip()
            price = parts[1].strip()
            description = parts[2].strip()
            features = [f"- {f.strip()}" for f in parts[3].split('-') if f.strip()]
            btc_address = parts[4].strip()
            stock = int(parts[5].strip())
            
            # تولید کلید محصول
            product_key = name.lower().replace(' ', '_')
            
            # افزودن محصول جدید
            self.products[product_key] = Product(
                name=name,
                price=price,
                description=description,
                features=features,
                btc_address=btc_address,
                stock=stock
            )
            
            await update.message.reply_text(
    f"✅ محصول '{name}' با موفقیت افزوده شد!",
    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
    ])
)
            return ADMIN_ACTIONS
        except Exception as e:
            logger.error(f"خطا در افزودن محصول: {e}")
            await update.message.reply_text(
                "⚠️ خطا در پردازش اطلاعات محصول. لطفاً مطابق فرمت خواسته شده ارسال کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
                ])
            )
            return ADMIN_ACTIONS

    async def process_edit_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پردازش ویرایش محصول"""
        query = update.callback_query
        await query.answer()
        
        product_key = query.data.split('_')[1]
        product = self.products[product_key]
        
        context.user_data['editing_product'] = product_key
        
        await query.edit_message_text(
            f"✏️ *ویرایش محصول: {product.name}*\n\n"
            f"لطفاً اطلاعات جدید را به فرمت زیر ارسال کنید:\n\n"
            f"نام محصول\nقیمت\nتوضیحات\nامکانات (با خط جدید و - جدا کنید)\nآدرس بیت کوین\nموجودی\n\n"
            f"مثال:\n"
            f"{product.name}\n{product.price}\n{product.description}\n"
            f"{'\\n'.join(product.features)}\n{product.btc_address}\n{product.stock}",
            parse_mode='Markdown'
        )
        return ADMIN_MANAGE_PRODUCTS

    async def process_remove_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پردازش حذف محصول"""
        query = update.callback_query
        await query.answer()
        
        product_key = query.data.split('_')[1]
        product_name = self.products[product_key].name
        
        # حذف محصول
        del self.products[product_key]
        
        await query.edit_message_text(
            f"✅ محصول '{product_name}' با موفقیت حذف شد!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
            ])
        )
        return ADMIN_ACTIONS

    async def save_edited_product(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """ذخیره تغییرات محصول ویرایش شده"""
        try:
            product_key = context.user_data['editing_product']
            parts = update.message.text.split('\n')
            
            if len(parts) < 6:
                raise ValueError
            
            name = parts[0].strip()
            price = parts[1].strip()
            description = parts[2].strip()
            features = [f"- {f.strip()}" for f in parts[3].split('-') if f.strip()]
            btc_address = parts[4].strip()
            stock = int(parts[5].strip())
            
            # به‌روزرسانی محصول
            self.products[product_key] = Product(
                name=name,
                price=price,
                description=description,
                features=features,
                btc_address=btc_address,
                stock=stock
            )
            
            await update.message.reply_text(
                f"✅ محصول '{name}' با موفقیت به‌روزرسانی شد!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
                ])
            )
            return ADMIN_ACTIONS
        except Exception as e:
            logger.error(f"خطا در ویرایش محصول: {e}")
            await update.message.reply_text(
                "⚠️ خطا در پردازش اطلاعات محصول. لطفاً مطابق فرمت خواسته شده ارسال کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
                ])
            )
            return ADMIN_ACTIONS

    # *********************** مدیریت سکه‌ها توسط ادمین ***********************
    async def admin_add_coins_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """منوی افزودن سکه توسط ادمین"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            "💰 *افزودن سکه به کاربر*\n\n"
            "لطفاً شناسه کاربر و تعداد سکه را به فرمت زیر ارسال کنید:\n\n"
            "مثال:\n"
            "12345678 100\n\n"
            "این مقدار به موجودی سکه‌های کاربر اضافه خواهد شد.",
            parse_mode='Markdown'
        )
        return ADMIN_ADD_COINS

    async def process_admin_add_coins(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پردازش افزودن سکه توسط ادمین"""
        try:
            parts = update.message.text.split()
            if len(parts) != 2:
                raise ValueError
            
            user_id = int(parts[0])
            amount = int(parts[1])
            
            if amount <= 0:
                await update.message.reply_text("تعداد سکه باید بیشتر از صفر باشد.")
                return ADMIN_ADD_COINS
                
            success = await self.coin_manager.admin_add_coins(user_id, amount)
            
            if success:
                await update.message.reply_text(
    f"✅ {amount} سکه به کاربر {user_id} با موفقیت افزوده شد!",
    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
    ])
)
            else:
                await update.message.reply_text(
                    "⚠️ خطا در افزودن سکه. لطفاً دوباره تلاش کنید.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
                    ])
                )
            return ADMIN_ACTIONS
        except ValueError:
            await update.message.reply_text(
    "فرمت وارد شده صحیح نیست. لطفاً مطابق مثال عمل کنید.",
    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به مدیریت", callback_data="admin")]
    ])
)
            return ADMIN_ACTIONS

    # *********************** دستورات ربات ***********************
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """دستور شروع ربات"""
        try:
            await self.show_hacking_animation(update)
            await self.show_battery_animation(update)
            
            user = update.effective_user
            stats_msg = await self.get_stats_message()
            
            # دریافت اطلاعات کاربر
            balance = await self.wallet_manager.get_balance(user.id)
            coins = await self.coin_manager.get_coins(user.id)
            orders = await self.get_user_orders(user.id)
            referral_code = await self.referral_system.get_referral_code(user.id)
            avatar = await self.coin_manager.get_avatar(user.id)
            dark_mode = await self.coin_manager.get_dark_mode(user.id)
            
            async with aiosqlite.connect(USERS_DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT registered_at FROM users WHERE user_id = ?", (user.id,)
                )
                join_date = (await cursor.fetchone())[0] if await cursor.fetchone() else "نامشخص"
            
            # تولید کارت پروفایل
            profile_image = await self.generate_profile_image(
                user.id, user.full_name, coins, join_date, avatar, dark_mode
            )
            
            # ارسال تصویر پروفایل
            await update.message.reply_photo(
                photo=profile_image,
                caption=f"👋 سلام {user.full_name}!\n\nبه ربات فروشگاه RedHotMafia خوش آمدید!\n\n{stats_msg}",
                parse_mode='Markdown'
            )
            
            # منوی شیشه‌ای
            keyboard = [
                [InlineKeyboardButton("🎮 محصولات ما", callback_data="products")],
                [InlineKeyboardButton("📦 سفارشات من", callback_data="my_orders")],
                [InlineKeyboardButton("💰 کیف پول دیجیتال", callback_data="wallet")],
                [InlineKeyboardButton("👤 پروفایل کاربری", callback_data="profile")],
                [InlineKeyboardButton("👥 سیستم معرفی", callback_data="referral")],
                [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")],
                [InlineKeyboardButton("📚 راهنمای ربات", callback_data="help_command")],
            ]

            if self.is_admin(user.id):
                keyboard.append(
                    [InlineKeyboardButton("🔐 پنل مدیریت پیشرفته", callback_data="admin")]
                )

            await update.message.reply_text(
                "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            # شروع ارسال پیام‌های دوره‌ای
            if not self.daily_notification_task:
                self.daily_notification_task = asyncio.create_task(self.send_periodic_notifications(context))
            
            return SELECTING_ACTION

        except Exception as e:
            logger.error(f"خطا در شروع: {e}", exc_info=True)
            await update.message.reply_text("⚠️ خطای سیستمی! لطفا بعدا تلاش کنید.")
            return ConversationHandler.END

    async def generate_license_image(self, license_code: str) -> bytes:
        """تولید کارت لایسنس گرافیکی"""
        img = Image.new('RGB', (600, 300), color=(0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # افزودن افکت هکری
        for _ in range(50):
            x1, y1 = random.randint(0, 600), random.randint(0, 300)
            x2, y2 = random.randint(0, 600), random.randint(0, 300)
            draw.line([(x1, y1), (x2, y2)], fill=(0, 255, 0), width=1)
        
        # افزودن متن لایسنس
        draw.text((150, 100), "REDHOT MAFIA LICENSE", font=TITLE_FONT, fill=(0, 255, 0))
        draw.text((150, 150), license_code, font=TITLE_FONT, fill=(0, 255, 255))
        draw.text((150, 200), "Valid for 30 days", font=MONO_FONT, fill=(255, 255, 255))
        
        # ذخیره تصویر در بایت
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()

    async def send_license(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, license_code: str):
        """ارسال لایسنس به صورت گرافیکی"""
        license_image = await self.generate_license_image(license_code)
        
        await context.bot.send_photo(
            chat_id=user_id,
            photo=license_image,
            caption=f"🎉 *خرید شما با موفقیت تکمیل شد!*\n\n"
                   f"کد لایسنس شما:\n"
                   f"`{license_code}`\n\n"
                   f"این کد را در بازی وارد کنید تا فعال شود.",
            parse_mode='Markdown'
        )

    async def generate_invoice_image(self, order_details: dict) -> bytes:
        """تولید فاکتور گرافیکی"""
        img = Image.new('RGB', (800, 600), color=(240, 240, 240))
        draw = ImageDraw.Draw(img)
        
        # هدر فاکتور
        draw.rectangle([(0, 0), (800, 80)], fill=(30, 30, 60))
        draw.text((20, 20), "فاکتور سفارش RedHotMafia", font=TITLE_FONT, fill=(255, 255, 255))
        
        # جزئیات سفارش
        y_position = 100
        for key, value in order_details.items():
            draw.text((20, y_position), f"{key}: {value}", font=MONO_FONT, fill=(0, 0, 0))
            y_position += 30
        
        # ذخیره تصویر در بایت
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr.getvalue()

    async def view_user_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """مشاهده سفارشات کاربر با فاکتور گرافیکی"""
        user_id = update.effective_user.id
        orders = await self.get_user_orders(user_id)
        
        if not orders:
            await update.callback_query.edit_message_text(
                "شما تاکنون هیچ سفارشی ثبت نکرده‌اید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
                ])
            )
            return VIEWING_ORDERS
        
        for order in orders:
            order_id, product, price, tracking_code, status, timestamp = order
            order_details = {
                "شماره سفارش": order_id,
                "محصول": product,
                "قیمت": price,
                "کد پیگیری": tracking_code,
                "وضعیت": status,
                "تاریخ سفارش": timestamp
            }
            
            # تولید فاکتور گرافیکی
            invoice_image = await self.generate_invoice_image(order_details)
            
            await update.callback_query.message.reply_photo(
                photo=invoice_image,
                caption=f"سفارش #{order_id}",
            )
        
        await update.callback_query.message.reply_text(
            "برای بازگشت به منوی اصلی دکمه زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ])
        )
        return VIEWING_ORDERS

    async def show_product_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش جزئیات محصول با هشدار موجودی"""
        query = update.callback_query
        await query.answer()
        
        product_key = query.data.split("_")[1]
        product = self.products[product_key]
        
        # به روزرسانی موجودی محصول
        product.update_stock()
        
        # هشدار موجودی کم
        stock_warning = ""
        if product.stock <= 1:
            stock_warning = "\n\n⚠️ *هشدار: موجودی در حال اتمام است!*"
        
        # دکمه‌های شیشه‌ای
        keyboard = [
            [InlineKeyboardButton("💳 خرید محصول", callback_data=f"pay_{product_key}")],
            [InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="products")],
        ]
        
        await query.edit_message_text(
            product.get_info() + stock_warning,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECTING_ACTION

    async def payment_instructions(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """دستورات پرداخت"""
        query = update.callback_query
        await query.answer()
        
        product_key = query.data.split("_")[1]
        product = self.products[product_key]
        
        # ذخیره محصول انتخاب شده در context
        context.user_data["selected_product"] = product_key
        
        # بررسی موجودی محصول
        if product.stock <= 0:
            await query.edit_message_text(
                "⚠️ متأسفانه این محصول در حال حاضر موجود نیست. لطفاً محصول دیگری انتخاب کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="products")]
                ])
            )
            return SELECTING_ACTION
        
        await query.edit_message_text(
            f"💳 *روش پرداخت برای {product.name}*\n\n"
            f"1. مبلغ {product.price} را به آدرس زیر واریز کنید:\n"
            f"`{product.btc_address}`\n\n"
            f"2. پس از واریز، هش تراکنش (TX Hash) را برای ما ارسال کنید.\n\n"
            f"3. پرداخت شما حداکثر تا **1 ساعت** تأیید خواهد شد.\n\n"
            f"4. پس از تأیید، کد لایسنس به صورت خودکار برای شما ارسال می‌شود.\n\n"
            f"⚠️ توجه: در صورت عدم ارسال هش تراکنش در مدت 24 ساعت، سفارش شما لغو خواهد شد.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data=f"product_{product_key}")]
            ])
        )
        return CONFIRM_PAYMENT

    async def handle_tx_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پردازش هش تراکنش"""
        user = update.effective_user
        tx_hash = update.message.text.strip()
        
        if not re.match(r"^[a-fA-F0-9]{64}$", tx_hash):
            await update.message.reply_text(
                "فرمت هش تراکنش صحیح نیست. لطفاً یک هش تراکنش معتبر وارد کنید:"
            )
            return CONFIRM_PAYMENT
        
        # ذخیره سفارش
        tracking_code = self.generate_tracking_code()
        product_key = context.user_data.get("selected_product", "mafia")
        product = self.products[product_key]
        
        # بررسی مجدد موجودی محصول
        if product.stock <= 0:
            await update.message.reply_text(
                "⚠️ متأسفانه موجودی این محصول به پایان رسیده است. لطفاً محصول دیگری انتخاب کنید."
            )
            return await self.show_products(update, context)
        
        # کاهش موجودی محصول پس از تأیید پرداخت
        product.stock -= 1
        
        await self.save_order(
            user.id,
            user.full_name,
            product,
            tracking_code,
            tx_hash
        )
        
        # اطلاع به ادمین
        admin_msg = (
            f"📦 سفارش جدید!\n\n"
            f"👤 کاربر: {user.full_name} (@{user.username})\n"
            f"🆔 ID: {user.id}\n"
            f"📦 محصول: {product.name}\n"
            f"💰 قیمت: {product.price}\n"
            f"🛒 کد پیگیری: {tracking_code}\n"
            f"🔗 TX Hash: {tx_hash}"
        )
        
        await self.send_to_admin(context, admin_msg)
        
        # تأیید خودکار پرداخت بعد از 1 ساعت
        asyncio.create_task(self.auto_confirm_payment(tx_hash, user.id, tracking_code))
        
        await update.message.reply_text(
            f"✅ سفارش شما با موفقیت ثبت شد!\n\n"
            f"کد پیگیری: `{tracking_code}`\n\n"
            f"پرداخت شما حداکثر تا **1 ساعت** تأیید خواهد شد. پس از تأیید، کد لایسنس به صورت خودکار برای شما ارسال می‌شود.",
            parse_mode='Markdown'
        )
        
        context.user_data.clear()
        return await self.show_main_menu(update, context)

    async def auto_confirm_payment(self, tx_hash: str, user_id: int, tracking_code: str):
        """تأیید خودکار پرداخت بعد از 1 ساعت"""
        await asyncio.sleep(3600)  # 1 ساعت تأخیر
        
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT status FROM orders WHERE tx_hash = ?", (tx_hash,)
            )
            order = await cursor.fetchone()
            
            if order and order[0] == "pending":
                # تأیید خودکار
                await db.execute(
                    "UPDATE orders SET status = 'completed' WHERE tx_hash = ?",
                    (tx_hash,)
                )
                await db.commit()
                
                # ارسال لایسنس به کاربر
                await self.send_license(self.application.context, user_id, tracking_code)
                
                # اطلاع به کاربر
                await self.send_to_user(
                    self.application.context, 
                    user_id, 
                    f"🎉 پرداخت شما تأیید شد! کد لایسنس به شما ارسال گردید."
                )

    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """پنل مدیریت"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_admin(update.effective_user.id):
            await query.edit_message_text("⛔ دسترسی denied!")
            return ConversationHandler.END
        
        keyboard = [
            [InlineKeyboardButton("📋 مشاهده سفارشات", callback_data="view_orders")],
            [InlineKeyboardButton("📊 مشاهده آمار", callback_data="view_stats")],
            [InlineKeyboardButton("💰 مدیریت سکه‌ها", callback_data="admin_add_coins")],
            [InlineKeyboardButton("🛍️ مدیریت محصولات", callback_data="manage_products")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")],
        ]
        
        await query.edit_message_text(
            "🔐 *پنل مدیریت*\n\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ADMIN_ACTIONS

    async def view_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """مشاهده سفارشات برای ادمین"""
        query = update.callback_query
        await query.answer()
        
        orders = await self.get_all_orders()
        
        if not orders:
            await query.edit_message_text(
                "هیچ سفارشی ثبت نشده است.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="admin")]
                ])
            )
            return ADMIN_ACTIONS
        
        message = "📋 *لیست سفارشات*\n\n"
        for order in orders[:10]:  # نمایش 10 سفارش آخر
            order_id, user_id, full_name, product, price, tracking_code, status, timestamp = order
            message += (
                f"🆔 #{order_id}\n"
                f"👤 {full_name} (ID: {user_id})\n"
                f"📦 {product}\n"
                f"💰 {price}\n"
                f"🛒 کد پیگیری: {tracking_code}\n"
                f"📌 وضعیت: {status}\n"
                f"📅 {timestamp}\n\n"
            )
        
        keyboard = []
        for order in orders[:10]:
            order_id = order[0]
            if order[6] == 'pending':
                keyboard.append([
                    InlineKeyboardButton(f"✅ تأیید #{order_id}", callback_data=f"confirm_{order_id}"),
                    InlineKeyboardButton(f"❌ حذف #{order_id}", callback_data=f"delete_{order_id}")
                ])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin")])
        
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return ADMIN_ACTIONS

    async def view_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """مشاهده آمار برای ادمین"""
        query = update.callback_query
        await query.answer()
        
        online_users = self.stats_generator.get_online_users()
        successful_orders = self.stats_generator.get_successful_orders()
        
        async with aiosqlite.connect(USERS_DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            total_users = (await cursor.fetchone())[0]
            
            cursor = await db.execute("SELECT COUNT(*) FROM referrals")
            total_referrals = (await cursor.fetchone())[0]
        
        await query.edit_message_text(
            f"📊 *آمار سیستم*\n\n"
            f"👥 کاربران آنلاین: {online_users}\n"
            f"✅ خریدهای موفق: {successful_orders}\n"
            f"👤 کاربران ثبت‌نامی: {total_users}\n"
            f"🤝 معرفی‌های انجام شده: {total_referrals}\n\n"
            f"🔄 آخرین به‌روزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="admin")]
            ]),
            parse_mode='Markdown'
        )
        return ADMIN_ACTIONS

    async def confirm_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """تأیید سفارش توسط ادمین"""
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.split("_")[1])
        await self.update_order_status(order_id, "completed")
        
        order = await self.get_order(order_id)
        if order:
            tracking_code = order[5]
            user_id = order[1]
            
            # ارسال لایسنس به کاربر
            await self.send_license(context, user_id, tracking_code)
            
            await query.edit_message_text(
                f"✅ سفارش #{order_id} با موفقیت تأیید شد و کد لایسنس برای کاربر ارسال گردید."
            )
        
        return await self.view_orders(update, context)

    async def delete_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """حذف سفارش توسط ادمین"""
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.split("_")[1])
        await self.update_order_status(order_id, "canceled")
        
        await query.edit_message_text(
            f"❌ سفارش #{order_id} با موفقیت لغو شد."
        )
        
        return await self.view_orders(update, context)

    async def support_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """درخواست پشتیبانی"""
        query = update.callback_query
        await query.answer()
        
        if not self.support_username:
            await query.edit_message_text(
                "⚠️ اطلاعات پشتیبانی تنظیم نشده است. لطفاً با پشتیبانی تماس بگیرید."
            )
            return SUPPORT_CHAT
        
        await query.edit_message_text(
            f"🆘 *پشتیبانی*\n\n"
            f"لطفاً پیام خود را برای تیم پشتیبانی ارسال کنید.\n\n"
            f"📌 می‌توانید مستقیماً با آیدی زیر در تماس باشید:\n"
            f"@{self.support_username}",
            parse_mode='Markdown'
        )
        return SUPPORT_CHAT

    async def forward_to_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """ارسال پیام به پشتیبانی"""
        user = update.effective_user
        message = update.message.text
        
        if not self.support_username:
            await update.message.reply_text(
                "⚠️ اطلاعات پشتیبانی تنظیم نشده است. لطفاً بعداً تلاش کنید."
            )
            return await self.show_main_menu(update, context)
        
        support_msg = (
            f"📩 پیام جدید از کاربر:\n\n"
            f"👤 نام: {user.full_name}\n"
            f"🆔 ID: {user.id}\n"
            f"📝 پیام:\n{message}"
        )
        
        try:
            await context.bot.send_message(
                chat_id=f"@{self.support_username}",
                text=support_msg
            )
            await update.message.reply_text(
                "✅ پیام شما با موفقیت به پشتیبانی ارسال شد.\n\n"
                "به زودی با شما تماس گرفته خواهد شد."
            )
        except Exception as e:
            logger.error(f"خطا در ارسال پیام به پشتیبانی: {e}")
            await update.message.reply_text(
                "⚠️ خطا در ارسال پیام به پشتیبانی. لطفاً مستقیماً با آیدی زیر در تماس باشید:\n"
                f"@{self.support_username}"
            )
        
        return await self.show_main_menu(update, context)

    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش منوی اصلی"""
        user = update.effective_user
        
        keyboard = [
            [InlineKeyboardButton("🎮 محصولات ما", callback_data="products")],
            [InlineKeyboardButton("📦 سفارشات من", callback_data="my_orders")],
            [InlineKeyboardButton("💰 کیف پول", callback_data="wallet")],
            [InlineKeyboardButton("👤 پروفایل", callback_data="profile")],
            [InlineKeyboardButton("👥 معرفی دوستان", callback_data="referral")],
            [InlineKeyboardButton("🆘 پشتیبانی", callback_data="support")],
            [InlineKeyboardButton("📚 راهنما", callback_data="help_command")],
        ]

        if self.is_admin(user.id):
            keyboard.append(
                [InlineKeyboardButton("🔐 پنل مدیریت", callback_data="admin")]
            )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        return SELECTING_ACTION

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """لغو عملیات جاری"""
        await update.message.reply_text(
            "عملیات فعلی لغو شد.",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data.clear()
        return ConversationHandler.END

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """دستور راهنما"""
        help_text = f"""
📚 *راهنمای کامل ربات RedHotMafia*

🔹 *منوی اصلی*:
- 🎮 محصولات ما: مشاهده و خرید محصولات
- 📦 سفارشات من: پیگیری سفارشات قبلی
- 💰 کیف پول: مدیریت موجودی و تراکنش‌های بیت کوین
- 👤 پروفایل: مشاهده اطلاعات حساب کاربری
- 👥 معرفی دوستان: دریافت پاداش با دعوت دوستان
- 🆘 پشتیبانی: ارتباط با تیم پشتیبانی
- 📚 راهنما: نمایش این صفحه

🔹 *سیستم کیف پول*:
- واریز بیت کوین به کیف پول ربات
- برداشت بیت کوین به آدرس دیگر (حداقل 0.0005 BTC)
- تبدیل سکه به بیت کوین (هر 300 سکه = 0.00002 BTC)
- مشاهده تاریخچه تراکنش‌ها

🔹 *سیستم سکه‌ها*:
- خرید موفق: 50 سکه
- ثبت نام: 10 سکه
- ورود روزانه: 5 سکه
- برداشت از کیف پول: 20 سکه
- معرفی دوستان: 10 سکه به ازای هر معرفی

🔹 *گردونه شانس*:
- هر 24 ساعت یک بار می‌توانید گردونه را بچرخانید
- جوایز احتمالی: 1, 3, 5, 10 سکه یا کد تخفیف 10%

🔹 *سیستم معرفی دوستان*:
- دریافت کد معرف شخصی
- دعوت دوستان با لینک اختصاصی
- دریافت 50,000 تومان بیت کوین برای هر 10 معرفی موفق

🔹 *روش خرید*:
1. انتخاب محصول از منو
2. واریز مبلغ به آدرس بیت کوین محصول
3. ارسال هش تراکنش (TX Hash)
4. پرداخت شما حداکثر تا 1 ساعت تأیید می‌شود
5. دریافت خودکار کد لایسنس + پنل

🔹 *گارانتی بازگشت وجه*:
- در صورت مشکل در لایسنس تا 7 روز می‌توانید درخواست بازگشت وجه دهید

🆘 پشتیبانی: {self.support_username if self.support_username else "تنظیم نشده"}
📢 کانال ما: {self.channel_username if self.channel_username else "تنظیم نشده"}
"""
        await update.callback_query.edit_message_text(
            help_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ])
        )
        return SELECTING_ACTION

    async def show_products(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """نمایش لیست محصولات"""
        query = update.callback_query
        await query.answer()
        
        keyboard = []
        for product_key, product in self.products.items():
            # به روزرسانی موجودی محصول
            product.update_stock()
            
            # نمایش موجودی در دکمه
            stock_indicator = "🟢" if product.stock > 2 else "🟡" if product.stock > 0 else "🔴"
            keyboard.append([
                InlineKeyboardButton(
                    f"{product.name} {stock_indicator}",
                    callback_data=f"product_{product_key}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
        
        await query.edit_message_text(
            "🎮 *لیست محصولات*\n\nلطفاً یکی از محصولات زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return SELECTING_ACTION

    async def send_periodic_notifications(self, context: ContextTypes.DEFAULT_TYPE):
        """ارسال پیام‌های دوره‌ای به کاربران"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # محاسبه زمان خواب تا ساعت 12 ظهر روز بعد
                now = datetime.now()
                target_time = now.replace(hour=12, minute=0, second=0, microsecond=0)
                if now > target_time:
                    target_time += timedelta(days=1)
                
                sleep_seconds = (target_time - now).total_seconds()
                await asyncio.sleep(sleep_seconds)
                
                # ارسال پیام به تمام کاربران
                async with aiosqlite.connect(USERS_DB_PATH) as db:
                    cursor = await db.execute("SELECT user_id FROM users")
                    users = await cursor.fetchall()
                    
                    tasks = []
                    for (user_id,) in users:
                        try:
                            # تولید محتوای پیام
                            online_users = self.stats_generator.get_online_users()
                            successful_orders = self.stats_generator.get_successful_orders()
                            
                            message = (
                                "📢 *اطلاعیه روزانه RedHotMafia*\n\n"
                                f"👥 کاربران آنلاین امروز: {online_users} نفر\n"
                                f"✅ خریدهای موفق: {successful_orders} نفر\n\n"
                                "🎁 پیشنهاد ویژه امروز:\n"
                                "با خرید هر دو محصول، 20% تخفیف دریافت کنید!\n\n"
                                f"📢 کانال ما: {self.channel_username}"
                            )
                            
                            # ارسال پیام
                            tasks.append(
                                context.bot.send_message(
                                    chat_id=user_id,
                                    text=message,
                                    parse_mode='Markdown'
                                )
                            )
                        except Exception as e:
                            logger.error(f"خطا در ارسال پیام به کاربر {user_id}: {e}")
                    
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                retry_count = 0  # Reset retry count after successful run
                
            except Exception as e:
                logger.error(f"خطا در ارسال پیام‌های دوره‌ای: {e}")
                retry_count += 1
                await asyncio.sleep(3600)  # در صورت خطا 1 ساعت صبر کن

    def setup_handlers(self, application: Application) -> None:
        """تنظیم هندلرهای ربات"""
        # هندلر احراز هویت
        auth_conv = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.handle_referral_start),
                CallbackQueryHandler(self.login, pattern="^login$"),
                CallbackQueryHandler(self.start_auth, pattern="^register$"),
                CallbackQueryHandler(self.check_channel_membership, pattern="^check_membership$"),
            ],
            states={
                CHANNEL_CHECK: [
                    CallbackQueryHandler(self.check_channel_membership, pattern="^check_membership$"),
                ],
                REGISTER_EMAIL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_email)
                ],
                REGISTER_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.register_password)
                ],
                LOGIN_EMAIL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.login_email)
                ],
                LOGIN_PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.login_password)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        
        # هندلر کیف پول
        wallet_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.show_wallet, pattern="^wallet$")],
            states={
                WALLET_ACTIONS: [
                    CallbackQueryHandler(self.deposit_btc, pattern="^deposit_btc$"),
                    CallbackQueryHandler(self.withdraw_btc, pattern="^withdraw_btc$"),
                    CallbackQueryHandler(self.convert_coins, pattern="^convert_coins$"),
                    CallbackQueryHandler(self.confirm_convert_coins, pattern="^confirm_convert_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_withdrawal),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.show_main_menu, pattern="^back$")],
        )
        
        # هندلر گردونه شانس
        wheel_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.show_wheel_of_fortune, pattern="^wheel_of_fortune$")],
            states={
                WHEEL_OF_FORTUNE: [
                    CallbackQueryHandler(self.spin_wheel, pattern="^spin_wheel$"),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.show_profile, pattern="^back$")],
        )
        
        # هندلر آواتار
        avatar_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.show_avatar_selection, pattern="^change_avatar$")],
            states={
                AVATAR_SELECTION: [
                    CallbackQueryHandler(self.select_avatar, pattern="^select_avatar_"),
                    CallbackQueryHandler(self.select_avatar, pattern="^locked_avatar$"),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.show_profile, pattern="^profile$")],
        )
        
        # هندلر مدیریت محصولات
        products_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.admin_manage_products, pattern="^manage_products$")],
            states={
                ADMIN_MANAGE_PRODUCTS: [
                    CallbackQueryHandler(self.add_product, pattern="^add_product$"),
                    CallbackQueryHandler(self.edit_product, pattern="^edit_product$"),
                    CallbackQueryHandler(self.remove_product, pattern="^remove_product$"),
                    CallbackQueryHandler(self.process_edit_product, pattern="^edit_"),
                    CallbackQueryHandler(self.process_remove_product, pattern="^remove_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_add_product),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_edited_product),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.admin_panel, pattern="^admin$")],
        )
        
        # هندلر مدیریت سکه‌ها
        coins_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.admin_add_coins_menu, pattern="^admin_add_coins$")],
            states={
                ADMIN_ADD_COINS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_admin_add_coins),
                ],
            },
            fallbacks=[CallbackQueryHandler(self.admin_panel, pattern="^admin$")],
        )
        
        # هندلر اصلی
        main_conv = ConversationHandler(
            entry_points=[CommandHandler("start", self.handle_referral_start)],
            states={
                SELECTING_ACTION: [
                    CallbackQueryHandler(self.show_products, pattern="^products$"),
                    CallbackQueryHandler(self.show_product_details, pattern="^product_"),
                    CallbackQueryHandler(self.payment_instructions, pattern="^pay_"),
                    CallbackQueryHandler(self.support_request, pattern="^support$"),
                    CallbackQueryHandler(self.admin_panel, pattern="^admin$"),
                    CallbackQueryHandler(self.view_user_orders, pattern="^my_orders$"),
                    CallbackQueryHandler(self.show_wallet, pattern="^wallet$"),
                    CallbackQueryHandler(self.show_profile, pattern="^profile$"),
                    CallbackQueryHandler(self.show_referral, pattern="^referral$"),
                    CallbackQueryHandler(self.help_command, pattern="^help_command$"),
                    CallbackQueryHandler(self.show_wheel_of_fortune, pattern="^wheel_of_fortune$"),
                    CallbackQueryHandler(self.show_leaderboard, pattern="^leaderboard$"),
                    CallbackQueryHandler(self.admin_add_coins_menu, pattern="^admin_add_coins$"),
                    CallbackQueryHandler(self.admin_manage_products, pattern="^manage_products$"),
                ],
                CONFIRM_PAYMENT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_tx_hash),
                ],
                ADMIN_ACTIONS: [
                    CallbackQueryHandler(self.view_orders, pattern="^view_orders$"),
                    CallbackQueryHandler(self.view_stats, pattern="^view_stats$"),
                    CallbackQueryHandler(self.confirm_order, pattern="^confirm_"),
                    CallbackQueryHandler(self.delete_order, pattern="^delete_"),
                    CallbackQueryHandler(self.show_main_menu, pattern="^back$"),
                    CallbackQueryHandler(self.admin_add_coins_menu, pattern="^admin_add_coins$"),
                    CallbackQueryHandler(self.admin_manage_products, pattern="^manage_products$"),
                ],
                SUPPORT_CHAT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.forward_to_support)
                ],
                VIEWING_ORDERS: [
                    CallbackQueryHandler(self.show_main_menu, pattern="^back$"),
                ],
                REFERRAL_MENU: [
                    CallbackQueryHandler(self.show_main_menu, pattern="^back$"),
                ],
                ADMIN_ADD_COINS: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_admin_add_coins),
                    CallbackQueryHandler(self.admin_panel, pattern="^admin$"),
                ],
                ADMIN_MANAGE_PRODUCTS: [
                    CallbackQueryHandler(self.add_product, pattern="^add_product$"),
                    CallbackQueryHandler(self.edit_product, pattern="^edit_product$"),
                    CallbackQueryHandler(self.remove_product, pattern="^remove_product$"),
                    CallbackQueryHandler(self.process_edit_product, pattern="^edit_"),
                    CallbackQueryHandler(self.process_remove_product, pattern="^remove_"),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.process_add_product),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.save_edited_product),
                    CallbackQueryHandler(self.admin_panel, pattern="^admin$"),
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        
        application.add_handler(auth_conv)
        application.add_handler(wallet_conv)
        application.add_handler(wheel_conv)
        application.add_handler(avatar_conv)
        application.add_handler(products_conv)
        application.add_handler(coins_conv)
        application.add_handler(main_conv)
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("stats", self.stats_command))
        application.add_handler(
            CommandHandler("orders", self.view_orders, filters.User(self.admin_id))
        )
        application.add_handler(
            CommandHandler("admin_stats", self.view_stats, filters.User(self.admin_id))
        )
        application.add_handler(
            CommandHandler("add_coins", self.admin_add_coins_menu, filters.User(self.admin_id))
        )

    async def run(self) -> None:
        """اجرای ربات"""
        try:
            await self.init_db()
            
            application = Application.builder().token(self.bot_token).build()
            self.setup_handlers(application)
            self.application = application  # برای دسترسی در متدهای دیگر

            logger.info("""
██████╗ ███████╗██████╗ ██╗  ██╗ ██████╗ ████████╗
██╔══██╗██╔════╝██╔══██╗██║  ██║██╔═══██╗╚══██╔══╝
██████╔╝█████╗  ██║  ██║███████║██║   ██║   ██║   
██╔══██╗██╔══╝  ██║  ██║██╔══██║██║   ██║   ██║   
██║  ██║███████╗██████╔╝██║  ██║╚██████╔╝   ██║   
╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝    ╚═╝   
            """)
            logger.info("ربات فروشگاه RedHotMafia با موفقیت راه‌اندازی شد!")

            await application.run_polling(drop_pending_updates=True)

        except Exception as e:
            logger.critical(f"خطا در راه‌اندازی ربات: {e}", exc_info=True)
            if self.daily_notification_task:
                self.daily_notification_task.cancel()


if __name__ == "__main__":
    bot = ShopBot()
    asyncio.run(bot.run())
