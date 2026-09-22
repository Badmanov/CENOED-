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
# HEALTH
# ============================================================

@app.get("/")
async def health_check():

    return {
        "status": "ok",
        "bot": "ЦЕНОЕД",
        "version": "1.2",
    }


# ============================================================
# HELPERS
# ============================================================

def clean_query(text: str) -> str:

    return re.sub(
        r"\s+",
        " ",
        text.strip(),
    )


# ============================================================
# PRICE
# ============================================================

def parse_price(value: Any):

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

    text = text.replace(
        "\xa0",
        " ",
    )

    text = re.sub(
        r"[^\d,.\s]",
        "",
        text,
    )

    text = text.replace(
        " ",
        "",
    )

    if not text:
        return None

    if "," in text and "." in text:

        if text.rfind(",") > text.rfind("."):

            text = text.replace(
                ".",
                "",
            )

            text = text.replace(
                ",",
                ".",
            )

        else:

            text = text.replace(
                ",",
                "",
            )

    elif "," in text:

        parts = text.split(",")

        if (
            len(parts) == 2
            and len(parts[1]) <= 2
        ):

            text = text.replace(
                ",",
                ".",
            )

        else:

            text = text.replace(
                ",",
                "",
            )

    elif "." in text:

        parts = text.split(".")

        if len(parts) > 2:

            text = text.replace(
                ".",
                "",
            )

        elif (
            len(parts) == 2
            and len(parts[1]) == 3
        ):

            text = text.replace(
                ".",
                "",
            )

    try:

        result = float(text)

        if result <= 0:
            return None

        return result

    except ValueError:

        return None


def format_price(price):

    numeric = parse_price(
        price
    )

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
# START
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

    if not message.text:

        await message.answer(
            "🦖 Отправь мне название товара текстом."
        )

        return


    # --------------------------------------------------------
    # USER QUERY
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
    # SEARCH QUERY
    # --------------------------------------------------------

    search_query = build_search_query(
        user_query
    )


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

            "🦖 Не удалось понять запрос."

        )

        return


    # --------------------------------------------------------
    # STATUS
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

            "Попробуй повторить запрос позже."

        )

        return


    # ========================================================
    # RAW RESULTS DEBUG
    # ========================================================

    print(
        f"RAW RESULTS: {len(results)}",
        flush=True,
    )


    for index, item in enumerate(
        results[:15],
        start=1,
    ):

        print(
            f"RESULT {index}: "
            f"{item.get('title')}",
            flush=True,
        )

        print(
            f"RESULT {index} STORE: "
            f"{item.get('store')}",
            flush=True,
        )

        print(
            f"RESULT {index} PRICE: "
            f"{item.get('price')}",
            flush=True,
        )


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


    print(
        f"RESULTS WITH PRICE: "
        f"{len(results_with_price)}",
        flush=True,
    )


    # ========================================================
    # PRODUCT MATCHING DEBUG
    # ========================================================

    filtered_results = []


    for index, item in enumerate(
        results_with_price,
        start=1,
    ):

        title = (
            item.get("title")
            or ""
        )


        try:

            relevant = is_relevant_result(

                user_query,

                item,

            )

        except Exception as e:

            print(

                f"MATCH ERROR {index}: "
                f"{type(e).__name__}: {e}",

                flush=True,

            )

            relevant = False


        print(

            f"MATCH {index}: "
            f"{relevant} | "
            f"{title}",

            flush=True,

        )


        if relevant:

            filtered_results.append(
                item
            )


    print(
        f"FILTERED RESULTS: "
        f"{len(filtered_results)}",
        flush=True,
    )


    # ========================================================
    # NO EXACT MATCH
    # ========================================================

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
    # SORT
    # ========================================================

    filtered_results.sort(

        key=lambda item:
        item["numeric_price"]

    )


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


        if index == 1:

            prefix = "🥇"

        elif index == 2:

            prefix = "🥈"

        elif index == 3:

            prefix = "🥉"

        else:

            prefix = f"{index}."


        lines.append(

            f"{prefix} 🛒 "

            f"{store_line} — "

            f"💰 <b>{html.escape(price)}</b>\n"

            f"   {title}"

        )


        lines.append("")


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


    await status_message.edit_text(

        "\n".join(lines),

        disable_web_page_preview=True,

    )


# ============================================================
# WEBHOOK
# ============================================================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(

    request: Request,

    x_telegram_bot_api_secret_token:
        str | None = Header(
            default=None
        ),

):

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


    data = await request.json()


    update = Update.model_validate(

        data,

        context={
            "bot": bot
        },

    )


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
# SERVER
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
