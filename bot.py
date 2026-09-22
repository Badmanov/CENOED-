import asyncio
import html
import os
import re
from typing import Any

import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, Update

from fastapi import FastAPI, Header, HTTPException, Request

from connectors.google_shopping import search_google_shopping
from product_matching import is_relevant_result
from search_query import build_search_query


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

BASE_WEBHOOK_URL = "https://cenoed.onrender.com"

WEBHOOK_PATH = "/telegram/webhook"

WEBHOOK_URL = (
    f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"
)


# ============================================================
# TELEGRAM / FASTAPI
# ============================================================

dp = Dispatcher()

app = FastAPI()

bot: Bot | None = None


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "bot": "ЦЕНОЕД",
        "version": "1.1",
    }


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_query(text: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        text.strip(),
    )


# ============================================================
# PRICE PARSING
# ============================================================

def parse_price(value: Any):
    """
    Преобразует цену из разных форматов
    в число.

    Поддерживает:

    12 990 ₽
    12,990
    12990
    12 990,50 ₽
    12.990,50
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):

        if value <= 0:
            return None

        return float(value)

    text = str(value).strip()

    if not text:
        return None

    cleaned = text.replace(
        "\xa0",
        " ",
    )

    # Оставляем только цифры,
    # запятую, точку и пробел.
    cleaned = re.sub(
        r"[^\d,.\s]",
        "",
        cleaned,
    )

    cleaned = cleaned.replace(
        " ",
        "",
    )

    if not cleaned:
        return None

    # Например:
    #
    # 12.990,50
    # 12,990.50
    #
    if "," in cleaned and "." in cleaned:

        if cleaned.rfind(",") > cleaned.rfind("."):

            cleaned = cleaned.replace(
                ".",
                "",
            )

            cleaned = cleaned.replace(
                ",",
                ".",
            )

        else:

            cleaned = cleaned.replace(
                ",",
                "",
            )

    elif "," in cleaned:

        parts = cleaned.split(",")

        if (
            len(parts) == 2
            and len(parts[1]) <= 2
        ):

            cleaned = cleaned.replace(
                ",",
                ".",
            )

        else:

            cleaned = cleaned.replace(
                ",",
                "",
            )

    elif "." in cleaned:

        parts = cleaned.split(".")

        if len(parts) > 2:

            cleaned = cleaned.replace(
                ".",
                "",
            )

        elif (
            len(parts) == 2
            and len(parts[1]) == 3
        ):

            cleaned = cleaned.replace(
                ".",
                "",
            )

    try:

        result = float(cleaned)

        if result <= 0:
            return None

        return result

    except ValueError:

        return None


def format_price(price):
    numeric = parse_price(price)

    if numeric is None:
        return "Цена не указана"

    if numeric.is_integer():

        return (
            f"{int(numeric):,} ₽"
            .replace(",", " ")
        )

    return (
        f"{numeric:,.2f} ₽"
        .replace(",", " ")
        .replace(".", ",")
    )


# ============================================================
# /START
# ============================================================

@dp.message(CommandStart())
async def start_handler(
    message: Message,
):

    await message.answer(

        "🦖 <b>ЦЕНОЕД</b> на связи!\n\n"

        "Я ищу товары, сравниваю цены "
        "и помогаю находить реальные скидки.\n\n"

        "🔎 Просто отправь название товара.\n\n"

        "Например:\n"
        "• Pampers Premium Care 5\n"
        "• iPhone 17 Pro 256 GB\n"
        "• Coca-Cola 1.5 л\n"
        "• Lavazza 1 кг\n"
        "• Чехол iPhone 17 Pro\n\n"

        "🦖 Отправляй товар — "
        "отправлю Ценоеда на охоту!"

    )


# ============================================================
# SEARCH
# ============================================================

@dp.message()
async def message_handler(
    message: Message,
):

    # --------------------------------------------------------
    # Проверяем текст
    # --------------------------------------------------------

    if not message.text:

        await message.answer(
            "🦖 Отправь мне название товара текстом."
        )

        return


    # --------------------------------------------------------
    # Оригинальный запрос пользователя
    # --------------------------------------------------------

    user_query = clean_query(
        message.text
    )


    if len(user_query) < 2:

        await message.answer(
            "🦖 Напиши название товара подробнее."
        )

        return


    # --------------------------------------------------------
    # Строим оптимизированный поисковый запрос
    # --------------------------------------------------------

    search_query = build_search_query(
        user_query
    )


    # --------------------------------------------------------
    # ДИАГНОСТИКА
    #
    # Эти строки будут видны в Render Logs.
    # --------------------------------------------------------

    print(
        f"USER QUERY: {user_query}",
        flush=True,
    )

    print(
        f"SEARCH QUERY: {search_query}",
        flush=True,
    )


    if not search_query:

        await message.answer(

            "🦖 Не удалось понять запрос.\n\n"

            "Попробуй написать название "
            "товара подробнее."

        )

        return


    # --------------------------------------------------------
    # Сообщение о поиске
    # --------------------------------------------------------

    status_message = await message.answer(

        "🦖 <b>ЦЕНОЕД ПРИНЯЛ ЗАПРОС!</b>\n\n"

        f"🔎 Ищу:\n"
        f"«{html.escape(user_query)}»\n\n"

        "⏳ Проверяю доступные магазины..."

    )


    # ========================================================
    # GOOGLE SHOPPING
    # ========================================================

    try:

        results = await asyncio.to_thread(

            search_google_shopping,

            search_query,

        )

    except Exception as e:

        print(
            f"SEARCH ERROR: "
            f"{type(e).__name__}: {e}",
            flush=True,
        )

        await status_message.edit_text(

            "🦖 Не удалось получить "
            "результаты поиска.\n\n"

            "Попробуй повторить запрос "
            "немного позже."

        )

        return


    # --------------------------------------------------------
    # Нет результатов
    # --------------------------------------------------------

    if not results:

        await status_message.edit_text(

            "🦖 Пока ничего не нашёл.\n\n"

            f"🔎 Искал:\n"
            f"«{html.escape(user_query)}»"

        )

        return


    # ========================================================
    # PRICE FILTER
    # ========================================================

    results_with_price = []


    for item in results:

        raw_price = (

            item.get("price")

            if item.get("price") is not None

            else item.get("price_text")

        )


        numeric_price = parse_price(
            raw_price
        )


        if numeric_price is None:
            continue


        item["numeric_price"] = (
            numeric_price
        )


        results_with_price.append(
            item
        )


    # ========================================================
    # PRODUCT MATCHING
    # ========================================================

    filtered_results = []


    for item in results_with_price:

        try:

            relevant = is_relevant_result(

                user_query,

                item,

            )

        except Exception as e:

            print(

                "MATCHING ERROR: "

                f"{type(e).__name__}: {e}",

                flush=True,

            )

            relevant = False


        if relevant:

            filtered_results.append(
                item
            )


    # --------------------------------------------------------
    # Нет точных совпадений
    # --------------------------------------------------------

    if not filtered_results:

        await status_message.edit_text(

            "🦖 <b>Точных совпадений не нашёл.</b>\n\n"

            f"🔎 Искал:\n"
            f"«{html.escape(user_query)}»\n\n"

            "Попробуй добавить бренд, "
            "модель, размер, объём "
            "или другую характеристику товара."

        )

        return


    # ========================================================
    # SORT BY PRICE
    # ========================================================

    filtered_results.sort(

        key=lambda item:
        item["numeric_price"]

    )


    # Максимум 10 результатов.

    filtered_results = (
        filtered_results[:10]
    )


    # ========================================================
    # RESPONSE
    # ========================================================

    lines = [

        "🦖 <b>ЦЕНОЕД НАШЁЛ!</b>",

        "",

        f"🔎 <b>"
        f"{html.escape(user_query)}"
        f"</b>",

        "",

    ]


    for index, item in enumerate(

        filtered_results,

        start=1,

    ):

        title = html.escape(

            item.get("title")

            or "Товар"

        )


        store = html.escape(

            item.get("store")

            or "Магазин",

            quote=True,

        )


        raw_link = item.get(
            "link"
        )


        price = format_price(

            item[
                "numeric_price"
            ]

        )


        safe_price = html.escape(
            price
        )


        # ----------------------------------------------------
        # Магазин
        # ----------------------------------------------------

        if raw_link:

            safe_link = html.escape(

                str(raw_link),

                quote=True,

            )


            store_line = (

                f'<a href="{safe_link}">'

                f"<b>{store}</b>"

                f"</a>"

            )

        else:

            store_line = (

                f"<b>{store}</b>"

            )


        # ----------------------------------------------------
        # Номер
        # ----------------------------------------------------

        if index == 1:

            prefix = "🥇"

        elif index == 2:

            prefix = "🥈"

        elif index == 3:

            prefix = "🥉"

        else:

            prefix = f"{index}."


        # ----------------------------------------------------
        # Товар
        # ----------------------------------------------------

        lines.append(

            f"{prefix} 🛒 "

            f"{store_line} — "

            f"💰 <b>{safe_price}</b>\n"

            f"   {title}"

        )


        lines.append("")


    # ========================================================
    # LOWEST PRICE
    # ========================================================

    lowest_price = (

        filtered_results[0]

        ["numeric_price"]

    )


    lines.append(

        "🔥 <b>Самая низкая "
        "найденная цена: "

        f"{format_price(lowest_price)}"

        "</b>"

    )


    lines.append("")


    lines.append(

        "🔔 Скоро добавим "
        "отслеживание цены."

    )


    # ========================================================
    # SEND RESULT
    # ========================================================

    await status_message.edit_text(

        "\n".join(lines),

        disable_web_page_preview=True,

    )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(

    request: Request,

    x_telegram_bot_api_secret_token:
        str | None = Header(
            default=None
        ),

):

    # --------------------------------------------------------
    # Проверяем секрет
    # --------------------------------------------------------

    if not WEBHOOK_SECRET:

        raise HTTPException(

            status_code=500,

            detail=(
                "WEBHOOK_SECRET "
                "is not configured"
            ),

        )


    if (
        x_telegram_bot_api_secret_token
        != WEBHOOK_SECRET
    ):

        raise HTTPException(

            status_code=403,

            detail="Invalid webhook secret",

        )


    # --------------------------------------------------------
    # Telegram Update
    # --------------------------------------------------------

    data = await request.json()


    update = Update.model_validate(

        data,

        context={
            "bot": bot
        },

    )


    # --------------------------------------------------------
    # Передаём update в aiogram
    # --------------------------------------------------------

    await dp.feed_update(

        bot,

        update,

    )


    return {
        "ok": True
    }


# ============================================================
# WEBHOOK SETUP
# ============================================================

async def setup_webhook():

    global bot


    if not TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is not set"
        )


    if not WEBHOOK_SECRET:

        raise RuntimeError(
            "WEBHOOK_SECRET is not set"
        )


    bot = Bot(

        token=TOKEN,

        default=DefaultBotProperties(

            parse_mode=ParseMode.HTML

        ),

    )


    await bot.set_webhook(

        url=WEBHOOK_URL,

        secret_token=WEBHOOK_SECRET,

        drop_pending_updates=False,

    )


    print(

        f"WEBHOOK SET: "
        f"{WEBHOOK_URL}",

        flush=True,

    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    await setup_webhook()


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event():

    global bot


    if bot:

        await bot.session.close()

        bot = None


# ============================================================
# WEB SERVER
# ============================================================

async def run_web():

    port = int(

        os.getenv(

            "PORT",

            "10000",

        )

    )


    config = uvicorn.Config(

        app,

        host="0.0.0.0",

        port=port,

        log_level="info",

    )


    server = uvicorn.Server(
        config
    )


    await server.serve()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    asyncio.run(
        run_web()
    )
