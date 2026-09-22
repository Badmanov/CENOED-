import os
from typing import Any

import requests


SCRAPEDO_TOKEN = os.getenv("SCRAPEDO_TOKEN")

SCRAPEDO_URL = "https://api.scrape.do/plugin/google/shopping"


def search_google_shopping(query: str) -> list[dict[str, Any]]:
    """
    Ищет товар в Google Shopping через Scrape.do
    с ориентацией на российский рынок.
    """

    if not SCRAPEDO_TOKEN:
        raise RuntimeError("SCRAPEDO_TOKEN is not set")

    params = {
        "token": SCRAPEDO_TOKEN,
        "q": query,
        "hl": "ru",
        "gl": "ru",
        "google_domain": "google.ru",
        "device": "desktop",
        "sort_by": 0,
    }

    response = requests.get(
        SCRAPEDO_URL,
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

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
