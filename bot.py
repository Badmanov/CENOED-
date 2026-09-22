import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from fastapi import FastAPI
import uvicorn


TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()
app = FastAPI()


@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "bot": "ЦЕНОЕД"
    }


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🦖 ЦЕНОЕД на связи!\n\n"
        "Я буду искать товары, сравнивать цены "
        "и помогать находить реальные скидки.\n\n"
        "🔎 Отправь мне название товара — "
        "и я отправлю Ценоеда на охоту!"
    )


@dp.message()
async def message_handler(message: Message):
    await message.answer(
        "🦖 Я получил твой запрос!\n\n"
        "ЦЕНОЕД уже готовится к охоте за низкими ценами."
    )


async def run_bot():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(token=TOKEN)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


async def run_web():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "10000"))
    )

    server = uvicorn.Server(config)
    await server.serve()


async def main():
    await asyncio.gather(
        run_bot(),
        run_web()
    )


if __name__ == "__main__":
    asyncio.run(main())
