import os
import re
from typing import Any
from urllib.parse import urlparse

SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN")
SCRAPEDO_SEARCH_URL = (
    "https://api.scrape.do/plugin/google/search"
)


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
    "market.yandex.ru",
    "ozon.ru",
    "wildberries.ru",
    "perekrestok.ru",
    "5ka.ru",
    "dixy.ru",
    "magnit.ru",
    "vkusvill.ru",
    "av.ru",
    "chizhik.club",
    "svetoforonline.ru",
    "winelab.ru",
    "krasnoeibeloe.ru",
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


# Крупные продуктовые сети, которые хотим проверять
# в первую очередь для продуктовых запросов.
GROCERY_RETAILERS = (
    ("perekrestok.ru", "🟢 Перекрёсток"),
    ("5ka.ru", "🟢 Пятёрочка"),
    ("magnit.ru", "🔴 Магнит"),
    ("dixy.ru", "🟠 Дикси"),
    ("chizhik.club", "🟡 Чижик"),
    ("svetoforonline.ru", "🔴 Светофор"),
    ("vkusvill.ru", "🟢 ВкусВилл"),
    ("av.ru", "🟣 Азбука Вкуса"),
)


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

    match = PRICE_PATTERN.search(
        searchable
    )

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

            # Для части продуктовых сетей Google может
            # вернуть полезную индексируемую страницу без
            # стандартного пути карточки. Не отбрасываем
            # непустые страницы полностью.
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

    return (
        f"цена купить ({scopes})"
    )


def _build_offer(
    result: dict[str, Any],
) -> dict[str, Any] | None:

    link = str(
        result.get("link")
        or ""
    ).strip()

    if not link:
        return None

    retailer = _retailer_name(
        link
    )

    if not retailer:
        return None

    if not _is_product_link(link):
        return None

    price = _extract_price(
        result
    )

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


def _organic_results(
    data: dict[str, Any],
) -> list[dict[str, Any]]:

    raw_results = data.get(
        "organic_results",
        [],
    )

    if not isinstance(
        raw_results,
        list,
    ):
        return []

    return [
        item
        for item in raw_results
        if isinstance(item, dict)
    ]


# ============================================================
# GOOGLE WEB SEARCH
# ============================================================

def _run_google_search(
    query: str,
    location: str | None = None,
) -> list[dict[str, Any]]:

    import requests

    if not SCRAPEDO_TOKEN:

        raise RuntimeError(
            "SCRAPEDO_TOKEN is not set"
        )

    params = {
        "token": SCRAPEDO_TOKEN,
        "q": query,
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

    return _organic_results(
        data
    )


# ============================================================
# RETAILER SEARCH
# ============================================================

def search_retailer_web(
    query: str,
    location: str | None = None,
) -> list[dict[str, Any]]:

    retailer_hint = (
        _retailer_search_hint()
    )

    organic_results = (
        _run_google_search(
            f"{query} {retailer_hint}",
            location,
        )
    )

    offers: list[
        dict[str, Any]
    ] = []

    seen = set()


    for result in organic_results:

        offer = _build_offer(
            result
        )

        if offer is None:
            continue

        identity = (
            str(offer.get("store") or ""),
            str(offer.get("link") or ""),
        )

        if identity in seen:
            continue

        seen.add(identity)

        offers.append(
            offer
        )


    # --------------------------------------------------------
    # EXTRA GROCERY SEARCH
    # --------------------------------------------------------
    #
    # Google не всегда возвращает все продуктовые сети,
    # если объединить много site: операторов в один запрос.
    # Поэтому отдельно проверяем крупные продуктовые сети,
    # которых нет в общей выдаче.
    #
    # Цена при этом НЕ придумывается. Если сеть не публикует
    # цену без выбора магазина, результат будет отмечен
    # price_requires_store=True.
    # --------------------------------------------------------

    found_retailers = {
        str(
            offer.get("store")
            or ""
        )
        for offer in offers
    }


    for domain, retailer_name in (
        GROCERY_RETAILERS
    ):

        if retailer_name in found_retailers:
            continue

        try:

            retailer_results = (
                _run_google_search(
                    (
                        f"{query} "
                        f"site:{domain}"
                    ),
                    location,
                )
            )

        except Exception as error:

            print(
                "GROCERY RETAILER SEARCH ERROR: "
                f"{retailer_name}: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True,
            )

            continue


        retailer_offer = None


        for result in retailer_results:

            offer = _build_offer(
                result
            )

            if offer is None:
                continue

            if (
                offer.get("store")
                != retailer_name
            ):
                continue

            retailer_offer = offer
            break


        if retailer_offer is None:
            continue


        identity = (
            str(
                retailer_offer.get(
                    "store"
                )
                or ""
            ),
            str(
                retailer_offer.get(
                    "link"
                )
                or ""
            ),
        )


        if identity in seen:
            continue


        seen.add(identity)

        offers.append(
            retailer_offer
        )

        found_retailers.add(
            retailer_name
        )


    return offers
