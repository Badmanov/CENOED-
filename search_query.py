import re

from product_matching import (
    has_accessory_marker,
    normalize_text,
)


# ============================================================
# ACCESSORY SEARCH
# ============================================================

ACCESSORY_SEARCH_WORDS = {
    "чехол",
    "чехлы",
    "case",
    "cover",

    "стекло",
    "glass",

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
    "крепеж",

    "ремешок",
    "strap",

    "бампер",
    "накладка",

    "аксессуар",
    "аксессуары",
    "accessory",
    "accessories",

    "powerbank",
    "пауэрбанк",

    "переходник",
    "штатив",

    "сумка",
    "bag",
}


# ============================================================
# ATTRIBUTE PATTERNS
# ============================================================

STORAGE_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:gb|tb)\b",
    re.IGNORECASE,
)


VOLUME_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ml|l)\b",
    re.IGNORECASE,
)


WEIGHT_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:kg|g)\b",
    re.IGNORECASE,
)


COUNT_PATTERN = re.compile(
    r"\b\d+\s*(?:шт|pcs|pieces)\b",
    re.IGNORECASE,
)


DIAGONAL_PATTERN = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:inch|in)\b",
    re.IGNORECASE,
)


DIAGONAL_QUOTE_PATTERN = re.compile(
    r'\b\d+(?:[.,]\d+)?\s*"',
    re.IGNORECASE,
)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_spaces(text: str) -> str:
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def remove_search_attributes(
    text: str,
) -> str:
    """
    Удаляет характеристики товара,
    которые мешают поиску аксессуара.

    Например:

    iPhone 17 Pro 256 GB
    ->
    iPhone 17 Pro

    500 ml
    ->
    удаляется

    1 kg
    ->
    удаляется
    """

    result = text

    patterns = (
        STORAGE_PATTERN,
        VOLUME_PATTERN,
        WEIGHT_PATTERN,
        COUNT_PATTERN,
        DIAGONAL_PATTERN,
        DIAGONAL_QUOTE_PATTERN,
    )

    for pattern in patterns:

        result = pattern.sub(
            " ",
            result,
        )

    return clean_spaces(result)


# ============================================================
# ACCESSORY WORDS
# ============================================================

def extract_accessory_words(
    text: str,
) -> list[str]:
    normalized = normalize_text(
        text
    )

    tokens = normalized.split()

    return [
        token
        for token in tokens
        if token in ACCESSORY_SEARCH_WORDS
    ]


# ============================================================
# QUERY NORMALIZATION
# ============================================================

def normalize_search_query(
    text: str,
) -> str:

    normalized = normalize_text(
        text
    )

    return clean_spaces(
        normalized
    )


# ============================================================
# ACCESSORY QUERY BUILDER
# ============================================================

def build_accessory_query(
    query: str,
) -> str:
    """
    Преобразует запрос пользователя
    для поиска аксессуара.

    Например:

    iPhone 17 Pro 256 GB чехол

    ->
    чехол iphone 17 pro

    iPhone 17 Pro 512 GB стекло

    ->
    стекло iphone 17 pro
    """

    normalized = normalize_search_query(
        query
    )

    # --------------------------------------------------------
    # Убираем характеристики самого устройства.
    # --------------------------------------------------------

    normalized = remove_search_attributes(
        normalized
    )

    # --------------------------------------------------------
    # Перестраиваем запрос:
    # сначала тип аксессуара,
    # затем модель устройства.
    # --------------------------------------------------------

    tokens = normalized.split()

    accessory_tokens = []

    product_tokens = []

    for token in tokens:

        if token in ACCESSORY_SEARCH_WORDS:

            if token not in accessory_tokens:

                accessory_tokens.append(
                    token
                )

        else:

            product_tokens.append(
                token
            )

    result_tokens = (
        accessory_tokens
        + product_tokens
    )

    result = " ".join(
        result_tokens
    )

    return clean_spaces(
        result
    )


# ============================================================
# REGULAR QUERY BUILDER
# ============================================================

def build_regular_query(
    query: str,
) -> str:
    """
    Обычный товар ищется практически
    без изменений.

    Например:

    iPhone 17 Pro 256 GB
    ->
    iPhone 17 Pro 256 GB
    """

    return normalize_search_query(
        query
    )


# ============================================================
# BROADER FALLBACK QUERY
# ============================================================

PACKAGING_COUNT_PATTERNS = (
    re.compile(
        r"\b(?:упаковк\w*\s+(?:из|по)\s*)?"
        r"\d+\s*"
        r"(?:бутыл\w*|банк\w*|пач\w*|"
        r"упаков\w*|шт\.?|pcs|pieces)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:pack|case)\s*(?:of\s*)?\d+\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d+\s*[xх×]\s*"
        r"(?=\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    ),
)


def build_fallback_search_query(
    query: str,
) -> str:
    """
    Создаёт второй, менее строгий запрос,
    если магазинный поиск не вернул результатов.

    Убирается только количество единиц в упаковке.
    Бренд, название товара, объём и вес сохраняются.
    """

    result = normalize_search_query(
        query
    )

    for pattern in PACKAGING_COUNT_PATTERNS:
        result = pattern.sub(
            " ",
            result,
        )

    return clean_spaces(result)


# ============================================================
# MAIN SEARCH QUERY BUILDER
# ============================================================

def build_search_query(
    query: str,
) -> str:
    """
    Главная функция.

    Обычный товар:
        iPhone 17 Pro 256 GB
        ->
        iphone 17 pro 256 gb

    Аксессуар:
        iPhone 17 Pro 256 GB чехол
        ->
        чехол iphone 17 pro
    """

    normalized = normalize_search_query(
        query
    )

    if not normalized:
        return ""

    # --------------------------------------------------------
    # Определяем режим поиска.
    # --------------------------------------------------------

    if has_accessory_marker(
        normalized
    ):

        result = build_accessory_query(
            normalized
        )

    else:

        result = build_regular_query(
            normalized
        )

    return clean_spaces(
        result
    )
