import os
import re
from typing import Any
from urllib.parse import urlparse

import requests


SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN")
SCRAPEDO_SEARCH_URL = (
    "https://api.scrape.do/plugin/google/search"
)

RETAILER_DOMAINS = (
    (("market.yandex",), "🟨 Яндекс Маркет"),
    (("winelab.ru",), "🔞 ВинЛаб"),
    (("krasnoeibeloe.ru",), "🔞 Красное & Белое"),
    (("perekrestok.ru",), "🟢 Перекрёсток"),
    (("5ka.ru",), "🟢 Пятёрочка"),
    (("dixy.ru",), "🟠 Дикси"),
    (("magnit.ru",), "🔴 Магнит"),
    (("vkusvill.ru",), "🟢 ВкусВилл"),
    (("av.ru",), "🟣 Азбука Вкуса"),
    (("ozon.ru",), "🟦 Ozon"),
    (
        ("wildberries.ru", "wb.ru"),
        "🟪 Wildberries",
    ),
)

PRICE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(\d{1,3}(?:[ \u00a0]\d{3})*|\d+)"
    r"(?:[,.](\d{2}))?\s*"
    r"(?:₽|руб(?:\.|ля|лей)?)",
    re.IGNORECASE,
)


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(
            _flatten_text(item)
            for item in value.values()
        )
    if isinstance(value, list):
        return " ".join(
            _flatten_text(item)
            for item in value
        )
    if value is None:
        return ""
    return str(value)


def _extract_price(result: dict[str, Any]) -> float | None:
    searchable = " ".join(
        (
            str(result.get("title") or ""),
            str(result.get("snippet") or ""),
            _flatten_text(
                result.get("rich_snippet")
            ),
        )
    )

    match = PRICE_PATTERN.search(
        searchable
    )
    if not match:
        return None

    whole = match.group(1).replace(
        " ",
        "",
    ).replace(
        "\u00a0",
        "",
    )
    fraction = match.group(2) or "00"
    price = float(
        f"{whole}.{fraction}"
    )
    return price if price > 0 else None


def _retailer_name(link: str) -> str | None:
    hostname = (
        urlparse(link).hostname
        or ""
    ).casefold()

    for markers, name in RETAILER_DOMAINS:
        if any(
            marker in hostname
            for marker in markers
        ):
            return name

    return None


def search_retailer_web(
    query: str,
    location: str | None = None,
) -> list[dict[str, Any]]:
    if not SCRAPEDO_TOKEN:
        raise RuntimeError(
            "SCRAPEDO_TOKEN is not set"
        )

    retailer_hint = (
        'цена купить '
        '(ВинЛаб OR "Красное Белое" OR '
        '"Яндекс Маркет" OR Перекрёсток)'
    )

    params = {
        "token": SCRAPEDO_TOKEN,
        "q": f"{query} {retailer_hint}",
        "hl": "ru",
        "gl": "ru",
        "google_domain": "google.ru",
        "device": "desktop",
        "resolveGoto": "true",
    }

    if location:
        params["location"] = location

    response = requests.get(
        SCRAPEDO_SEARCH_URL,
        params=params,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    offers = []

    for result in data.get(
        "organic_results",
        [],
    ):
        link = str(
            result.get("link")
            or ""
        ).strip()
        retailer = _retailer_name(
            link
        )
        price = _extract_price(
            result
        )

        if (
            not link
            or not retailer
            or price is None
        ):
            continue

        title = str(result.get("title") or "").strip()
        snippet = str(result.get("snippet") or "").strip()
        match_text = " ".join(
            part for part in (title, snippet) if part
        )

        offers.append(
            {
                "title": title or "Товар",
                "match_text": match_text,
                "snippet": snippet,
                "price": price,
                "price_text": None,
                "old_price": None,
                "old_price_text": None,
                "store": retailer,
                "link": link,
                "rating": None,
                "reviews": None,
                "delivery": None,
                "extensions": [],
                "web_search_result": True,
            }
        )

    return offers
