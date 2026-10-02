import html
import re
import time
from typing import Any
from urllib.parse import urljoin

from search_cache import (
    begin_search,
    clear_search_failure,
    configured_cache_ttl_seconds,
    finish_search,
    get_persistent_results,
    get_recent_failure,
    normalize_search_text,
    record_search_failure,
    save_persistent_results,
)


MAGNIT_SEARCH_URL = "https://magnit.ru/search"
MAGNIT_BASE_URL = "https://magnit.ru"
SEARCH_CACHE_TTL_SECONDS = configured_cache_ttl_seconds()
_SEARCH_CACHE: dict[
    tuple[str, str],
    tuple[float, list[dict[str, Any]]],
] = {}

_ARTICLE_PATTERN = re.compile(
    r'<article[^>]*data-test-id="v-product-preview"[^>]*>'
    r'(.*?)</article>',
    re.IGNORECASE | re.DOTALL,
)
_PRODUCT_LINK_PATTERN = re.compile(
    r'<a\b(?P<attributes>[^>]*\bdata-test-id="v-app-link"[^>]*)>',
    re.IGNORECASE | re.DOTALL,
)
_TITLE_PATTERN = re.compile(r'\btitle="([^"]+)"', re.IGNORECASE)
_HREF_PATTERN = re.compile(r'\bhref="([^"]+)"', re.IGNORECASE)
_CURRENT_PRICE_PATTERN = re.compile(
    r'unit-catalog-product-preview-prices__regular.*?'
    r'<span[^>]*>([\d\s.,]+)(?:&#8202;|\s)*₽',
    re.IGNORECASE | re.DOTALL,
)
_OLD_PRICE_PATTERN = re.compile(
    r'unit-catalog-product-preview-prices__sale.*?'
    r'<span[^>]*>([\d\s.,]+)(?:&#8202;|\s)*₽',
    re.IGNORECASE | re.DOTALL,
)


def _parse_price(value: str | None) -> float | None:
    if not value:
        return None
    normalized = value.replace(" ", "").replace("\u00a0", "").replace(",", ".")
    try:
        price = float(normalized)
    except ValueError:
        return None
    return price if price > 0 else None


def parse_magnit_search_page(page: str) -> list[dict[str, Any]]:
    """Extract official product cards from Magnit's server-rendered search."""
    offers: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for article_match in _ARTICLE_PATTERN.finditer(page):
        article = article_match.group(1)
        link_match = _PRODUCT_LINK_PATTERN.search(article)
        price_match = _CURRENT_PRICE_PATTERN.search(article)
        if link_match is None or price_match is None:
            continue

        attributes = link_match.group("attributes")
        title_match = _TITLE_PATTERN.search(attributes)
        href_match = _HREF_PATTERN.search(attributes)
        if title_match is None or href_match is None:
            continue

        title = html.unescape(title_match.group(1)).strip()
        # Magnit writes the category word as Latin "Cola" while Russian
        # users normally type "Кола". Normalize only this equivalent word so
        # the strict brand/variant checks remain effective.
        title = re.sub(r"\bcola\b", "Кола", title, flags=re.IGNORECASE)
        link = urljoin(
            MAGNIT_BASE_URL,
            html.unescape(href_match.group(1)).strip(),
        )
        price = _parse_price(price_match.group(1))
        if not title or not link or price is None or link in seen_links:
            continue

        old_price_match = _OLD_PRICE_PATTERN.search(article)
        old_price = _parse_price(
            old_price_match.group(1) if old_price_match else None
        )

        seen_links.add(link)
        offers.append(
            {
                "title": title,
                "match_text": title,
                "snippet": "Официальный каталог Магнита",
                "price": price,
                "price_text": None,
                "old_price": old_price,
                "old_price_text": None,
                "store": "🔴 Магнит",
                "link": link,
                "rating": None,
                "reviews": None,
                "delivery": None,
                "extensions": [],
                "official_retailer_result": True,
            }
        )

    return offers


def search_magnit(
    query: str,
    location: str | None = None,
) -> list[dict[str, Any]]:
    """Search Magnit's public catalogue without a paid search request."""
    import requests

    cache_key = (
        normalize_search_text(query),
        normalize_search_text(location),
    )
    cached = _SEARCH_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < SEARCH_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    persistent = get_persistent_results("magnit_official", query, location)
    if persistent is not None:
        _SEARCH_CACHE[cache_key] = (now, persistent)
        return [dict(item) for item in persistent]

    recent_failure = get_recent_failure("magnit_official", query, location)
    if recent_failure is not None:
        raise RuntimeError(f"Recent Magnit search failure: {recent_failure}")

    is_leader, completed = begin_search("magnit_official", query, location)
    if not is_leader:
        if not completed.wait(timeout=35):
            raise RuntimeError("Timed out waiting for identical Magnit search")
        return search_magnit(query, location)

    try:
        response = requests.get(
            MAGNIT_SEARCH_URL,
            params={"term": query},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            },
            timeout=25,
        )
        response.raise_for_status()
        offers = parse_magnit_search_page(response.text)
        _SEARCH_CACHE[cache_key] = (now, [dict(item) for item in offers])
        save_persistent_results(
            "magnit_official",
            query,
            location,
            offers,
            SEARCH_CACHE_TTL_SECONDS,
        )
        clear_search_failure("magnit_official", query, location)
        return offers
    except Exception as error:
        record_search_failure("magnit_official", query, location, error)
        raise
    finally:
        finish_search("magnit_official", query, location)
