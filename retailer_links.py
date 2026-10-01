import re


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
    *,
    age_restricted: bool = False,
) -> tuple[tuple[str, str], ...]:
    retailers = BASE_GROCERY_RETAILERS
    if age_restricted:
        retailers += ALCOHOL_RETAILERS
    return retailers
