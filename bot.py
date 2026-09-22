import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message


TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🦖 ЦЕНОЕД на связи!\n\n"
        "Я буду искать товары, сравнивать цены "
        "и помогать находить реальные скидки.\n\n"
        "🔎 Скоро отправишь мне товар — и я отправлю Ценоеда на охоту!"
    )


@dp.message()
async def message_handler(message: Message):
    await message.answer(
        "🦖 Я получил твой запрос!\n\n"
        "Сейчас ЦЕНОЕД ещё собирает свои магазины и источники цен. "
        "Скоро здесь появится настоящий поиск."
    )


async def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(token=TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
