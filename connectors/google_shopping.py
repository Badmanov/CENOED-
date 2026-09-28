import os
from typing import Any

import requests


SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN")
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SEARCHAPI_KEY = os.getenv("SEARCHAPI_KEY")

SCRAPEDO_URL = "https://api.scrape.do/plugin/google/shopping"
SERPAPI_URL = "https://serpapi.com/search.json"
SEARCHAPI_URL = "https://www.searchapi.io/api/v1/search"


def _fetch_shopping_data(
    query: str,
    location: str | None,
) -> dict[str, Any]:
    errors: list[str] = []

    if SCRAPEDO_TOKEN:
        params = {
            "token": SCRAPEDO_TOKEN,
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

    if SERPAPI_KEY:
        params = {
            "api_key": SERPAPI_KEY,
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

    if SEARCHAPI_KEY:
        params = {
            "api_key": SEARCHAPI_KEY,
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

    data = _fetch_shopping_data(query, location)

    results = []

    for item in data.get("shopping_results", []):
        price = item.get("extracted_price")

        results.append(
            {
                "title": item.get("title"),
                "price": price,
                "price_text": item.get("price"),
                "old_price": item.get("extracted_old_price"),
                "old_price_text": item.get("old_price"),
                "store": item.get("source"),
                "link": item.get("product_link"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews"),
                "delivery": item.get("delivery"),
                "extensions": item.get("extensions", []),
            }
        )

    return results
