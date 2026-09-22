import asyncio
import os
import re

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
        "bot": "ЦЕНОЕД",
        "version": "0.2"
    }


def clean_query(text: str) -> str:
    """Очищаем запрос пользователя."""
    return re.sub(r"\s+", " ", text.strip())


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🦖 ЦЕНОЕД на связи!\n\n"
        "Я ищу товары, сравниваю цены и помогаю находить "
        "реальные скидки.\n\n"
        "🔎 Просто отправь название товара.\n\n"
        "Например:\n"
        "• Pampers Premium Care 5\n"
        "• iPhone 17 Pro 256 GB\n"
        "• Coca-Cola 1.5 л\n"
        "• Lavazza 1 кг\n\n"
        "🦖 Отправляй товар — отправлю Ценоеда на охоту!"
    )


@dp.message()
async def message_handler(message: Message):
    if not message.text:
        await message.answer(
            "🦖 Отправь мне название товара текстом."
        )
        return

    query = clean_query(message.text)

    if len(query) < 2:
        await message.answer(
            "🦖 Напиши название товара подробнее."
        )
        return

    await message.answer(
        "🦖 ЦЕНОЕД ПРИНЯЛ ЗАПРОС!\n\n"
        f"🔎 Товар:\n«{query}»\n\n"
        "⏳ Подготавливаю поиск цен...\n\n"
        "💰 Следующий этап — подключение реальных "
        "источников цен."
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
