import os
import re
import time
from typing import Any
from urllib.parse import urlparse

from search_cache import (
    begin_search,
    finish_search,
    get_persistent_results,
    save_persistent_results,
)

SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SEARCHAPI_KEY = os.getenv("SEARCHAPI_KEY")
SCRAPEDO_SEARCH_URL = "https://api.scrape.do/plugin/google/search"
SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
SEARCHAPI_SEARCH_URL = "https://www.searchapi.io/api/v1/search"
SEARCH_CACHE_TTL_SECONDS = 3600
_SEARCH_CACHE: dict[
    tuple[str, str],
    tuple[float, list[dict[str, Any]]],
] = {}


def _runtime_key(name: str, imported_value: str | None) -> str | None:
    """Read credentials at request time and ignore accidental whitespace."""
    value = os.getenv(name)
    if value is None:
        value = imported_value
    if not value:
        return None
    return value.strip() or None


# ============================================================
# RETAILERS
# ============================================================

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
    (("chizhik.club",), "🟡 Чижик"),
    (("svetoforonline.ru",), "🔴 Светофор"),
    (("ozon.ru",), "🟦 Ozon"),
    (
        ("wildberries.ru", "wb.ru"),
        "🟪 Wildberries",
    ),
)


RETAILER_SEARCH_DOMAINS = (
    "krasnoeibeloe.ru",
    "winelab.ru",
    "perekrestok.ru",
    "5ka.ru",
    "dixy.ru",
    "magnit.ru",
    "vkusvill.ru",
    "av.ru",
    "chizhik.club",
    "svetoforonline.ru",
)


STORE_SELECTION_RETAILERS = {
    "🔞 ВинЛаб",
    "🔞 Красное & Белое",
    "🟢 Перекрёсток",
    "🟢 Пятёрочка",
    "🟠 Дикси",
    "🔴 Магнит",
    "🟢 ВкусВилл",
    "🟣 Азбука Вкуса",
    "🟡 Чижик",
    "🔴 Светофор",
}

PREFERRED_RETAILERS = {
    name
    for _, name in RETAILER_DOMAINS
}


PRICE_PATTERN = re.compile(
    r"(?<!\d)"
    r"(\d{1,3}(?:[ \u00a0]\d{3})*|\d+)"
    r"(?:[,.](\d{2}))?\s*"
    r"(?:₽|руб(?:\.|ля|лей)?)",
    re.IGNORECASE,
)


# ============================================================
# HELPERS
# ============================================================

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


def _extract_price(
    result: dict[str, Any],
) -> float | None:

    searchable = " ".join(
        (
            str(result.get("title") or ""),
            str(result.get("snippet") or ""),
            _flatten_text(
                result.get("rich_snippet")
            ),
        )
    )

    match = PRICE_PATTERN.search(searchable)

    if not match:
        return None

    whole = (
        match.group(1)
        .replace(" ", "")
        .replace("\u00a0", "")
    )

    fraction = match.group(2) or "00"

    try:
        price = float(
            f"{whole}.{fraction}"
        )
    except ValueError:
        return None

    return price if price > 0 else None


def _retailer_name(
    link: str,
) -> str | None:

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


def _is_product_link(
    link: str,
) -> bool:

    parsed = urlparse(link)

    hostname = (
        parsed.hostname
        or ""
    ).casefold()

    path = parsed.path.casefold()


    if "market.yandex" in hostname:
        return (
            path.startswith("/card/")
            or path.startswith("/product/")
            or "/product--" in path
        )


    if "ozon.ru" in hostname:
        return "/product/" in path


    if (
        "wildberries.ru" in hostname
        or hostname == "wb.ru"
        or hostname.endswith(".wb.ru")
    ):
        return bool(
            re.search(
                r"/catalog/\d+/detail\.aspx/?$",
                path,
            )
        )


    if "krasnoeibeloe.ru" in hostname:
        return bool(
            re.match(
                r"^/catalog/[^/]+/[^/]+/?$",
                path,
            )
        )


    product_path_markers = {
        "perekrestok.ru": (
            "/cat/",
        ),
        "5ka.ru": (
            "/product/",
        ),
        "dixy.ru": (
            "/product/",
        ),
        "magnit.ru": (
            "/product/",
            "/catalog/",
        ),
        "vkusvill.ru": (
            "/goods/",
        ),
        "av.ru": (
            "/product/",
        ),
        "winelab.ru": (
            "/product/",
        ),
        "chizhik.club": (
            "/product/",
            "/catalog/",
        ),
        "svetoforonline.ru": (
            "/product/",
            "/catalog/",
        ),
    }


    for domain, markers in (
        product_path_markers.items()
    ):
        if domain in hostname:
            return (
                any(
                    marker in path
                    for marker in markers
                )
                or path not in {"", "/"}
            )


    return True


def _retailer_search_hint() -> str:

    scopes = " OR ".join(
        f"site:{domain}"
        for domain
        in RETAILER_SEARCH_DOMAINS
    )

    return f"цена купить ({scopes})"


def _build_offer(
    result: dict[str, Any],
) -> dict[str, Any] | None:

    link = str(
        result.get("link")
        or ""
    ).strip()

    if not link:
        return None

    retailer = _retailer_name(link)

    if not retailer:
        return None

    if not _is_product_link(link):
        return None

    price = _extract_price(result)

    price_requires_store = (
        price is None
        and retailer
        in STORE_SELECTION_RETAILERS
    )

    if (
        price is None
        and not price_requires_store
    ):
        return None

    title = str(
        result.get("title")
        or ""
    ).strip()

    snippet = str(
        result.get("snippet")
        or ""
    ).strip()

    match_text = " ".join(
        part
        for part in (
            title,
            snippet,
        )
        if part
    )

    return {
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
        "price_requires_store": (
            price_requires_store
        ),
    }


# ============================================================
# RETAILER SEARCH
# ============================================================

def search_retailer_web(
    query: str,
    location: str | None = None,
) -> list[dict[str, Any]]:

    import requests

    cache_key = (
        " ".join(query.casefold().split()),
        " ".join((location or "").casefold().split()),
    )
    cached = _SEARCH_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < SEARCH_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    persistent = get_persistent_results(
        "retailer_web",
        query,
        location,
    )
    if persistent is not None:
        _SEARCH_CACHE[cache_key] = (now, persistent)
        return [dict(item) for item in persistent]

    is_leader, completed = begin_search(
        "retailer_web",
        query,
        location,
    )
    if not is_leader:
        if not completed.wait(timeout=190):
            raise RuntimeError(
                "Timed out waiting for identical retailer search"
            )
        return search_retailer_web(query, location)

    try:
        retailer_hint = _retailer_search_hint()
        search_text = f"{query} {retailer_hint}"
        errors: list[str] = []
        data: dict[str, Any] | None = None
        scrapedo_token = _runtime_key("SCRAPEDO_TOKEN", SCRAPEDO_TOKEN)
        serpapi_key = _runtime_key("SERPAPI_KEY", SERPAPI_KEY)
        searchapi_key = _runtime_key("SEARCHAPI_KEY", SEARCHAPI_KEY)

        if scrapedo_token:
            params = {
                "token": scrapedo_token,
                "q": search_text,
                "hl": "ru",
                "gl": "ru",
                "google_domain": "google.ru",
                "device": "desktop",
                "resolveGoto": "true",
            }
            if location:
                params["location"] = location

            try:
                response = requests.get(
                    SCRAPEDO_SEARCH_URL,
                    params=params,
                    timeout=60,
                )
                response.raise_for_status()
                data = response.json()
            except Exception as error:
                errors.append(
                    f"Scrape.do: {type(error).__name__}"
                )

        if data is None and serpapi_key:
            params = {
                "api_key": serpapi_key,
                "engine": "google",
                "q": search_text,
                "hl": "ru",
                "gl": "ru",
                "google_domain": "google.ru",
                "device": "desktop",
            }
            if location:
                params["location"] = location

            try:
                response = requests.get(
                    SERPAPI_SEARCH_URL,
                    params=params,
                    timeout=60,
                )
                response.raise_for_status()
                candidate = response.json()
                if candidate.get("error"):
                    raise RuntimeError(str(candidate["error"]))
                data = candidate
            except Exception as error:
                errors.append(
                    f"SerpApi: {type(error).__name__}"
                )

        if data is None and searchapi_key:
            params = {
                "api_key": searchapi_key,
                "engine": "google",
                "q": search_text,
                "hl": "ru",
                "gl": "ru",
                "link": "resolved",
            }

            try:
                response = requests.get(
                    SEARCHAPI_SEARCH_URL,
                    params=params,
                    timeout=60,
                )
                response.raise_for_status()
                candidate = response.json()
                if candidate.get("error"):
                    raise RuntimeError(str(candidate["error"]))
                data = candidate
            except Exception as error:
                errors.append(
                    f"SearchApi: {type(error).__name__}"
                )

        if data is None:
            if not errors:
                raise RuntimeError(
                    "No retailer search provider is configured"
                )
            raise RuntimeError(
                "Retailer search providers failed: "
                + "; ".join(errors)
            )

        raw_results = data.get(
            "organic_results",
            [],
        )

        if not isinstance(raw_results, list):
            return []

        offers: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for result in raw_results:
            if not isinstance(result, dict):
                continue

            offer = _build_offer(result)

            if offer is None:
                continue

            identity = (
                str(offer.get("store") or ""),
                str(offer.get("link") or ""),
            )

            if identity in seen:
                continue

            seen.add(identity)
            offers.append(offer)

        _SEARCH_CACHE[cache_key] = (
            now,
            [dict(item) for item in offers],
        )
        save_persistent_results(
            "retailer_web",
            query,
            location,
            offers,
            SEARCH_CACHE_TTL_SECONDS,
        )
        return offers
    finally:
        finish_search("retailer_web", query, location)
