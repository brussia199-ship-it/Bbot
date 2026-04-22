import logging
import sqlite3
import time
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher.filters import Command
from aiogram.utils import executor

# КОНФИГУРАЦИЯ
BOT_TOKEN = "8600527005:AAFYeIcMzjKfIkn41amkWkJ2_eqIoddiF5E"
ADMIN_IDS = [7673683792]
STARS_PRICE = 50
MOSCOW_OFFSET = 3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ========== БАЗА ДАННЫХ ==========
@contextmanager
def get_db():
    conn = sqlite3.connect('sms_bomber.db')
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                subscription_end DATETIME,
                subscription_active BOOLEAN DEFAULT 0,
                total_attacks INTEGER DEFAULT 0,
                joined_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logger.info("База данных готова")

def get_moscow_time():
    return datetime.now() + timedelta(hours=MOSCOW_OFFSET)

def check_subscription(user_id: int) -> bool:
    with get_db() as conn:
        result = conn.execute(
            "SELECT subscription_active, subscription_end FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not result or not result['subscription_active']:
            return False
        end_date = datetime.strptime(result['subscription_end'], '%Y-%m-%d %H:%M:%S')
        if end_date > datetime.now():
            return True
        conn.execute("UPDATE users SET subscription_active = 0 WHERE user_id = ?", (user_id,))
        return False

def add_subscription(user_id: int, days: int = 30):
    end_date = datetime.now() + timedelta(days=days)
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO users (user_id, subscription_active, subscription_end)
            VALUES (?, 1, ?)
        ''', (user_id, end_date.strftime('%Y-%m-%d %H:%M:%S')))

def remove_subscription(user_id: int):
    with get_db() as conn:
        conn.execute("UPDATE users SET subscription_active = 0 WHERE user_id = ?", (user_id,))

def register_user(user_id: int, username: str = None, first_name: str = None):
    with get_db() as conn:
        conn.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))

def get_user_stats(user_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else {}

def get_bot_stats():
    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
        active_subs = conn.execute("SELECT COUNT(*) as count FROM users WHERE subscription_active = 1").fetchone()['count']
        total_attacks = conn.execute("SELECT SUM(total_attacks) as sum FROM users").fetchone()['sum'] or 0
        return {'total_users': total_users, 'active_subs': active_subs, 'total_attacks': total_attacks}

async def send_sms(phone: str, count: int = 50) -> int:
    """Имитация отправки SMS"""
    apis = [
        f"https://api.sms-service.com/send?phone={phone}",
        f"https://api.sms-bomber.net/attack?number={phone}",
        f"https://api.sms-flood.com/start?target={phone}"
    ]
    success_count = 0
    async with aiohttp.ClientSession() as session:
        for _ in range(count):
            api = random.choice(apis)
            try:
                async with session.get(api, timeout=3) as resp:
                    if resp.status == 200:
                        success_count += 1
            except:
                pass
            await asyncio.sleep(0.05)
    return success_count

# ========== КОМАНДЫ ==========
@dp.message_handler(Command('start'))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    register_user(user_id, message.from_user.username, message.from_user.first_name)
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("💣 Купить подписку (50 ⭐️)", callback_data="buy_subscription"),
        InlineKeyboardButton("ℹ️ Инфо", callback_data="info")
    )
    
    await message.answer(
        "🔥 <b>SMS Bomber Bot</b> 🔥\n\n"
        "Отправляйте массовые SMS на номера!\n\n"
        f"Подписка: {STARS_PRICE} Telegram Stars\n"
        "Команды:\n"
        "/sms <номер> - Запустить атаку\n"
        "/status - Статус бота\n"
        "/help - Помощь",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.message_handler(Command('help'))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Помощь по командам</b>\n\n"
        "/start - Запуск бота\n"
        "/sms <номер> - SMS атака (нужна подписка)\n"
        "/status - Статус бота\n"
        "/help - Это сообщение",
        parse_mode="HTML"
    )

@dp.message_handler(Command('status'))
async def cmd_status(message: Message):
    start_time = time.time()
    await asyncio.sleep(0.05)
    ping = round((time.time() - start_time) * 1000)
    moscow_time = get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
    stats = get_bot_stats()
    
    await message.answer(
        f"📊 <b>Статус бота</b>\n\n"
        f"🟢 Статус: <code>Работает</code>\n"
        f"🏓 Пинг: <code>{ping} мс</code>\n"
        f"🕐 Время (МСК+3): <code>{moscow_time}</code>\n"
        f"👥 Всего пользователей: <code>{stats['total_users']}</code>\n"
        f"💎 Активных подписок: <code>{stats['active_subs']}</code>\n"
        f"💣 Всего атак: <code>{stats['total_attacks']}</code>",
        parse_mode="HTML"
    )

@dp.message_handler(Command('sms'))
async def cmd_sms(message: Message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("💎 Купить подписку", callback_data="buy_subscription")
        )
        await message.answer(
            f"❌ <b>Доступ запрещён!</b>\n\n"
            f"Для использования команды /sms необходимо оформить подписку.\n"
            f"Стоимость: {STARS_PRICE} Telegram Stars",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        return
    
    args = message.get_args()
    if not args:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Использование: <code>/sms +79991234567</code>",
            parse_mode="HTML"
        )
        return
    
    phone = args.strip()
    if not phone.startswith('+') or len(phone) < 10:
        await message.answer(
            "❌ <b>Неверный формат номера!</b>\n\n"
            "Пример: <code>/sms +79001234567</code>",
            parse_mode="HTML"
        )
        return
    
    status_msg = await message.answer(
        f"💣 <b>Запуск атаки на номер {phone}</b>\n\n"
        "🔄 Отправка SMS...",
        parse_mode="HTML"
    )
    
    sent = await send_sms(phone, count=50)
    
    with get_db() as conn:
        conn.execute("UPDATE users SET total_attacks = total_attacks + 1 WHERE user_id = ?", (user_id,))
    
    await status_msg.edit_text(
        f"✅ <b>Атака завершена!</b>\n\n"
        f"📱 Номер: <code>{phone}</code>\n"
        f"📨 Отправлено: <code>{sent}/50</code>\n"
        f"👤 Выполнил: {message.from_user.first_name}",
        parse_mode="HTML"
    )

# ========== АДМИН-КОМАНДЫ ==========
@dp.message_handler(Command('admin'))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Нет доступа!")
        return
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton("👥 Выдать подписку", callback_data="admin_give_sub"),
        InlineKeyboardButton("🔴 Забрать подписку", callback_data="admin_remove_sub"),
        InlineKeyboardButton("📢 Рассылка", callback_data="admin_mailing"),
        InlineKeyboardButton("🔍 Проверить профиль", callback_data="admin_check_user")
    )
    
    await message.answer(
        "👑 <b>Админ-панель</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_'))
async def admin_callbacks(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет доступа!", show_alert=True)
        return
    
    data = callback.data
    
    if data == "admin_stats":
        stats = get_bot_stats()
        await callback.message.edit_text(
            f"📊 <b>Статистика</b>\n\n"
            f"👥 Пользователей: {stats['total_users']}\n"
            f"💎 Активных подписок: {stats['active_subs']}\n"
            f"💣 Всего атак: {stats['total_attacks']}",
            parse_mode="HTML"
        )
    
    elif data == "admin_give_sub":
        await callback.message.edit_text(
            "📝 <b>Выдача подписки</b>\n\n"
            "Команда: <code>/give_sub user_id days</code>\n"
            "Пример: <code>/give_sub 123456789 30</code>",
            parse_mode="HTML"
        )
    
    elif data == "admin_remove_sub":
        await callback.message.edit_text(
            "📝 <b>Удаление подписки</b>\n\n"
            "Команда: <code>/remove_sub user_id</code>",
            parse_mode="HTML"
        )
    
    elif data == "admin_check_user":
        await callback.message.edit_text(
            "🔍 <b>Проверка профиля</b>\n\n"
            "Команда: <code>/check_user user_id</code>",
            parse_mode="HTML"
        )
    
    elif data == "admin_mailing":
        await callback.message.edit_text(
            "📢 <b>Рассылка</b>\n\n"
            "Команда: <code>/mailing текст сообщения</code>",
            parse_mode="HTML"
        )
    
    await callback.answer()

@dp.message_handler(Command('give_sub'))
async def give_sub(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.get_args().split()
    if len(args) != 2:
        await message.answer("❌ Использование: /give_sub <user_id> <days>")
        return
    try:
        uid, days = int(args[0]), int(args[1])
        add_subscription(uid, days)
        await message.answer(f"✅ Подписка выдана {uid} на {days} дней")
    except:
        await message.answer("❌ Ошибка!")

@dp.message_handler(Command('remove_sub'))
async def remove_sub(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.get_args()
    if not args:
        await message.answer("❌ Использование: /remove_sub <user_id>")
        return
    try:
        uid = int(args)
        remove_subscription(uid)
        await message.answer(f"✅ Подписка удалена у {uid}")
    except:
        await message.answer("❌ Ошибка!")

@dp.message_handler(Command('check_user'))
async def check_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.get_args()
    if not args:
        await message.answer("❌ Использование: /check_user <user_id>")
        return
    try:
        uid = int(args)
        data = get_user_stats(uid)
        if data:
            await message.answer(
                f"👤 <b>Профиль</b>\n\n"
                f"ID: <code>{data.get('user_id')}</code>\n"
                f"Имя: {data.get('first_name', '-')}\n"
                f"Подписка: {'✅ Да' if data.get('subscription_active') else '❌ Нет'}\n"
                f"Атак: {data.get('total_attacks', 0)}",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Не найден")
    except:
        await message.answer("❌ Ошибка!")

@dp.message_handler(Command('mailing'))
async def mailing(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.get_args()
    if not text:
        await message.answer("❌ Использование: /mailing <текст>")
        return
    
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()
    
    ok, fail = 0, 0
    status = await message.answer(f"📢 Рассылка для {len(users)} пользователей...")
    
    for user in users:
        try:
            await bot.send_message(user['user_id'], text, parse_mode="HTML")
            ok += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    
    await status.edit_text(f"✅ Готово!\n📨 Отправлено: {ok}\n❌ Ошибок: {fail}")

# ========== ПОКУПКА ПОДПИСКИ ==========
@dp.callback_query_handler(lambda c: c.data == "buy_subscription")
async def buy_subscription(callback: CallbackQuery):
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⭐️ Оплатить 50 Stars", callback_data="pay_50_stars"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")
    )
    await callback.message.edit_text(
        f"💎 <b>Покупка подписки</b>\n\nСтоимость: {STARS_PRICE} Stars\nДлительность: 30 дней",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "pay_50_stars")
async def pay_subscription(callback: CallbackQuery):
    uid = callback.from_user.id
    add_subscription(uid, 30)
    await callback.message.edit_text(
        "✅ <b>Подписка активирована на 30 дней!</b>\n\n"
        "Теперь вы можете использовать /sms",
        parse_mode="HTML"
    )
    await callback.answer("Подписка активирована!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "back_to_start")
async def back_to_start(callback: CallbackQuery):
    await cmd_start(callback.message)
    await callback.answer()

@dp.callback_query_handler(lambda c: c.data == "info")
async def show_info(callback: CallbackQuery):
    await callback.message.edit_text(
        f"ℹ️ <b>SMS Bomber Bot</b>\n\n"
        f"Версия: 1.0\n"
        f"Подписка: {STARS_PRICE} Stars / 30 дней\n"
        f"👑 Админ: @me_mapaevv",
        parse_mode="HTML"
    )
    await callback.answer()

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    init_db()
    print("✅ Бот запущен!")
    executor.start_polling(dp, skip_updates=True)
