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
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)

from fastapi import FastAPI, Header, HTTPException, Request

from connectors.google_search import search_retailer_web
from connectors.google_shopping import search_google_shopping
from product_matching import (
    extract_pack_count,
    is_relevant_result,
)
from search_query import (
    build_fallback_search_query,
    build_search_query,
)
from price_history import (
    init_database,
    save_price_and_get_history,
    calculate_price_change,
)
from subscriptions import (
    activate_subscription,
    create_watch_candidate,
    deactivate_subscription,
    init_subscriptions,
    list_subscriptions,
    get_due_subscriptions,
    get_user_city,
    is_adult_confirmed,
    confirm_adult,
    record_price_check,
    set_user_city,
    should_notify,
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


ALCOHOL_QUERY_PHRASES = {
    "corona extra",
    "винлаб",
    "красное белое",
}


ALCOHOL_QUERY_TERMS = {
    "пиво",
    "beer",
    "lager",
    "эль",
    "ale",
    "сидр",
    "cider",
    "вино",
    "wine",
    "шампанское",
    "champagne",
    "просекко",
    "prosecco",
    "водка",
    "vodka",
    "виски",
    "whiskey",
    "whisky",
    "ром",
    "rum",
    "джин",
    "gin",
    "текила",
    "tequila",
    "коньяк",
    "brandy",
    "бренди",
    "ликер",
    "ликёр",
    "liqueur",
}


def is_age_restricted_query(text: str) -> bool:
    normalized = " ".join(
        re.findall(
            r"[a-zа-яё]+",
            text.casefold(),
        )
    )
    tokens = set(normalized.split())
    return (
        bool(tokens & ALCOHOL_QUERY_TERMS)
        or any(
            phrase in normalized
            for phrase in ALCOHOL_QUERY_PHRASES
        )
    )


def format_retailer_name(
    store: Any,
    link: Any = None,
) -> str:
    original = str(
        store or "Магазин"
    ).strip()

    identity = (
        f"{original} {link or ''}"
    ).casefold()

    retailers = (
        (
            ("ozon", "ozon.ru"),
            "🟦 Ozon",
        ),
        (
            (
                "wildberries",
                "wildberries.ru",
                "wb.ru",
            ),
            "🟪 Wildberries",
        ),
        (
            (
                "яндекс маркет",
                "yandex market",
                "market.yandex",
            ),
            "🟨 Яндекс Маркет",
        ),
        (
            ("пятёрочка", "пятерочка", "5ka.ru"),
            "🟢 Пятёрочка",
        ),
        (
            ("перекрёсток", "перекресток", "perekrestok.ru"),
            "🟢 Перекрёсток",
        ),
        (
            ("дикси", "dixy.ru"),
            "🟠 Дикси",
        ),
        (
            ("магнит", "magnit.ru"),
            "🔴 Магнит",
        ),
        (
            ("вкусвилл", "vkusvill.ru"),
            "🟢 ВкусВилл",
        ),
        (
            (
                "азбука вкуса",
                "av.ru",
            ),
            "🟣 Азбука Вкуса",
        ),
        (
            ("винлаб", "winelab.ru"),
            "🔞 ВинЛаб",
        ),
        (
            (
                "красное белое",
                "красное & белое",
                "krasnoeibeloe.ru",
            ),
            "🔞 Красное & Белое",
        ),
    )

    for markers, label in retailers:
        if any(
            marker in identity
            for marker in markers
        ):
            return label

    return original


def offer_retailer_key(
    item: dict[str, Any],
) -> str:
    store = str(
        item.get("store")
        or "Магазин"
    ).strip()

    canonical = format_retailer_name(
        store,
        item.get("link"),
    )

    return re.sub(
        r"[^a-zа-яё0-9]+",
        " ",
        canonical.casefold(),
    ).strip()


def cheapest_offer_per_retailer(
    offers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unique_offers = []
    seen_retailers = set()

    for offer in offers:
        retailer_key = offer_retailer_key(
            offer
        )

        if retailer_key in seen_retailers:
            continue

        seen_retailers.add(retailer_key)
        unique_offers.append(offer)

    return unique_offers


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

        "📍 Город поиска: команда /city\n"
        "🔔 Подписки: команда /subscriptions\n\n"
        "🦖 Отправляй товар — "
        "отправлю Ценоеда на охоту!"

    )


# ============================================================
# USER CITY
# ============================================================

@dp.message(Command("city"))
async def city_handler(message: Message):
    if not message.from_user:
        return

    raw_city = ""

    if message.text:
        parts = message.text.split(
            maxsplit=1
        )
        if len(parts) > 1:
            raw_city = parts[1].strip()

    if not raw_city:
        try:
            current_city = await asyncio.to_thread(
                get_user_city,
                message.from_user.id,
            )
        except Exception:
            current_city = "Москва, Россия"

        await message.answer(
            "📍 <b>Город поиска</b>\n\n"
            f"Сейчас: {html.escape(current_city)}\n\n"
            "Чтобы изменить, отправь, например:\n"
            "<code>/city Санкт-Петербург</code>"
        )
        return

    if "," not in raw_city:
        raw_city = f"{raw_city}, Россия"

    try:
        city = await asyncio.to_thread(
            set_user_city,
            message.from_user.id,
            raw_city,
        )
    except (ValueError, TypeError):
        await message.answer(
            "📍 Не удалось сохранить город. "
            "Напиши название города после /city."
        )
        return
    except Exception as e:
        print(
            f"CITY SAVE ERROR: {type(e).__name__}: {e}",
            flush=True,
        )
        await message.answer(
            "📍 Не удалось сохранить город. Попробуй позже."
        )
        return

    await message.answer(
        "📍 <b>Город сохранён</b>\n\n"
        f"{html.escape(city)}\n"
        "Новые поиски и подписки будут учитывать этот город."
    )


# ============================================================
# SUBSCRIPTIONS
# ============================================================

@dp.message(Command("subscriptions"))
async def subscriptions_handler(message: Message):
    if not message.from_user:
        return

    try:
        items = await asyncio.to_thread(
            list_subscriptions,
            message.from_user.id,
        )
    except Exception as e:
        print(
            f"SUBSCRIPTIONS LIST ERROR: {type(e).__name__}: {e}",
            flush=True,
        )
        await message.answer(
            "🔔 Не удалось открыть подписки. Попробуй позже."
        )
        return

    if not items:
        await message.answer(
            "🔔 Активных подписок пока нет.\n\n"
            "Найди товар и нажми «Следить за снижением»."
        )
        return

    lines = ["🔔 <b>Мои подписки</b>", ""]
    buttons = []

    for item in items:
        lines.append(
            f"• {html.escape(item['product_query'])}\n"
            f"  Последняя цена: "
            f"{format_price(item['last_seen_price'])}"
        )
        buttons.append([
            InlineKeyboardButton(
                text=f"Отключить: {item['product_query'][:24]}",
                callback_data=f"unwatch:{item['id']}",
            )
        ])

    await message.answer(
        "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
    )


@dp.callback_query(
    lambda query:
    query.data == "city_help"
)
async def city_help_callback(
    callback: CallbackQuery,
):
    await callback.answer()

    if callback.message:
        await callback.message.answer(
            "📍 <b>Как изменить город</b>\n\n"
            "Отправь команду с названием города, например:\n"
            "<code>/city Санкт-Петербург</code>\n\n"
            "Текущий город можно посмотреть командой /city."
        )


@dp.callback_query(
    lambda query:
    query.data
    and query.data.startswith("watch:")
)
async def watch_callback(callback: CallbackQuery):
    if not callback.from_user or not callback.data:
        return

    token = callback.data.split(":", 1)[1]

    try:
        subscription = await asyncio.to_thread(
            activate_subscription,
            token,
            callback.from_user.id,
        )
    except Exception as e:
        print(
            f"SUBSCRIPTION ACTIVATE ERROR: "
            f"{type(e).__name__}: {e}",
            flush=True,
        )
        await callback.answer(
            "Не удалось создать подписку.",
            show_alert=True,
        )
        return

    if subscription is None:
        await callback.answer(
            "Эта кнопка устарела. Выполни поиск ещё раз.",
            show_alert=True,
        )
        return

    await callback.answer("Подписка включена")

    if callback.message:
        await callback.message.answer(
            "🔔 <b>Подписка включена</b>\n\n"
            f"{html.escape(subscription['product_query'])}\n"
            "Сообщу при любом снижении цены. "
            "Одинаковые уведомления повторять не буду.\n\n"
            "Команда /subscriptions — управление подписками."
        )


@dp.callback_query(
    lambda query:
    query.data
    and query.data.startswith("unwatch:")
)
async def unwatch_callback(callback: CallbackQuery):
    if not callback.from_user or not callback.data:
        return

    try:
        subscription_id = int(
            callback.data.split(":", 1)[1]
        )
        removed = await asyncio.to_thread(
            deactivate_subscription,
            subscription_id,
            callback.from_user.id,
        )
    except (TypeError, ValueError):
        removed = False
    except Exception as e:
        print(
            f"SUBSCRIPTION REMOVE ERROR: "
            f"{type(e).__name__}: {e}",
            flush=True,
        )
        removed = False

    await callback.answer(
        "Подписка отключена"
        if removed
        else "Подписка уже отключена",
        show_alert=not removed,
    )

    if removed and callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )


# ============================================================
# AGE CONFIRMATION
# ============================================================

@dp.callback_query(
    lambda query:
    query.data == "age18_confirm"
)
async def age18_confirm_callback(
    callback: CallbackQuery,
):
    if not callback.from_user:
        return

    try:
        await asyncio.to_thread(
            confirm_adult,
            callback.from_user.id,
        )
    except Exception as e:
        print(
            f"AGE CONFIRM ERROR: {type(e).__name__}: {e}",
            flush=True,
        )
        await callback.answer(
            "Не удалось сохранить подтверждение. Попробуй позже.",
            show_alert=True,
        )
        return

    await callback.answer("Возраст подтверждён")

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
        await callback.message.answer(
            "✅ <b>Возраст подтверждён</b>\n\n"
            "Теперь повтори запрос товара. "
            "Больше подтверждать возраст не потребуется."
        )


@dp.callback_query(
    lambda query:
    query.data == "age18_cancel"
)
async def age18_cancel_callback(
    callback: CallbackQuery,
):
    await callback.answer("Поиск отменён")

    if callback.message:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
        await callback.message.answer(
            "Поиск товара категории 18+ отменён."
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

    if message.from_user:

        try:

            user_city = await asyncio.to_thread(
                get_user_city,
                message.from_user.id,
            )

        except Exception:

            user_city = "Москва, Россия"

    else:

        user_city = "Москва, Россия"


    if len(user_query) < 2:

        await message.answer(
            "🦖 Напиши название товара подробнее."
        )

        return


    if (
        message.from_user
        and is_age_restricted_query(user_query)
    ):
        try:
            adult_confirmed = await asyncio.to_thread(
                is_adult_confirmed,
                message.from_user.id,
            )
        except Exception as e:
            print(
                f"AGE CHECK ERROR: {type(e).__name__}: {e}",
                flush=True,
            )
            adult_confirmed = False

        if not adult_confirmed:
            await message.answer(
                "🔞 <b>Подтверждение возраста</b>\n\n"
                "Поиск алкогольной продукции доступен только "
                "совершеннолетним пользователям.\n"
                "Подтверди, что тебе уже исполнилось 18 лет.",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="✅ Мне есть 18 лет",
                                callback_data="age18_confirm",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="❌ Отмена",
                                callback_data="age18_cancel",
                            )
                        ],
                    ]
                ),
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

            user_city,

        )

        if not results:
            fallback_query = (
                build_fallback_search_query(
                    user_query
                )
            )

            if (
                fallback_query
                and fallback_query != search_query
            ):
                print(
                    f"FALLBACK SEARCH QUERY: "
                    f"{fallback_query}",
                    flush=True,
                )

                results = await asyncio.to_thread(

                    search_google_shopping,

                    fallback_query,

                    user_city,

                )

                if results:
                    search_query = fallback_query

        if (
            not results
            and is_age_restricted_query(
                user_query
            )
        ):
            web_query = (
                build_fallback_search_query(
                    user_query
                )
            )
            results = await asyncio.to_thread(

                search_retailer_web,

                web_query,

                user_city,

            )

            if results:
                search_query = web_query

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
        match_text = (
            item.get("match_text")
            or title
        )
        matching_item = dict(item)
        matching_item["title"] = match_text


        try:

            relevant = is_relevant_result(

                user_query,

                matching_item,

            )

        except Exception as e:

            print(
                f"MATCH ERROR: "
                f"{type(e).__name__}: {e}",
                flush=True,
            )

            relevant = False


        if (
            not relevant
            and item.get("web_search_result")
        ):
            requested_pack = extract_pack_count(
                user_query
            )
            unit_query = (
                build_fallback_search_query(
                    user_query
                )
            )
            item_pack = extract_pack_count(
                title
            )

            if (
                requested_pack
                and item_pack is None
                and unit_query
            ):
                try:
                    relevant = is_relevant_result(

                        unit_query,

                        matching_item,

                    )
                except Exception:
                    relevant = False

                if relevant:
                    item["unit_numeric_price"] = (
                        item["numeric_price"]
                    )
                    item["numeric_price"] = round(
                        item["numeric_price"]
                        * requested_pack,
                        2,
                    )
                    item["calculated_pack_count"] = (
                        requested_pack
                    )

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
        cheapest_offer_per_retailer(
            filtered_results
        )[:10]
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

        f"📍 {html.escape(user_city)}",

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


        raw_link = item.get(
            "link"
        )


        store = html.escape(

            format_retailer_name(
                item.get("store"),
                raw_link,
            ),

            quote=True,

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


        calculation_line = ""

        if item.get("calculated_pack_count"):
            calculation_line = (
                "\n   ≈ Расчёт: "
                f"{item['calculated_pack_count']} × "
                f"{format_price(item['unit_numeric_price'])}"
            )


        # ----------------------------------------------------
        # RESULT
        # ----------------------------------------------------

        lines.append(

            f"{prefix} 🛒 "
            f"{store_line} — "
            f"{price_line}\n"

            f"   {title}"
            f"{calculation_line}"

        )


        lines.append("")


    # ========================================================
    # LOWEST PRICE
    # ========================================================

    lowest_price = (

        filtered_results[0]
        ["numeric_price"]

    )

    watch_token = None

    if message.from_user:

        try:

            watch_token = await asyncio.to_thread(

                create_watch_candidate,

                message.from_user.id,

                message.chat.id,

                user_query,

                search_query,

                lowest_price,

                user_city,

            )

        except Exception as e:

            print(
                f"WATCH CANDIDATE ERROR: "
                f"{type(e).__name__}: {e}",
                flush=True,
            )


    lowest_link = filtered_results[0].get(
        "link"
    )

    lowest_price_text = html.escape(
        format_price(lowest_price)
    )

    if lowest_link:

        safe_lowest_link = html.escape(
            str(lowest_link),
            quote=True,
        )

        lowest_price_text = (
            f'<a href="{safe_lowest_link}">'
            f"{lowest_price_text}"
            "</a>"
        )


    lines.append(

        "🔥 <b>Самая низкая "
        "найденная цена: "

        f"{lowest_price_text}"

        "</b>"

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


    reply_markup = None

    if watch_token:

        reply_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔔 Следить за снижением",
                        callback_data=f"watch:{watch_token}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📍 Изменить город",
                        callback_data="city_help",
                    )
                ],
            ]
        )

    await status_message.edit_text(

        "\n".join(lines),

        disable_web_page_preview=True,

        reply_markup=reply_markup,

    )


# ============================================================
# AUTOMATIC SUBSCRIPTION CHECKS
# ============================================================

def find_lowest_subscription_offer(
    product_query: str,
    prepared_query: str,
    city: str,
) -> dict[str, Any] | None:
    def matching_offers(
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        matching = []

        for item in results or []:
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

            try:
                relevant = is_relevant_result(
                    product_query,
                    item,
                )
            except Exception:
                relevant = False

            if not relevant:
                continue

            item = dict(item)
            item["numeric_price"] = numeric_price
            matching.append(item)

        return matching

    results = search_google_shopping(
        prepared_query,
        city,
    )
    matching = matching_offers(
        results
    )

    if not matching:
        fallback_query = (
            build_fallback_search_query(
                product_query
            )
        )

        if (
            fallback_query
            and fallback_query != prepared_query
        ):
            fallback_results = (
                search_google_shopping(
                    fallback_query,
                    city,
                )
            )
            matching = matching_offers(
                fallback_results
            )

    if not matching:
        return None

    return min(
        matching,
        key=lambda item:
        item["numeric_price"],
    )


async def check_price_subscriptions() -> dict[str, int]:
    if bot is None:
        return {
            "checked": 0,
            "notified": 0,
            "failed": 0,
        }

    subscriptions = await asyncio.to_thread(
        get_due_subscriptions,
        10,
    )

    checked = 0
    notified = 0
    failed = 0

    for subscription in subscriptions:
        subscription_id = subscription["id"]

        try:
            offer = await asyncio.to_thread(
                find_lowest_subscription_offer,
                subscription["product_query"],
                subscription["search_query"],
                subscription.get("city")
                or "Москва, Россия",
            )

            if offer is None:
                await asyncio.to_thread(
                    record_price_check,
                    subscription_id,
                    None,
                )
                checked += 1
                continue

            current_price = float(
                offer["numeric_price"]
            )
            baseline_price = float(
                subscription["baseline_price"]
            )
            notify = (
                current_price < baseline_price
                and should_notify(
                    current_price,
                    subscription["last_seen_price"],
                    subscription["last_notified_price"],
                )
            )

            if notify:
                previous_price = float(
                    subscription["last_seen_price"]
                )
                discount = (
                    (previous_price - current_price)
                    / previous_price
                    * 100
                )

                store = html.escape(
                    format_retailer_name(
                        offer.get("store"),
                        offer.get("link"),
                    )
                )
                title = html.escape(
                    offer.get("title")
                    or subscription["product_query"]
                )
                link = offer.get("link")
                link_line = ""

                if link:
                    safe_link = html.escape(
                        str(link),
                        quote=True,
                    )
                    link_line = (
                        f'\n<a href="{safe_link}">'
                        "Открыть предложение"
                        "</a>"
                    )

                await bot.send_message(
                    chat_id=subscription["chat_id"],
                    text=(
                        "🔔 <b>Цена снизилась!</b>\n\n"
                        f"{title}\n"
                        f"Магазин: <b>{store}</b>\n"
                        f"Новая цена: "
                        f"<b>{format_price(current_price)}</b>\n"
                        f"Предыдущая цена: "
                        f"{format_price(previous_price)}\n"
                        f"Снижение: <b>{discount:.1f}%</b>"
                        f"{link_line}"
                    ),
                    disable_web_page_preview=True,
                )
                notified += 1

            await asyncio.to_thread(
                record_price_check,
                subscription_id,
                current_price,
                notify,
            )
            checked += 1

        except Exception as e:
            failed += 1
            print(
                f"SUBSCRIPTION CHECK ERROR "
                f"{subscription_id}: "
                f"{type(e).__name__}: {e}",
                flush=True,
            )
            try:
                await asyncio.to_thread(
                    record_price_check,
                    subscription_id,
                    None,
                )
            except Exception:
                pass

    return {
        "checked": checked,
        "notified": notified,
        "failed": failed,
    }


@app.get("/tasks/check-prices")
async def scheduled_price_check():
    result = await check_price_subscriptions()
    print(
        f"SUBSCRIPTION CHECK: {result}",
        flush=True,
    )
    return {
        "status": "ok",
        **result,
    }


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


    await bot.set_my_commands([
        BotCommand(
            command="city",
            description="Выбрать город поиска",
        ),
        BotCommand(
            command="subscriptions",
            description="Мои подписки",
        ),
        BotCommand(
            command="start",
            description="Помощь",
        ),
    ])


    await bot.set_webhook(

        url=WEBHOOK_URL,

        secret_token=WEBHOOK_SECRET,

        drop_pending_updates=False,

        allowed_updates=(
            dp.resolve_used_update_types()
        ),

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
        await asyncio.to_thread(
            init_subscriptions
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
