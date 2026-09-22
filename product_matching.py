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

    # 256GB -> 256 GB
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

    # Оставляем полезные символы названий и характеристик.
    text = re.sub(
        r"[^\w\s./+&-]",
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
    "пауэрбанк",

    "переходник",
    "штатив",

    "сумка",
    "bag",
}


def has_accessory_marker(text: str) -> bool:
    tokens = set(
        normalize_text(text).split()
    )

    return bool(
        tokens.intersection(ACCESSORY_WORDS)
    )


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

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(gb|tb)\b",
        normalized,
    )

    result = []

    for value, unit in matches:
        number = float(
            value.replace(",", ".")
        )

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

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(ml|l)\b",
        normalized,
    )

    result = []

    for value, unit in matches:
        number = float(
            value.replace(",", ".")
        )

        if unit == "l":
            number *= 1000

        result.append(
            round(number, 2)
        )

    return result or None


def extract_weight(text: str):
    """
    Возвращает вес в граммах.

    1 kg -> 1000
    500 g -> 500
    """

    normalized = normalize_text(text)

    # Русские варианты.
    normalized = re.sub(
        r"\bгр\b",
        "g",
        normalized,
    )

    normalized = re.sub(
        r"\bг\b",
        "g",
        normalized,
    )

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(kg|g)\b",
        normalized,
    )

    result = []

    for value, unit in matches:
        number = float(
            value.replace(",", ".")
        )

        if unit == "kg":
            number *= 1000

        result.append(
            round(number, 2)
        )

    return result or None


def extract_count(text: str):
    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+)\s*(?:шт|pcs|pieces)\b",
        normalized,
    )

    if not matches:
        return None

    return [
        int(value)
        for value in matches
    ]


def extract_diagonal(text: str):
    """
    Возвращает диагонали экранов в дюймах.

    Поддерживает:
    6.7 inch
    6.7 in
    6.7"
    """

    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(?:inch|in)\b",
        normalized,
    )

    if matches:
        return [
            float(
                value.replace(",", ".")
            )
            for value in matches
        ]

    # normalize_text удаляет кавычки.
    # Поэтому отдельно проверяем исходный текст.
    original = (
        str(text or "")
        .lower()
        .replace(",", ".")
    )

    quoted = re.findall(
        r"\b(\d+(?:\.\d+)?)\s*\"",
        original,
    )

    if quoted:
        return [
            float(value)
            for value in quoted
        ]

    return None


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
            return int(
                match.group(1)
            )

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

    # Единицы измерения не являются частью
    # идентичности товара.
    "gb",
    "tb",
    "kg",
    "g",
    "ml",
    "l",
    "inch",
    "in",
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
        "эппл",
    },

    "samsung": {
        "samsung",
        "самсунг",
    },

    "xiaomi": {
        "xiaomi",
        "сяоми",
        "ксиаоми",
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
        "хуавей",
    },

    "google": {
        "google",
        "гугл",
    },

    "oneplus": {
        "oneplus",
        "one plus",
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
        "coca-cola",
        "кока-кола",
    },

    "pepsi": {
        "pepsi",
    },
}


def detect_brands(text: str):
    normalized = normalize_text(text)
    tokens = set(
        normalized.split()
    )

    found = set()

    for canonical, aliases in BRAND_ALIASES.items():

        for alias in aliases:
            alias_normalized = normalize_text(
                alias
            )

            # Составные названия.
            if " " in alias_normalized:
                if alias_normalized in normalized:
                    found.add(canonical)
                    break

            # Обычные слова.
            elif alias_normalized in tokens:
                found.add(canonical)
                break

    return found


# ============================================================
# PRODUCT VARIANTS
# ============================================================

VARIANT_FAMILIES = [
    {
        "pro max",
        "pro",
        "plus",
        "air",
        "mini",
        "max",
    },

    {
        "ultra",
        "fe",
        "lite",
    },

    {
        "zero",
        "light",
        "diet",
        "classic",
    },

    {
        "fold",
        "flip",
    },
]


VARIANT_PHRASES = (
    "pro max",
    "pro",
    "plus",
    "ultra",
    "air",
    "mini",
    "max",
    "fe",
    "lite",
    "zero",
    "light",
    "diet",
    "classic",
    "fold",
    "flip",
)


def extract_variants(text: str):
    normalized = normalize_text(text)

    found = set()

    # Сначала длинные варианты.
    # Это важно для Pro Max.
    if re.search(
        r"\bpro\s+max\b",
        normalized,
    ):
        found.add("pro max")

    for phrase in VARIANT_PHRASES:

        if phrase == "pro max":
            continue

        if re.search(
            rf"(?<!\w){re.escape(phrase)}(?!\w)",
            normalized,
        ):
            found.add(phrase)

    # Pro Max — отдельная модификация,
    # а не одновременно Pro и Max.
    if "pro max" in found:
        found.discard("pro")
        found.discard("max")

    return found


def variants_match(
    query: str,
    title: str,
):
    query_variants = extract_variants(
        query
    )

    title_variants = extract_variants(
        title
    )

    # Все явно указанные варианты запроса
    # должны совпадать.
    if not query_variants.issubset(
        title_variants
    ):
        return False

    # Проверяем несовместимые варианты
    # внутри одного семейства.
    for family in VARIANT_FAMILIES:

        query_family = (
            query_variants.intersection(
                family
            )
        )

        title_family = (
            title_variants.intersection(
                family
            )
        )

        if query_family and title_family:

            if query_family != title_family:
                return False

    # Если пользователь не указал вариант,
    # не подставляем ему очевидно другую
    # модификацию товара.
    if not query_variants:

        for family in VARIANT_FAMILIES:

            if title_variants.intersection(
                family
            ):
                return False

    return True


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
    checks = (
        (
            extract_storage(query),
            extract_storage(title),
        ),
        (
            extract_volume(query),
            extract_volume(title),
        ),
        (
            extract_weight(query),
            extract_weight(title),
        ),
        (
            extract_count(query),
            extract_count(title),
        ),
    )

    for query_values, title_values in checks:

        if not values_match(
            query_values,
            title_values,
        ):
            return False

    # Диагональ.
    query_diagonal = extract_diagonal(
        query
    )

    title_diagonal = extract_diagonal(
        title
    )

    if query_diagonal:

        if not title_diagonal:
            return False

        for value in query_diagonal:

            if value not in title_diagonal:
                return False

    # Pampers.
    query_pampers = extract_pampers_size(
        query
    )

    if query_pampers is not None:

        title_pampers = (
            extract_pampers_size(title)
        )

        if title_pampers != query_pampers:
            return False

    return True


# ============================================================
# PRODUCT IDENTITY
# ============================================================

def identity_tokens(text: str):
    tokens = tokenize(text)

    attributes = set()

    extractors = (
        extract_storage,
        extract_volume,
        extract_weight,
        extract_count,
        extract_diagonal,
    )

    for extractor in extractors:

        for value in extractor(text) or []:

            attributes.add(
                str(value)
                .rstrip("0")
                .rstrip(".")
            )

    result = set()

    for token in tokens:

        if token in attributes:
            continue

        # Чистые числа характеристик
        # не являются названием товара.
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
    query_tokens = identity_tokens(
        query
    )

    title_tokens = identity_tokens(
        title
    )

    if not query_tokens:
        return True

    # Каждый существенный токен запроса
    # должен присутствовать в результате.
    return query_tokens.issubset(
        title_tokens
    )


# ============================================================
# MAIN MATCHER
# ============================================================

def is_relevant_result(
    query: str,
    item: dict,
) -> bool:

    title = item.get("title") or ""

    if not title.strip():
        return False

    # --------------------------------------------------------
    # 1. ACCESSORIES
    # --------------------------------------------------------

    if not has_accessory_marker(query):

        if has_accessory_marker(title):
            return False

    # --------------------------------------------------------
    # 2. BRAND
    # --------------------------------------------------------

    query_brands = detect_brands(
        query
    )

    title_brands = detect_brands(
        title
    )

    if query_brands:

        if not query_brands.intersection(
            title_brands
        ):
            return False

    # --------------------------------------------------------
    # 3. ATTRIBUTES
    # --------------------------------------------------------

    if not attributes_match(
        query,
        title,
    ):
        return False

    # --------------------------------------------------------
    # 4. VARIANT
    # --------------------------------------------------------

    if not variants_match(
        query,
        title,
    ):
        return False

    # --------------------------------------------------------
    # 5. PRODUCT IDENTITY
    # --------------------------------------------------------

    if not identity_match(
        query,
        title,
    ):
        return False

    return True
