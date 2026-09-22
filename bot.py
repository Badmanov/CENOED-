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
        "version": "1.3",
    }


# ============================================================
# BASIC HELPERS
# ============================================================

def clean_query(
    text: str,
) -> str:

    return re.sub(
        r"\s+",
        " ",
        text.strip(),
    )


# ============================================================
# PRICE PARSING
# ============================================================

def parse_price(
    value: Any,
):

    if value is None:

        return None


    if isinstance(
        value,
        bool,
    ):

        return None


    if isinstance(
        value,
        (int, float),
    ):

        if value <= 0:

            return None

        return float(value)


    text = str(
        value
    ).strip()


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


    # --------------------------------------------------------
    # 12.990,50
    # --------------------------------------------------------

    if (
        "," in text
        and "." in text
    ):

        if (
            text.rfind(",")
            >
            text.rfind(".")
        ):

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


    # --------------------------------------------------------
    # 12,990
    # 12,99
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # 12.990
    # 12.990,50
    # --------------------------------------------------------

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

        result = float(
            text
        )


        if result <= 0:

            return None


        return result


    except ValueError:

        return None


# ============================================================
# PRICE FORMAT
# ============================================================

def format_price(
    price,
):

    numeric = parse_price(
        price
    )


    if numeric is None:

        return "Цена не указана"


    if numeric.is_integer():

        return (
            f"{int(numeric):,} ₽"
            .replace(
                ",",
                " ",
            )
        )


    return (
        f"{numeric:,.2f} ₽"
        .replace(
            ",",
            " ",
        )
        .replace(
            ".",
            ",",
        )
    )


# ============================================================
# DISCOUNT
# ============================================================

def calculate_discount(
    current_price,
    old_price,
):
    """
    Рассчитывает скидку относительно
    переданной старой цены.

    Важно:

    Это НЕ доказательство реальной скидки.
    Это скидка по старой цене,
    которую передал источник.
    """

    current = parse_price(
        current_price
    )

    old = parse_price(
        old_price
    )


    if current is None:

        return None


    if old is None:

        return None


    if old <= current:

        return None


    discount = (
        (old - current)
        / old
        * 100
    )


    if discount <= 0:

        return None


    if discount >= 100:

        return None


    return discount


def format_discount(
    discount,
):

    if discount is None:

        return None


    if discount >= 10:

        return (
            f"−{discount:.0f}%"
        )


    return (
        f"−{discount:.1f}%"
    ).replace(
        ".",
        ",",
    )


# ============================================================
# /START
# ============================================================

@dp.message(
    CommandStart()
)
async def start_handler(
    message: Message,
):

    await message.answer(

        "🦖 <b>ЦЕНОЕД</b> на связи!\n\n"

        "Я ищу товары, сравниваю цены "
        "и помогаю находить выгодные предложения.\n\n"

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
    # Запрос пользователя
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
    # Строим поисковый запрос
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

            item.get(
                "price"
            )

            if item.get(
                "price"
            ) is not None

            else item.get(
                "price_text"
            )

        )


        numeric_price = parse_price(
            raw_price
        )


        if numeric_price is None:

            continue


        item[
            "numeric_price"
        ] = numeric_price


        # ----------------------------------------------------
        # Старая цена
        # ----------------------------------------------------

        raw_old_price = (

            item.get(
                "old_price"
            )

            if item.get(
                "old_price"
            ) is not None

            else item.get(
                "old_price_text"
            )

        )


        numeric_old_price = parse_price(
            raw_old_price
        )


        item[
            "numeric_old_price"
        ] = numeric_old_price


        # ----------------------------------------------------
        # Скидка
        # ----------------------------------------------------

        discount = calculate_discount(

            numeric_price,

            numeric_old_price,

        )


        item[
            "discount_percent"
        ] = discount


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
    # SORT
    # ========================================================

    filtered_results.sort(

        key=lambda item:
        item[
            "numeric_price"
        ]

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


    # ========================================================
    # RESULTS
    # ========================================================

    for index, item in enumerate(

        filtered_results,

        start=1,

    ):

        title = html.escape(

            item.get(
                "title"
            )
            or "Товар"

        )


        store = html.escape(

            item.get(
                "store"
            )
            or "Магазин",

            quote=True,

        )


        raw_link = item.get(
            "link"
        )


        current_price = item[
            "numeric_price"
        ]


        current_price_text = (
            format_price(
                current_price
            )
        )


        old_price = item.get(
            "numeric_old_price"
        )


        discount = item.get(
            "discount_percent"
        )


        discount_text = (
            format_discount(
                discount
            )
        )


        # ----------------------------------------------------
        # Цена
        # ----------------------------------------------------

        if (
            old_price is not None
            and discount_text
        ):

            price_line = (

                f"💰 <b>"
                f"{html.escape(current_price_text)}"
                f"</b> "

                f"🔥 <b>"
                f"{html.escape(discount_text)}"
                f"</b>\n"

                f"   <s>"
                f"{html.escape(format_price(old_price))}"
                f"</s>"

            )

        else:

            price_line = (

                f"💰 <b>"
                f"{html.escape(current_price_text)}"
                f"</b>"

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
        # Результат
        # ----------------------------------------------------

        lines.append(

            f"{prefix} 🛒 "
            f"{store_line} — "
            f"{price_line}\n"
            f"   {title}"

        )


        lines.append("")


    # ========================================================
    # LOWEST PRICE
    # ========================================================

    lowest_item = (
        filtered_results[0]
    )


    lowest_price = (
        lowest_item[
            "numeric_price"
        ]
    )


    lines.append(

        "🔥 <b>Самая низкая "
        "найденная цена: "

        f"{format_price(lowest_price)}"

        "</b>"

    )


    # ========================================================
    # DISCOUNT SUMMARY
    # ========================================================

    discounted_items = [

        item

        for item in filtered_results

        if item.get(
            "discount_percent"
        ) is not None

    ]


    if discounted_items:

        best_discount_item = max(

            discounted_items,

            key=lambda item:
            item[
                "discount_percent"
            ],

        )


        best_discount = (
            best_discount_item[
                "discount_percent"
            ]
        )


        if best_discount is not None:

            lines.append("")


            lines.append(

                "🏷 <b>Максимальная скидка "
                "по данным магазина: "

                f"{format_discount(best_discount)}"

                "</b>"

            )


    lines.append("")


    lines.append(

        "ℹ️ Скидка рассчитана "
        "по указанной старой цене. "

        "Проверку реальной истории цены "
        "добавим следующим этапом."

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

@app.post(
    WEBHOOK_PATH
)
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

@app.on_event(
    "startup"
)
async def startup_event():

    await setup_webhook()


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event(
    "shutdown"
)
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
