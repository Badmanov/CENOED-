import asyncio
import html
import os
import re
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, Update
from fastapi import FastAPI, Header, HTTPException, Request
import uvicorn

from connectors.google_shopping import search_google_shopping


TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

BASE_WEBHOOK_URL = "https://cenoed.onrender.com"
WEBHOOK_PATH = "/telegram/webhook"
WEBHOOK_URL = f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}"

dp = Dispatcher()
app = FastAPI()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
async def health_check():
    return {
        "status": "ok",
        "bot": "ЦЕНОЕД",
        "version": "0.8"
    }


# ============================================================
# BASIC TEXT HELPERS
# ============================================================

def clean_query(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_text(text: str) -> str:
    text = text.lower().replace("ё", "е")

    replacements = {
        "ё": "е",
        "×": "x",
        "–": "-",
        "—": "-",
        "−": "-",
        "гб": "gb",
        "гигабайт": "gb",
        "гигабайта": "gb",
        "кг": "kg",
        "литров": "l",
        "литра": "l",
        "литр": "l",
        "мл": "ml",
        "миллилитров": "ml",
        "шт.": "шт",
        "штук": "шт",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^\w\s.\-/+]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_model_text(text: str) -> str:
    text = normalize_text(text)

    text = re.sub(r"\bapple\b", " ", text)
    text = re.sub(r"\bсмартфон\b", " ", text)
    text = re.sub(r"\bтелефон\b", " ", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


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

    cleaned = text.replace("\xa0", " ")

    cleaned = re.sub(
        r"[^\d,.\s]",
        "",
        cleaned
    )

    cleaned = cleaned.replace(" ", "")

    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "")
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    elif "," in cleaned:
        parts = cleaned.split(",")

        if len(parts) == 2 and len(parts[1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    elif "." in cleaned:
        parts = cleaned.split(".")

        if len(parts) > 2:
            cleaned = cleaned.replace(".", "")
        elif len(parts) == 2 and len(parts[1]) == 3:
            cleaned = cleaned.replace(".", "")

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
        return f"{int(numeric):,} ₽".replace(",", " ")

    return f"{numeric:,.2f} ₽".replace(",", " ").replace(".", ",")


# ============================================================
# PRODUCT MATCHING
# ============================================================

ACCESSORY_WORDS = {
    "чехол",
    "чехлы",
    "case",
    "cover",
    "glass",
    "стекло",
    "защитное стекло",
    "пленка",
    "пленку",
    "кабель",
    "cable",
    "charger",
    "зарядка",
    "зарядное",
    "адаптер",
    "adapter",
    "наушники",
    "headphones",
    "гарнитура",
    "держатель",
    "holder",
    "крепление",
    "ремешок",
    "strap",
    "аксессуар",
    "аксессуары",
    "accessory",
    "accessories",
    "накладка",
    "бампер",
    "powerbank",
    "power bank",
    "переходник",
    "штатив",
    "сумка",
    "bag",
}

NON_PRODUCT_WORDS = {
    "для",
    "совместимый",
    "совместимая",
    "совместимые",
    "compatible",
}

BRANDS = {
    "apple",
    "samsung",
    "xiaomi",
    "redmi",
    "honor",
    "huawei",
    "google",
    "oneplus",
    "oppo",
    "realme",
    "sony",
    "lg",
    "bosch",
    "philips",
    "pampers",
    "huggies",
    "lavazza",
    "nescafe",
    "coca",
    "coca-cola",
    "pepsi",
}


def has_accessory_marker(text: str) -> bool:
    normalized = normalize_text(text)

    for word in ACCESSORY_WORDS:
        if word in normalized:
            return True

    return False


def extract_storage(text: str):
    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d{2,5})\s*(?:gb|tb)\b",
        normalized
    )

    if not matches:
        return None

    return [int(value) for value in matches]


def extract_volume(text: str):
    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(ml|l)\b",
        normalized
    )

    if not matches:
        return None

    result = []

    for value, unit in matches:
        number = float(value.replace(",", "."))

        if unit == "l":
            number *= 1000

        result.append(round(number, 2))

    return result


def extract_weight(text: str):
    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(kg|g)\b",
        normalized
    )

    if not matches:
        return None

    result = []

    for value, unit in matches:
        number = float(value.replace(",", "."))

        if unit == "kg":
            number *= 1000

        result.append(round(number, 2))

    return result


def extract_count(text: str):
    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+)\s*(?:шт|штук|pcs|pieces)\b",
        normalized
    )

    if not matches:
        return None

    return [int(value) for value in matches]


# ============================================================
# IPHONE
# ============================================================

def extract_iphone_model(text: str):
    normalized = normalize_model_text(text)

    match = re.search(
        r"\biphone\s+(\d+)\s*(pro\s*max|pro|plus|air)?\b",
        normalized
    )

    if not match:
        return None

    number = match.group(1)
    variant = match.group(2) or ""

    variant = re.sub(r"\s+", "", variant)

    return {
        "number": number,
        "variant": variant,
    }


def iphone_models_match(query: str, title: str) -> bool:
    query_model = extract_iphone_model(query)

    if not query_model:
        return True

    result_model = extract_iphone_model(title)

    if not result_model:
        return False

    if result_model["number"] != query_model["number"]:
        return False

    query_variant = query_model["variant"]
    result_variant = result_model["variant"]

    if query_variant:
        if result_variant != query_variant:
            return False

    else:
        if result_variant:
            return False

    return True


# ============================================================
# PAMPERS
# ============================================================

PAMPERS_SIZE_WORDS = {
    "newborn": 0,
    "new born": 0,
    "nb": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
}


def extract_pampers_size(text: str):
    normalized = normalize_text(text)

    if not (
        "pampers" in normalized
        or "памперс" in normalized
        or "подгуз" in normalized
    ):
        return None

    patterns = [
        r"\bpremium\s+care\s+([1-7])\b",
        r"\bpampers\s+(?:premium\s+care\s+)?([1-7])\b",
        r"\bразмер\s*([1-7])\b",
        r"\bsize\s*([1-7])\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)

        if match:
            return int(match.group(1))

    if "newborn" in normalized or "new born" in normalized:
        return 0

    weight_range = re.search(
        r"\b\d+\s*-\s*\d+\s*kg\b",
        normalized
    )

    if weight_range:
        return None

    return None


def pampers_match(query: str, title: str) -> bool:
    query_size = extract_pampers_size(query)

    if query_size is None:
        return True

    result_size = extract_pampers_size(title)

    if result_size != query_size:
        return False

    return True


# ============================================================
# GENERIC ATTRIBUTE MATCHING
# ============================================================

def numbers_without_attributes(text: str):
    normalized = normalize_text(text)

    protected_spans = []

    patterns = [
        r"\b\d+(?:[.,]\d+)?\s*(?:gb|tb)\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:kg|g)\b",
        r"\b\d+(?:[.,]\d+)?\s*(?:ml|l)\b",
        r"\b\d+\s*(?:шт|штук|pcs|pieces)\b",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, normalized):
            protected_spans.append(match.span())

    numbers = []

    for match in re.finditer(r"\b\d+(?:[.,]\d+)?\b", normalized):
        start, end = match.span()

        if any(
            start >= p_start and end <= p_end
            for p_start, p_end in protected_spans
        ):
            continue

        numbers.append(match.group(0))

    return numbers


def important_tokens(text: str):
    normalized = normalize_model_text(text)

    tokens = normalized.split()

    ignored = {
        "и",
        "или",
        "для",
        "с",
        "со",
        "на",
        "в",
        "из",
        "по",
        "шт",
        "штук",
        "новый",
        "новая",
        "оригинал",
        "оригинальный",
        "original",
        "global",
        "россия",
        "российский",
        "ru",
    }

    return {
        token
        for token in tokens
        if token not in ignored
        and len(token) >= 2
    }


def brand_match(query: str, title: str) -> bool:
    q = normalize_text(query)
    t = normalize_text(title)

    query_brands = [
        brand for brand in BRANDS
        if brand in q
    ]

    if not query_brands:
        return True

    return any(brand in t for brand in query_brands)


def attribute_lists_match(query: str, title: str) -> bool:
    query_storage = extract_storage(query)

    if query_storage:
        result_storage = extract_storage(title)

        if not result_storage:
            return False

        for required in query_storage:
            if required not in result_storage:
                return False

    query_volume = extract_volume(query)

    if query_volume:
        result_volume = extract_volume(title)

        if not result_volume:
            return False

        for required in query_volume:
            if required not in result_volume:
                return False

    query_weight = extract_weight(query)

    if query_weight:
        result_weight = extract_weight(title)

        if not result_weight:
            return False

        for required in query_weight:
            if required not in result_weight:
                return False

    query_count = extract_count(query)

    if query_count:
        result_count = extract_count(title)

        if not result_count:
            return False

        for required in query_count:
            if required not in result_count:
                return False

    return True


# ============================================================
# UNIVERSAL PRODUCT MATCH
# ============================================================

def is_relevant_result(query: str, item: dict) -> bool:
    title = item.get("title") or ""

    if not title:
        return False

    query_normalized = normalize_text(query)

    if not has_accessory_marker(query):
        if has_accessory_marker(title):
            return False

    if not brand_match(query, title):
        return False

    if "iphone" in query_normalized:
        if not iphone_models_match(query, title):
            return False

    if (
        "pampers" in query_normalized
        or "памперс" in query_normalized
        or "подгуз" in query_normalized
    ):
        if not pampers_match(query, title):
            return False

    if not attribute_lists_match(query, title):
        return False

    q_tokens = important_tokens(query)
    t_tokens = important_tokens(title)

    characteristic_tokens = {
        "gb",
        "tb",
        "kg",
        "ml",
        "l",
        "g",
        "шт",
        "pcs",
        "pieces",
    }

    q_tokens -= characteristic_tokens
    t_tokens -= characteristic_tokens

    if len(q_tokens) <= 2:
        if not q_tokens.intersection(t_tokens):
            return False

    else:
        overlap = len(q_tokens.intersection(t_tokens))
        ratio = overlap / len(q_tokens)

        if ratio < 0.50:
            return False

    return True


# ============================================================
# START
# ============================================================

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


# ============================================================
# MESSAGE HANDLER
# ============================================================

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

    results_with_price = []

    for item in results:
        raw_price = (
            item.get("price")
            if item.get("price") is not None
            else item.get("price_text")
        )

        numeric_price = parse_price(raw_price)

        if numeric_price is None:
            continue

        item["numeric_price"] = numeric_price

        results_with_price.append(item)

    filtered_results = [
        item
        for item in results_with_price
        if is_relevant_result(query, item)
    ]

    if not filtered_results:
        await status_message.edit_text(
            "🦖 <b>Точных совпадений не нашёл.</b>\n\n"
            f"🔎 Искал:\n«{html.escape(query)}»\n\n"
            "Попробуй добавить бренд, модель, размер, "
            "объём или другую характеристику товара."
        )

        return

    filtered_results.sort(
        key=lambda item: item["numeric_price"]
    )

    filtered_results = filtered_results[:10]

    lines = [
        "🦖 <b>ЦЕНОЕД НАШЁЛ!</b>",
        "",
        f"🔎 <b>{html.escape(query)}</b>",
        ""
    ]

    for index, item in enumerate(
        filtered_results,
        start=1
    ):
        title = html.escape(
            item.get("title") or "Товар"
        )

        store = html.escape(
            item.get("store") or "Магазин",
            quote=True
        )

        raw_link = item.get("link")

        price = format_price(
            item["numeric_price"]
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

    lowest_price = filtered_results[0]["numeric_price"]

    lines.append(
        f"🔥 <b>Самая низкая найденная цена: "
        f"{format_price(lowest_price)}</b>"
    )

    lines.append("")
    lines.append(
        "🔔 Скоро добавим отслеживание цены."
    )

    await status_message.edit_text(
        "\n".join(lines),
        disable_web_page_preview=True
    )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None
    ),
):
    if not WEBHOOK_SECRET:
        raise HTTPException(
            status_code=500,
            detail="WEBHOOK_SECRET is not configured"
        )

    if (
        x_telegram_bot_api_secret_token
        != WEBHOOK_SECRET
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook secret"
        )

    data = await request.json()

    update = Update.model_validate(
        data,
        context={"bot": bot}
    )

    await dp.feed_update(
        bot,
        update
    )

    return {"ok": True}


# ============================================================
# BOT
# ============================================================

bot: Bot | None = None


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
        )
    )

    await bot.set_webhook(
        url=WEBHOOK_URL,
        secret_token=WEBHOOK_SECRET,
        drop_pending_updates=False,
    )

    print(
        f"WEBHOOK SET: {WEBHOOK_URL}",
        flush=True
    )


@app.on_event("startup")
async def startup_event():
    await setup_webhook()


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
        os.getenv("PORT", "10000")
    )

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )

    server = uvicorn.Server(config)

    await server.serve()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    asyncio.run(run_web())
