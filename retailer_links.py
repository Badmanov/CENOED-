import re
from urllib.parse import quote_plus


GROCERY_QUERY_TERMS = {
    "вода",
    "напиток",
    "газировка",
    "кола",
    "сок",
    "нектар",
    "чай",
    "кофе",
    "молоко",
    "кефир",
    "йогурт",
    "сыр",
    "масло",
    "хлеб",
    "батон",
    "яйцо",
    "яйца",
    "мясо",
    "курица",
    "рыба",
    "колбаса",
    "сосиски",
    "макароны",
    "крупа",
    "рис",
    "гречка",
    "мука",
    "сахар",
    "соль",
    "печенье",
    "конфеты",
    "шоколад",
    "чипсы",
    "соус",
    "майонез",
    "кетчуп",
}


BASE_GROCERY_RETAILERS = (
    ("🟢 Пятёрочка", "https://5ka.ru/"),
    ("🟢 Перекрёсток", "https://www.perekrestok.ru/"),
    ("🔴 Магнит", "https://magnit.ru/"),
    ("🟠 Дикси", "https://dixy.ru/"),
    ("🟢 ВкусВилл", "https://vkusvill.ru/"),
    ("🟣 Азбука Вкуса", "https://av.ru/"),
    ("🟡 Чижик", "https://chizhik.club/"),
    ("🔴 Светофор", "https://svetoforonline.ru/"),
)


ALCOHOL_RETAILERS = (
    ("🔞 ВинЛаб", "https://www.winelab.ru/"),
    ("🔞 Красное & Белое", "https://krasnoeibeloe.ru/"),
)


RETAILER_SEARCH_URLS = {
    "🟢 Перекрёсток": (
        "https://www.perekrestok.ru/cat/search?search={query}"
    ),
    "🟢 ВкусВилл": "https://vkusvill.ru/search/?q={query}",
}


def retailer_url_for_query(
    retailer_name: str,
    fallback_url: str,
    query: str | None,
) -> str:
    """Return a verified product-search URL or the official homepage."""
    search_url = RETAILER_SEARCH_URLS.get(retailer_name)
    cleaned_query = (query or "").strip()
    if not search_url or not cleaned_query:
        return fallback_url
    return search_url.format(query=quote_plus(cleaned_query))


def is_likely_grocery_query(
    text: str,
    *,
    age_restricted: bool = False,
) -> bool:
    if age_restricted:
        return True
    tokens = set(
        re.findall(r"[a-zа-яё]+", text.casefold())
    )
    return bool(tokens & GROCERY_QUERY_TERMS)


def large_retailers_for_query(
    query: str | None = None,
    *,
    age_restricted: bool = False,
) -> tuple[tuple[str, str], ...]:
    retailers = BASE_GROCERY_RETAILERS
    if age_restricted:
        retailers += ALCOHOL_RETAILERS
    return tuple(
        (
            retailer_name,
            retailer_url_for_query(
                retailer_name,
                retailer_url,
                query,
            ),
        )
        for retailer_name, retailer_url in retailers
    )
