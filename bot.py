import asyncio
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    base_path = Path(sys._MEIPASS)
    load_dotenv(dotenv_path=base_path / '.env')
else:
    load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from parser import UksivtParser
from formatter import format_schedule_response

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID", 49))

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")

bot = Bot(token=TOKEN)
dp = Dispatcher()
parser = UksivtParser(group_id=GROUP_ID)


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📅 На сегодня"),
            KeyboardButton(text="🗓 На неделю")
        ],
        [
            KeyboardButton(text="👨🏻‍💻 Разработчик")
        ]
    ],
    resize_keyboard=True
)


dev_inline_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 Написать разработчику", url="https://t.me/freakbanned")
        ]
    ]
)


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user = message.from_user
    logging.info(f"🚀 Старт от {user.full_name} (@{user.username} | ID: {user.id})")
    await message.answer(
        "Привет! Я бот расписания УКСиВТ.\nВыбери нужный вариант ниже:",
        reply_markup=main_keyboard
    )


@dp.message(F.text == "📅 На сегодня")
async def get_today_schedule(message: types.Message):
    user = message.from_user
    logging.info(f"📅 Пользователь {user.full_name} (@{user.username}) нажал 'На сегодня'")

    await message.answer("🔄 Загружаю расписание на сегодня...")
    try:
        data = await parser.parse_schedule()
        response = format_schedule_response(data, today_only=True)
        await message.answer(response, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Ошибка при получении расписания: {e}")
        await message.answer("⚠️ Ошибка при получении данных с сайта.")


@dp.message(F.text == "🗓 На неделю")
async def get_week_schedule(message: types.Message):
    user = message.from_user
    logging.info(f"🗓 Пользователь {user.full_name} (@{user.username}) нажал 'На неделю'")

    await message.answer("🔄 Загружаю расписание на неделю...")
    try:
        data = await parser.parse_schedule()
        response = format_schedule_response(data, today_only=False)

        if len(response) > 4000:
            for i in range(0, len(response), 4000):
                await message.answer(response[i:i + 4000], parse_mode=ParseMode.HTML)
        else:
            await message.answer(response, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"Ошибка при получении расписания: {e}")
        await message.answer("⚠️ Ошибка при получении данных с сайта.")


@dp.message(F.text == "👨🏻‍💻 Разработчик")
async def show_developer_info(message: types.Message):
    user = message.from_user
    logging.info(f"👨🏻‍💻 Пользователь {user.full_name} (@{user.username}) запросил контакты разработчика")

    text = (
        "<b>👨🏻‍💻 Разработчик бота</b>\n\n"
        "По вопросам работы бота, багам и предложениям пиши напрямую:\n"
        "• Telegram: @freakbanned\n"
        "• ID: <code>1652458355</code>"
    )

    await message.answer(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=dev_inline_keyboard
    )


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())