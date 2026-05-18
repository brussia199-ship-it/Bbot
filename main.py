from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
import asyncio
import aiohttp
import json

API_TOKEN = '8596007073:AAFNvB6Zcl76uQGCkFGmU-n20euQeMXscgc'
onesecmail = 'https://www.1secmail.com/api/v1/'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_emails = {}

def get_main_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📧 Получить новую почту")],
            [KeyboardButton(text="🔄 Создать новый ящик")],
            [KeyboardButton(text="📬 Проверить почту")],
            [KeyboardButton(text="📋 Мой email")]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command('start'))
async def start_cmd(message: types.Message):
    await message.answer(
        "Приветствую вас в боте для создания временных почт!\n"
        "Используйте кнопки ниже для управления:",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "📧 Получить новую почту")
async def get_temp_mail(message: types.Message):
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{onesecmail}?action=genRandomMailbox&count=1') as response:
            email = (await response.json())[0]
            user_emails[message.from_user.id] = email
            await message.answer(
                f"✉️ Ваш новый временный email:\n`{email}`\n\n"
                "Используйте кнопку «📬 Проверить почту» для проверки входящих сообщений",
                parse_mode="Markdown"
            )

@dp.message(F.text == "🔄 Создать новый ящик")
async def create_new_mailbox(message: types.Message):
    """Функция для создания нового почтового ящика (удаляет старый и создаёт новый)"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f'{onesecmail}?action=genRandomMailbox&count=1') as response:
            email = (await response.json())[0]
            user_emails[message.from_user.id] = email
            await message.answer(
                f"✨ **Создан новый почтовый ящик!** ✨\n\n"
                f"✉️ Ваш новый email:\n`{email}`\n\n"
                "💡 *Совет:* старая почта больше неактивна, все письма будут приходить сюда",
                parse_mode="Markdown"
            )

@dp.message(F.text == "📋 Мой email")
async def show_current_email(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_emails:
        await message.answer(
            "❌ У вас пока нет временной почты.\n"
            "Нажмите «📧 Получить новую почту» или «🔄 Создать новый ящик» чтобы создать почтовый ящик."
        )
        return
    await message.answer(
        f"📋 Ваш текущий email:\n`{user_emails[user_id]}`",
        parse_mode="Markdown"
    )

@dp.message(F.text == "📬 Проверить почту")
async def check_mail(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_emails:
        await message.answer(
            "❌ Сначала получите временную почту!\n"
            "Нажмите «📧 Получить новую почту» или «🔄 Создать новый ящик»"
        )
        return
    
    email = user_emails[user_id]
    username, domain = email.split('@')
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f'{onesecmail}?action=getMessages&login={username}&domain={domain}'
        ) as response:
            messages = await response.json()
            
            if not messages:
                await message.answer("📭 Входящих сообщений нет")
                return
            
            for msg in messages:
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text="📄 Читать сообщение",
                        callback_data=f"read_msg_{msg['id']}"
                    )]
                ])
                await message.answer(
                    f"📬 Новое сообщение:\n"
                    f"От: {msg['from']}\n"
                    f"Тема: {msg['subject']}\n"
                    f"Дата: {msg['date']}",
                    reply_markup=keyboard
                )

@dp.callback_query(F.data.startswith("read_msg_"))
async def read_message(callback: types.CallbackQuery):
    msg_id = callback.data.split('_')[2]
    user_id = callback.from_user.id
    
    if user_id not in user_emails:
        await callback.message.answer("❌ Ваш почтовый ящик не найден")
        await callback.answer()
        return
    
    email = user_emails[user_id]
    username, domain = email.split('@')
    
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f'{onesecmail}?action=readMessage&login={username}&domain={domain}&id={msg_id}'
        ) as response:
            msg_data = await response.json()
            
            await callback.message.answer(
                f"📩 **Сообщение:**\n\n"
                f"📤 **От:** {msg_data['from']}\n"
                f"📎 **Тема:** {msg_data['subject']}\n"
                f"📅 **Дата:** {msg_data['date']}\n\n"
                f"📝 **Текст:**\n\n{msg_data['textBody']}",
                parse_mode="Markdown"
            )
            await callback.answer()

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
