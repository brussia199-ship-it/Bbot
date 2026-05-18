import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from config import API_TOKEN
import keyboard as kb
from onesec_api import Mailbox
import asyncio

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


@dp.message(lambda message: message.text == '✉️ Получить почту')
async def get_email_handler(m: types.Message):
    ma = Mailbox('')
    email = f'{ma._mailbox_}@1secmail.com'
    await m.answer(f'📫 Твоя почта: {email}\n\nОтправляй письмо, почта проверяется автоматически, каждые 5 секунд, если придет новое письмо, мы вас об этом оповестим!\n\nНа 1 почту можно получить только - 1 письмо.\n\nРЕКОМЕНДУЕМ ПОДПИСАТЬСЯ НА НАШ КАНАЛ @UrallProject')
    
    while True:
        mb = ma.filtred_mail()
        if isinstance(mb, list) and mb:
            mf = ma.mailjobs('read', mb[0])
            js = mf.json()
            fromm = js['from']
            theme = js['subject']
            mes = js['textBody']
            await m.answer(f'📩 Новое письмо:\n<b>От</b>: {fromm}\n<b>Тема</b>: {theme}\n<b>Сообщение</b>: {mes}', reply_markup=kb.menu, parse_mode='HTML')
            break
        await asyncio.sleep(5)


@dp.message()
async def start_handler(m: types.Message):
    await m.answer(f'Приветствую тебя, {m.from_user.mention}\nЭтот бот создан для быстрого получения временной почты.\nНажми на кнопку ниже 👇', reply_markup=kb.menu)


if __name__ == '__main__':
    dp.run_polling(bot, skip_updates=True)
