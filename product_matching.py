import re


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    text = str(text or "").lower().replace("ё", "е")

    replacements = {
        "×": "x",
        "–": "-",
        "—": "-",
        "−": "-",

        "гб": "gb",
        "гигабайт": "gb",
        "гигабайта": "gb",

        "тб": "tb",
        "терабайт": "tb",
        "терабайта": "tb",

        "кг": "kg",
        "килограмм": "kg",
        "килограмма": "kg",

        "мл": "ml",
        "миллилитров": "ml",

        "литров": "l",
        "литра": "l",
        "литр": "l",

        "шт.": "шт",
        "штук": "шт",
        "штуки": "шт",

        "дюйма": "inch",
        "дюймов": "inch",
        "дюйм": "inch",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Разделяем 256GB -> 256 GB
    text = re.sub(
        r"(\d)([a-zа-я])",
        r"\1 \2",
        text,
    )

    text = re.sub(
        r"([a-zа-я])(\d)",
        r"\1 \2",
        text,
    )

    text = re.sub(
        r"[^\w\s./+-]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# ACCESSORIES
# ============================================================

ACCESSORY_WORDS = {
    "чехол",
    "чехлы",
    "case",
    "cover",

    "стекло",
    "glass",
    "защитное",
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

    "ремешок",
    "strap",

    "аксессуар",
    "аксессуары",
    "accessory",
    "accessories",

    "накладка",
    "бампер",

    "powerbank",
    "power",
    "bank",

    "переходник",
    "штатив",

    "сумка",
    "bag",
}


def has_accessory_marker(text: str) -> bool:
    normalized = normalize_text(text)
    tokens = set(normalized.split())

    for word in ACCESSORY_WORDS:
        if word in tokens:
            return True

    return False


# ============================================================
# ATTRIBUTES
# ============================================================

def extract_storage(text: str):
    """
    Возвращает память в GB.

    256 GB -> 256
    512 GB -> 512
    1 TB -> 1024
    """

    normalized = normalize_text(text)

    result = []

    pattern = re.compile(
        r"\b(\d+(?:[.,]\d+)?)\s*(gb|tb)\b"
    )

    for value, unit in pattern.findall(normalized):
        number = float(value.replace(",", "."))

        if unit == "tb":
            number *= 1024

        result.append(int(number))

    return result or None


def extract_volume(text: str):
    """
    Возвращает объём в миллилитрах.

    1.5 l -> 1500
    500 ml -> 500
    """

    normalized = normalize_text(text)

    result = []

    pattern = re.compile(
        r"\b(\d+(?:[.,]\d+)?)\s*(ml|l)\b"
    )

    for value, unit in pattern.findall(normalized):
        number = float(value.replace(",", "."))

        if unit == "l":
            number *= 1000

        result.append(round(number, 2))

    return result or None


def extract_weight(text: str):
    """
    Возвращает вес в граммах.

    1 kg -> 1000
    500 g -> 500
    """

    normalized = normalize_text(text)

    result = []

    pattern = re.compile(
        r"\b(\d+(?:[.,]\d+)?)\s*(kg|g)\b"
    )

    for value, unit in pattern.findall(normalized):
        number = float(value.replace(",", "."))

        if unit == "kg":
            number *= 1000

        result.append(round(number, 2))

    return result or None


def extract_count(text: str):
    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+)\s*(?:шт|pcs|pieces)\b",
        normalized,
    )

    if not matches:
        return None

    return [int(value) for value in matches]


def extract_diagonal(text: str):
    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(?:inch|")\b",
        normalized,
    )

    if not matches:
        return None

    return [
        float(value.replace(",", "."))
        for value in matches
    ]


# ============================================================
# PAMPERS SIZE
# ============================================================

def extract_pampers_size(text: str):
    normalized = normalize_text(text)

    if not any(
        word in normalized
        for word in (
            "pampers",
            "памперс",
            "подгуз",
        )
    ):
        return None

    patterns = [
        r"\bpremium\s+care\s+([1-7])\b",
        r"\bpampers\s+(?:premium\s+care\s+)?([1-7])\b",
        r"\bразмер\s*([1-7])\b",
        r"\bsize\s*([1-7])\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            normalized,
        )

        if match:
            return int(match.group(1))

    if "newborn" in normalized:
        return 0

    return None


# ============================================================
# TOKENIZATION
# ============================================================

STOP_WORDS = {
    "и",
    "или",
    "для",
    "с",
    "со",
    "на",
    "в",
    "из",
    "по",
    "шт",
    "pcs",
    "pieces",

    "новый",
    "новая",
    "новое",

    "оригинал",
    "оригинальный",
    "original",

    "global",
    "россия",
    "российский",
    "ru",

    "смартфон",
    "телефон",

    "товар",
    "купить",
    "цена",
}


def tokenize(text: str):
    normalized = normalize_text(text)

    return [
        token
        for token in normalized.split()
        if token not in STOP_WORDS
        and len(token) >= 2
    ]


# ============================================================
# BRANDS
# ============================================================

BRAND_ALIASES = {
    "apple": {
        "apple",
    },

    "samsung": {
        "samsung",
    },

    "xiaomi": {
        "xiaomi",
        "сяоми",
    },

    "redmi": {
        "redmi",
    },

    "honor": {
        "honor",
        "хонор",
    },

    "huawei": {
        "huawei",
    },

    "google": {
        "google",
    },

    "oneplus": {
        "oneplus",
    },

    "oppo": {
        "oppo",
    },

    "realme": {
        "realme",
    },

    "sony": {
        "sony",
    },

    "lg": {
        "lg",
    },

    "bosch": {
        "bosch",
    },

    "philips": {
        "philips",
    },

    "pampers": {
        "pampers",
        "памперс",
        "подгуз",
    },

    "huggies": {
        "huggies",
    },

    "lavazza": {
        "lavazza",
    },

    "nescafe": {
        "nescafe",
        "нескафе",
    },

    "coca-cola": {
        "coca",
        "coca-cola",
        "кока",
        "кока-кола",
    },

    "pepsi": {
        "pepsi",
    },
}


def detect_brands(text: str):
    normalized = normalize_text(text)

    found = set()

    for canonical, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                found.add(canonical)
                break

    return found


# ============================================================
# VARIANT FAMILIES
# ============================================================

VARIANT_FAMILIES = [
    {
        "pro",
        "pro max",
        "plus",
        "air",
        "mini",
        "max",
    },

    {
        "ultra",
        "plus",
        "fe",
        "lite",
        "mini",
        "pro",
        "pro max",
        "max",
    },

    {
        "zero",
        "light",
        "diet",
        "classic",
        "original",
    },

    {
        "fold",
        "flip",
    },
]


def contains_phrase(text: str, phrase: str) -> bool:
    normalized = normalize_text(text)

    if " " in phrase:
        return phrase in normalized.split(
            " "
        ) if False else phrase in normalized

    return phrase in set(
        normalized.split()
    )


def extract_variants(text: str):
    normalized = normalize_text(text)

    found = set()

    phrases = {
        "pro max",
        "pro",
        "plus",
        "air",
        "mini",
        "max",
        "ultra",
        "fe",
        "lite",
        "zero",
        "light",
        "diet",
        "classic",
        "original",
        "fold",
        "flip",
    }

    for phrase in phrases:
        if contains_phrase(
            normalized,
            phrase,
        ):
            found.add(phrase)

    return found


# ============================================================
# ATTRIBUTE MATCHING
# ============================================================

def values_match(
    query_values,
    title_values,
):
    if not query_values:
        return True

    if not title_values:
        return False

    return all(
        value in title_values
        for value in query_values
    )


def attributes_match(
    query: str,
    title: str,
):
    query_storage = extract_storage(query)
    title_storage = extract_storage(title)

    if not values_match(
        query_storage,
        title_storage,
    ):
        return False

    query_volume = extract_volume(query)
    title_volume = extract_volume(title)

    if not values_match(
        query_volume,
        title_volume,
    ):
        return False

    query_weight = extract_weight(query)
    title_weight = extract_weight(title)

    if not values_match(
        query_weight,
        title_weight,
    ):
        return False

    query_count = extract_count(query)
    title_count = extract_count(title)

    if not values_match(
        query_count,
        title_count,
    ):
        return False

    query_diagonal = extract_diagonal(query)
    title_diagonal = extract_diagonal(title)

    if query_diagonal:
        if not title_diagonal:
            return False

        for value in query_diagonal:
            if value not in title_diagonal:
                return False

    query_pampers = extract_pampers_size(query)

    if query_pampers is not None:
        title_pampers = extract_pampers_size(title)

        if title_pampers != query_pampers:
            return False

    return True


# ============================================================
# VARIANT MATCHING
# ============================================================

def variants_match(
    query: str,
    title: str,
):
    query_variants = extract_variants(query)
    title_variants = extract_variants(title)

    # Все явно указанные варианты запроса
    # должны присутствовать в результате.
    for variant in query_variants:
        if variant not in title_variants:
            return False

    # Если запрос содержит конкретный вариант,
    # несовместимый вариант в названии запрещаем.
    if query_variants:
        for family in VARIANT_FAMILIES:
            query_family = query_variants & family
            title_family = title_variants & family

            if query_family and title_family:
                if query_family.isdisjoint(
                    title_family
                ):
                    return False

    # Если запрос без варианта,
    # не принимаем очевидно другой вариант
    # для известных семейств.
    if not query_variants:
        for family in VARIANT_FAMILIES:
            title_family = title_variants & family

            if len(title_family) > 0:
                return False

    return True


# ============================================================
# IDENTITY MATCHING
# ============================================================

def identity_tokens(
    text: str,
):
    tokens = tokenize(text)

    # Убираем числа характеристик.
    attributes = set()

    for value in extract_storage(text) or []:
        attributes.add(str(value))

    for value in extract_volume(text) or []:
        attributes.add(str(value))

    for value in extract_weight(text) or []:
        attributes.add(str(value))

    for value in extract_count(text) or []:
        attributes.add(str(value))

    for value in extract_diagonal(text) or []:
        attributes.add(str(value))

    result = set()

    for token in tokens:
        if token in attributes:
            continue

        # Чистые числа характеристик не являются
        # частью названия товара.
        if re.fullmatch(
            r"\d+(?:[.,]\d+)?",
            token,
        ):
            continue

        result.add(token)

    return result


def identity_match(
    query: str,
    title: str,
):
    query_tokens = identity_tokens(query)
    title_tokens = identity_tokens(title)

    if not query_tokens:
        return True

    # Каждый существенный токен запроса должен
    # встречаться в названии результата.
    missing = query_tokens - title_tokens

    if missing:
        return False

    return True


# ============================================================
# MAIN MATCHER
# ============================================================

def is_relevant_result(
    query: str,
    item: dict,
) -> bool:
    title = item.get("title") or ""

    if not title:
        return False

    # --------------------------------------------------------
    # 1. Accessories
    # --------------------------------------------------------

    if not has_accessory_marker(query):
        if has_accessory_marker(title):
            return False

    # --------------------------------------------------------
    # 2. Brand
    # --------------------------------------------------------

    query_brands = detect_brands(query)
    title_brands = detect_brands(title)

    if query_brands:
        if not query_brands.intersection(
            title_brands
        ):
            return False

    # --------------------------------------------------------
    # 3. Attributes
    # --------------------------------------------------------

    if not attributes_match(
        query,
        title,
    ):
        return False

    # --------------------------------------------------------
    # 4. Variants
    # --------------------------------------------------------

    if not variants_match(
        query,
        title,
    ):
        return False

    # --------------------------------------------------------
    # 5. Product identity
    # --------------------------------------------------------

    if not identity_match(
        query,
        title,
    ):
        return False

    return True
