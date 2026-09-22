import asyncio
import html
import os
import re

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from fastapi import FastAPI
import uvicorn

from connectors.google_shopping import search_google_shopping


TOKEN = os.getenv("BOT_TOKEN")

dp = Dispatcher()
app = FastAPI()


@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "bot": "ЦЕНОЕД",
        "version": "0.5"
    }


def clean_query(text: str) -> str:
    """Очищает поисковый запрос."""
    return re.sub(r"\s+", " ", text.strip())


def format_price(price):
    """Красиво форматирует цену."""
    if price is None:
        return "Цена не указана"

    try:
        value = float(price)

        if value.is_integer():
            return f"{int(value):,} ₽".replace(",", " ")

        return f"{value:,.2f} ₽".replace(",", " ").replace(".", ",")
    except (TypeError, ValueError):
        return str(price)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "🦖 <b>ЦЕНОЕД</b> на связи!\n\n"
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

    status_message = await message.answer(
        "🦖 <b>ЦЕНОЕД ПРИНЯЛ ЗАПРОС!</b>\n\n"
        f"🔎 Ищу:\n«{html.escape(query)}»\n\n"
        "⏳ Проверяю доступные магазины..."
    )

    try:
        results = await asyncio.to_thread(
            search_google_shopping,
            query
        )

    except Exception as e:
        print(
            f"SEARCH ERROR: {type(e).__name__}: {e}",
            flush=True
        )

        await status_message.edit_text(
            "🦖 Не удалось получить результаты поиска.\n\n"
            "Попробуй повторить запрос немного позже."
        )
        return

    if not results:
        await status_message.edit_text(
            "🦖 Пока ничего не нашёл.\n\n"
            f"Попробуй изменить запрос:\n"
            f"«{html.escape(query)}»"
        )
        return

    results_with_price = [
        item
        for item in results
        if item.get("price") is not None
        or item.get("price_text")
    ]

    results_with_price.sort(
        key=lambda item: (
            item.get("price")
            if isinstance(item.get("price"), (int, float))
            else float("inf")
        )
    )

    results_with_price = results_with_price[:10]

    lines = [
        "🦖 <b>ЦЕНОЕД НАШЁЛ!</b>",
        "",
        f"🔎 <b>{html.escape(query)}</b>",
        ""
    ]

    for index, item in enumerate(results_with_price, start=1):
        title = html.escape(
            item.get("title") or "Товар"
        )

        store = html.escape(
            item.get("store") or "Магазин",
            quote=True
        )

        raw_link = item.get("link")

        price = format_price(
            item.get("price")
            if item.get("price") is not None
            else item.get("price_text")
        )

        safe_price = html.escape(price)

        if raw_link:
            safe_link = html.escape(
                str(raw_link),
                quote=True
            )

            store_line = (
                f'<a href="{safe_link}">'
                f"<b>{store}</b>"
                f"</a>"
            )
        else:
            store_line = f"<b>{store}</b>"

        if index == 1:
            prefix = "🥇"
        elif index == 2:
            prefix = "🥈"
        elif index == 3:
            prefix = "🥉"
        else:
            prefix = f"{index}."

        lines.append(
            f"{prefix} 🛒 {store_line} — "
            f"💰 <b>{safe_price}</b>\n"
            f"   {title}"
        )

        lines.append("")

    lowest_price = results_with_price[0].get("price")

    if isinstance(lowest_price, (int, float)):
        lines.append(
            f"🔥 <b>Самая низкая найденная цена: "
            f"{format_price(lowest_price)}</b>"
        )

    lines.append("")
    lines.append("🔔 Скоро добавим отслеживание цены.")

    await status_message.edit_text(
        "\n".join(lines),
        disable_web_page_preview=True
    )


async def run_bot():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

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
