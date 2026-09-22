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
        "version": "0.6"
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


def extract_pampers_size(text: str):
    """
    Пытается определить размер Pampers из текста.
    Например:
    Pampers Premium Care 5 -> 5
    Premium Care 1 -> 1
    1 размер -> 1
    size 5 -> 5
    """
    text = text.lower()

    patterns = [
        r"\bpampers\s+premium\s+care\s+(\d+)\b",
        r"\bpremium\s+care\s+(\d+)\b",
        r"\bпремиум\s*(?:кэр|care)\s*(\d+)\b",
        r"\bразмер\s*(\d+)\b",
        r"\b(\d+)\s*размер\b",
        r"\bsize\s*(\d+)\b",
        r"\b(\d+)\s*size\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return int(match.group(1))

    return None


def is_pampers_query(query: str) -> bool:
    """Определяет, является ли запрос поиском Pampers."""
    text = query.lower()

    return (
        "pampers" in text
        or "памперс" in text
        or "подгузник" in text
    )


def is_relevant_result(query: str, item: dict) -> bool:
    """
    Проверяет, соответствует ли найденный товар запросу.
    Для Pampers Premium Care с указанным размером
    применяем строгую проверку размера.
    """

    if not is_pampers_query(query):
        return True

    query_size = extract_pampers_size(query)

    if query_size is None:
        return True

    title = item.get("title") or ""
    result_size = extract_pampers_size(title)

    # Если пользователь указал конкретный размер,
    # результат должен иметь тот же явно определённый размер.
    if result_size != query_size:
        return False

    return True


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

    # Оставляем только результаты с ценой.
    results_with_price = [
        item
        for item in results
        if item.get("price") is not None
        or item.get("price_text")
    ]

    # Проверяем соответствие товара запросу.
    filtered_results = [
        item
        for item in results_with_price
        if is_relevant_result(query, item)
    ]

    # Если строгий фильтр ничего не оставил,
    # показываем понятное сообщение вместо неправильных товаров.
    if not filtered_results:
        await status_message.edit_text(
            "🦖 <b>Точных совпадений не нашёл.</b>\n\n"
            f"🔎 Искал:\n«{html.escape(query)}»\n\n"
            "Попробуй добавить бренд, модель, размер "
            "или объём товара."
        )
        return

    # Сортируем от самой низкой цены.
    filtered_results.sort(
        key=lambda item: (
            item.get("price")
            if isinstance(item.get("price"), (int, float))
            else float("inf")
        )
    )

    # Показываем максимум 10 результатов.
    filtered_results = filtered_results[:10]

    lines = [
        "🦖 <b>ЦЕНОЕД НАШЁЛ!</b>",
        "",
        f"🔎 <b>{html.escape(query)}</b>",
        ""
    ]

    for index, item in enumerate(filtered_results, start=1):
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

    lowest_price = filtered_results[0].get("price")

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
