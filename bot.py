import asyncio
import html
import os
import re
from typing import Any
from zoneinfo import ZoneInfo

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
from price_history import (
    init_database,
    save_price_and_get_history,
    calculate_price_change,
    calculate_market_difference,
)


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
        "version": "1.4",
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


def format_history_datetime(
    value: Any,
) -> str | None:

    if value is None:
        return None

    try:

        localized = value.astimezone(
            ZoneInfo("Europe/Moscow")
        )

    except (
        AttributeError,
        TypeError,
        ValueError,
    ):

        return None

    return localized.strftime(
        "%d.%m.%Y %H:%M"
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
# DISCOUNT
# ============================================================

def calculate_discount(
    current_price: float,
    old_price: float | None,
) -> float | None:

    if old_price is None:
        return None

    if old_price <= 0:
        return None

    if current_price >= old_price:
        return None

    discount = (
        (old_price - current_price)
        / old_price
        * 100
    )

    if discount <= 0:
        return None

    return discount


def format_discount(
    discount: float | None,
) -> str | None:

    if discount is None:
        return None

    return f"−{discount:.0f}%"


# ============================================================
# PRICE HISTORY DISPLAY
# ============================================================

def format_price_change(
    current_price: float,
    previous_price: float | None,
) -> str | None:

    change = calculate_price_change(
        current_price,
        previous_price,
    )

    if change is None:
        return None

    if abs(change) < 0.05:
        return None

    if change < 0:

        return (
            f"📉 Цена снизилась на "
            f"<b>{abs(change):.1f}%</b>\n"
            f"   Было: "
            f"{format_price(previous_price)}"
        )

    return (
        f"📈 Цена выросла на "
        f"<b>{change:.1f}%</b>\n"
        f"   Было: "
        f"{format_price(previous_price)}"
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


    if not results_with_price:

        await status_message.edit_text(

            "🦖 Не нашёл товаров "
            "с указанной ценой.\n\n"

            f"🔎 Искал:\n"
            f"«{html.escape(user_query)}»"

        )

        return


    # ========================================================
    # PRODUCT MATCHING
    # ========================================================

    filtered_results = []


    for item in results_with_price:

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
                f"MATCH ERROR: "
                f"{type(e).__name__}: {e}",
                flush=True,
            )

            relevant = False


        if relevant:

            filtered_results.append(
                item
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
    # SAVE PRICE HISTORY
    # ========================================================

    history_available = True
    market_history = None

    for item in filtered_results:

        title = (
            item.get("title")
            or "Товар"
        )

        store = (
            item.get("store")
            or "Магазин"
        )

        link = item.get("link")

        current_price = (
            item["numeric_price"]
        )


        try:

            history = (
                await asyncio.to_thread(

                    save_price_and_get_history,

                    user_query,

                    title,

                    store,

                    link,

                    current_price,

                )
            )

            previous_price = (
                history.get(
                    "store_previous_price"
                )
            )

            item["previous_price"] = (
                previous_price
            )

            item["price_change"] = (
                calculate_price_change(
                    current_price,
                    previous_price,
                )
            )

            # Первый успешный результат содержит статистику рынка,
            # рассчитанную до сохранения текущей выдачи.
            if market_history is None:

                market_history = {
                    "min_price": history.get(
                        "market_min_price"
                    ),
                    "max_price": history.get(
                        "market_max_price"
                    ),
                    "min_price_7d": history.get(
                        "market_min_price_7d"
                    ),
                    "min_price_30d": history.get(
                        "market_min_price_30d"
                    ),
                    "min_observed_at": history.get(
                        "market_min_observed_at"
                    ),
                    "last_observed_at": history.get(
                        "market_last_observed_at"
                    ),
                    "observations": history.get(
                        "market_observations",
                        0,
                    ),
                }


        except Exception as e:

            history_available = False

            item["previous_price"] = None
            item["price_change"] = None

            print(
                f"HISTORY SAVE ERROR: "
                f"{type(e).__name__}: {e}",
                flush=True,
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


    max_discount = None


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


        current_price = (
            item["numeric_price"]
        )


        price = format_price(
            current_price
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


        # ----------------------------------------------------
        # RANK
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
        # STORE OLD PRICE DISCOUNT
        # ----------------------------------------------------

        raw_old_price = (

            item.get("old_price")

            if item.get("old_price") is not None

            else item.get("old_price_text")

        )


        old_price = parse_price(
            raw_old_price
        )


        discount = calculate_discount(

            current_price,

            old_price,

        )


        if discount is not None:

            if (
                max_discount is None
                or discount > max_discount
            ):

                max_discount = discount


            discount_text = (
                format_discount(
                    discount
                )
            )


            price_line = (

                f"💰 <b>{html.escape(price)}</b> "
                f"🔥 <b>{discount_text}</b>\n"

                f"   <s>"
                f"{html.escape(format_price(old_price))}"
                f"</s>"

            )

        else:

            price_line = (
                f"💰 <b>{html.escape(price)}</b>"
            )


        # ----------------------------------------------------
        # PRICE HISTORY
        # ----------------------------------------------------

        previous_price = (
            item.get("previous_price")
        )


        history_text = format_price_change(

            current_price,

            previous_price,

        )


        if history_text:

            history_block = (
                f"\n{history_text}"
            )

        else:

            history_block = ""


        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        lines.append(

            f"{prefix} 🛒 "
            f"{store_line} — "
            f"{price_line}\n"

            f"   {title}"

            f"{history_block}"

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


    # ========================================================
    # MARKET HISTORY
    # ========================================================

    if (
        market_history
        and market_history.get(
            "observations",
            0,
        ) > 0
        and market_history.get(
            "min_price"
        ) is not None
    ):

        market_min = (
            market_history["min_price"]
        )

        market_max = (
            market_history["max_price"]
        )

        market_difference = (
            calculate_market_difference(
                lowest_price,
                market_min,
            )
        )

        min_price_7d = (
            market_history.get(
                "min_price_7d"
            )
        )

        min_price_30d = (
            market_history.get(
                "min_price_30d"
            )
        )

        min_observed_at = (
            format_history_datetime(
                market_history.get(
                    "min_observed_at"
                )
            )
        )

        last_observed_at = (
            format_history_datetime(
                market_history.get(
                    "last_observed_at"
                )
            )
        )

        lines.extend([
            "",
            "📊 <b>Сохранённые наблюдения рынка</b>",
        ])

        if min_price_7d is not None:

            lines.append(
                "Минимум за 7 дней: "
                f"{format_price(min_price_7d)}"
            )

        if min_price_30d is not None:

            lines.append(
                "Минимум за 30 дней: "
                f"{format_price(min_price_30d)}"
            )

        market_min_line = (
            "Минимум среди всех наблюдений: "
            f"{format_price(market_min)}"
        )

        if min_observed_at:

            market_min_line += (
                f" — {min_observed_at}"
            )

        lines.extend([
            market_min_line,
            (
                "Максимум среди наблюдений: "
                f"{format_price(market_max)}"
            ),
            (
                "Точек истории: "
                f"{market_history['observations']}"
            ),
        ])

        if last_observed_at:

            lines.append(
                "Последнее изменение/новое предложение: "
                f"{last_observed_at}"
            )

        if market_difference is not None:

            if abs(market_difference) < 0.05:

                lines.append(
                    "✅ Сейчас цена совпадает с минимумом "
                    "среди сохранённых наблюдений."
                )

            elif market_difference > 0:

                lines.append(
                    "📈 Сейчас на "
                    f"<b>{market_difference:.1f}%</b> "
                    "выше минимума среди "
                    "сохранённых наблюдений."
                )

            else:

                lines.append(
                    "📉 Текущая цена на "
                    f"<b>{abs(market_difference):.1f}%</b> "
                    "ниже прежнего минимума среди "
                    "сохранённых наблюдений."
                )


    # ========================================================
    # MAX STORE DISCOUNT
    # ========================================================

    if max_discount is not None:

        lines.append("")

        lines.append(

            "🏷 <b>Максимальная скидка "
            "по данным магазина: "
            f"−{max_discount:.0f}%</b>"

        )


    # ========================================================
    # HISTORY INFO
    # ========================================================

    lines.append("")


    if history_available:

        lines.append(

            "📊 <b>История цен сохраняется.</b>\n"

            "Сравниваю текущие предложения "
            "с сохранёнными наблюдениями."

        )

    else:

        lines.append(

            "📊 История цен временно "
            "недоступна, но поиск работает."

        )


    # ========================================================
    # DISCOUNT DISCLAIMER
    # ========================================================

    if max_discount is not None:

        lines.append("")

        lines.append(

            "ℹ️ Скидка рассчитана "
            "по указанной старой цене магазина. "
            "Историческое сравнение цены "
            "показывается отдельно."

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

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:

        await asyncio.to_thread(
            init_database
        )

        print(
            "DATABASE: ready",
            flush=True,
        )

    except Exception as e:

        print(

            f"DATABASE INIT ERROR: "
            f"{type(e).__name__}: {e}",

            flush=True,

        )


    # --------------------------------------------------------
    # TELEGRAM
    # --------------------------------------------------------

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
