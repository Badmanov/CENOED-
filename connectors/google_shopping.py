import os
import time
from typing import Any

import requests
from search_cache import (
    begin_search,
    finish_search,
    get_persistent_results,
    save_persistent_results,
)


SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SEARCHAPI_KEY = os.getenv("SEARCHAPI_KEY")

SCRAPEDO_URL = "https://api.scrape.do/plugin/google/shopping"
SERPAPI_URL = "https://serpapi.com/search.json"
SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"
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


def _fetch_shopping_data(
    query: str,
    location: str | None,
) -> dict[str, Any]:
    errors: list[str] = []
    scrapedo_token = _runtime_key("SCRAPEDO_TOKEN", SCRAPEDO_TOKEN)
    serpapi_key = _runtime_key("SERPAPI_KEY", SERPAPI_KEY)
    searchapi_key = _runtime_key("SEARCHAPI_KEY", SEARCHAPI_KEY)

    if scrapedo_token:
        params = {
            "token": scrapedo_token,
            "q": query,
            "hl": "ru",
            "gl": "ru",
            "google_domain": "google.ru",
            "device": "desktop",
            "sort_by": 0,
        }
        if location:
            params["location"] = location

        try:
            response = requests.get(
                SCRAPEDO_URL,
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except Exception as error:
            errors.append(
                f"Scrape.do: {type(error).__name__}"
            )

    if serpapi_key:
        params = {
            "api_key": serpapi_key,
            "engine": "google_shopping",
            "q": query,
            "hl": "ru",
            "gl": "ru",
            "google_domain": "google.ru",
            "device": "desktop",
        }
        if location:
            params["location"] = location

        try:
            response = requests.get(
                SERPAPI_URL,
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            return data
        except Exception as error:
            errors.append(
                f"SerpApi: {type(error).__name__}"
            )

    if searchapi_key:
        params = {
            "api_key": searchapi_key,
            "engine": "google_shopping",
            "q": query,
            "hl": "ru",
            "gl": "ru",
            "link": "resolved",
        }
        try:
            response = requests.get(
                SEARCHAPI_URL,
                params=params,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            return data
        except Exception as error:
            errors.append(
                f"SearchApi: {type(error).__name__}"
            )

    if not errors:
        raise RuntimeError(
            "No shopping search provider is configured"
        )
    raise RuntimeError(
        "Shopping search providers failed: "
        + "; ".join(errors)
    )


def search_google_shopping(
    query: str,
    location: str | None = None,
) -> list[dict[str, Any]]:
    """
    Ищет товар через основной источник Scrape.do.
    При его недоступности использует SerpApi или SearchApi.
    """

    cache_key = (
        " ".join(query.casefold().split()),
        " ".join((location or "").casefold().split()),
    )
    cached = _SEARCH_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and now - cached[0] < SEARCH_CACHE_TTL_SECONDS:
        return [dict(item) for item in cached[1]]

    persistent = get_persistent_results(
        "google_shopping",
        query,
        location,
    )
    if persistent is not None:
        _SEARCH_CACHE[cache_key] = (now, persistent)
        return [dict(item) for item in persistent]

    is_leader, completed = begin_search(
        "google_shopping",
        query,
        location,
    )
    if not is_leader:
        if not completed.wait(timeout=190):
            raise RuntimeError("Timed out waiting for identical shopping search")
        return search_google_shopping(query, location)

    try:
        data = _fetch_shopping_data(query, location)

        results = []

        for item in data.get("shopping_results", []):
            price = item.get("extracted_price")

            results.append(
                {
                    "title": item.get("title"),
                    "price": price,
                    "price_text": item.get("price"),
                    "old_price": item.get("extracted_old_price")
                    or item.get("extracted_original_price"),
                    "old_price_text": item.get("old_price")
                    or item.get("original_price"),
                    "store": item.get("source") or item.get("seller"),
                    "link": item.get("product_link") or item.get("link"),
                    "rating": item.get("rating"),
                    "reviews": item.get("reviews"),
                    "delivery": item.get("delivery"),
                    "extensions": item.get("extensions", []),
                }
            )

        _SEARCH_CACHE[cache_key] = (
            now,
            [dict(item) for item in results],
        )
        save_persistent_results(
            "google_shopping",
            query,
            location,
            results,
            SEARCH_CACHE_TTL_SECONDS,
        )
        return results
    finally:
        finish_search("google_shopping", query, location)
