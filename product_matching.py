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

    # iPhone17 -> iPhone 17
    text = re.sub(
        r"([a-zа-я])(\d)",
        r"\1 \2",
        text,
    )

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
    "защитная",
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
        tokens.intersection(
            ACCESSORY_WORDS
        )
    )


# ============================================================
# ATTRIBUTE EXTRACTION
# ============================================================

def extract_storage(text: str):
    """
    Память в GB.

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

        result.append(
            int(number)
        )

    return result or None


def extract_volume(text: str):
    """
    Объём в миллилитрах.

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
    Вес в граммах.

    1 kg -> 1000
    500 g -> 500
    """

    normalized = normalize_text(text)

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
    Поддерживает:

    6.7"
    6.7 inch
    6.7 in
    """

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

    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(?:inch|in)\b",
        normalized,
    )

    if not matches:
        return None

    return [
        float(
            value.replace(",", ".")
        )
        for value in matches
    ]


# ============================================================
# PAMPERS
# ============================================================

def extract_pampers_size(text: str):
    normalized = normalize_text(text)

    tokens = set(
        normalized.split()
    )

    if not any(
        word in tokens
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

    if "newborn" in tokens:
        return 0

    return None


# ============================================================
# STOP WORDS
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

            if " " in alias_normalized:

                if alias_normalized in normalized:
                    found.add(canonical)
                    break

            else:

                if alias_normalized in tokens:
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

    # Сначала длинная комбинация.
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

    # Pro Max — самостоятельный вариант.
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

    # Если пользователь указал конкретную
    # модификацию — она обязана совпадать.
    if not query_variants.issubset(
        title_variants
    ):
        return False

    # Проверяем несовместимые варианты.
    for family in VARIANT_FAMILIES:

        query_family = (
            query_variants & family
        )

        title_family = (
            title_variants & family
        )

        if query_family and title_family:

            if query_family != title_family:
                return False

    # Если вариант не указан,
    # не подставляем другую очевидную
    # модификацию.
    if not query_variants:

        for family in VARIANT_FAMILIES:

            if title_variants & family:
                return False

    return True


# ============================================================
# ACCESSORY QUERY
# ============================================================

def accessory_tokens(text: str):
    normalized = normalize_text(text)

    return set(
        normalized.split()
    ).intersection(
        ACCESSORY_WORDS
    )


def remove_accessory_words(
    tokens: set[str],
):
    return {
        token
        for token in tokens
        if token not in ACCESSORY_WORDS
    }


# ============================================================
# IDENTITY TOKENS
# ============================================================

ATTRIBUTE_UNITS = {
    "gb",
    "tb",
    "kg",
    "g",
    "ml",
    "l",
    "inch",
    "in",
    "шт",
    "pcs",
    "pieces",
}


def identity_tokens(
    text: str,
    accessory_mode: bool = False,
):
    tokens = tokenize(text)

    result = []

    index = 0

    while index < len(tokens):

        token = tokens[index]

        # ----------------------------------------------------
        # Число + единица измерения.
        # ----------------------------------------------------

        if re.fullmatch(
            r"\d+(?:[.,]\d+)?",
            token,
        ):

            if (
                index + 1 < len(tokens)
                and tokens[index + 1]
                in ATTRIBUTE_UNITS
            ):

                # Для аксессуара и обычного товара
                # характеристики не являются частью
                # текстовой идентичности.
                index += 2
                continue

            # Обычное число без единицы —
            # это поколение/номер модели.
            result.append(token)

            index += 1
            continue

        # ----------------------------------------------------
        # Единица измерения.
        # ----------------------------------------------------

        if token in ATTRIBUTE_UNITS:

            index += 1
            continue

        result.append(token)

        index += 1

    result_set = set(result)

    # В запросе аксессуара слова "чехол",
    # "case" и т.д. описывают тип аксессуара,
    # а не модель телефона.
    if accessory_mode:

        result_set = remove_accessory_words(
            result_set
        )

    return result_set


# ============================================================
# ACCESSORY IDENTITY
# ============================================================

def accessory_identity_match(
    query: str,
    title: str,
):
    """
    Для аксессуаров:

    iPhone 17 Pro 256 GB чехол

    сравнивается с:

    Чехол для iPhone 17 Pro

    но не требует 256 GB.

    При этом модель и поколение обязательны.
    """

    query_tokens = identity_tokens(
        query,
        accessory_mode=True,
    )

    title_tokens = identity_tokens(
        title,
        accessory_mode=True,
    )

    if not query_tokens:
        return False

    return query_tokens.issubset(
        title_tokens
    )


# ============================================================
# REGULAR PRODUCT IDENTITY
# ============================================================

def regular_identity_match(
    query: str,
    title: str,
):
    query_tokens = identity_tokens(
        query,
        accessory_mode=False,
    )

    title_tokens = identity_tokens(
        title,
        accessory_mode=False,
    )

    if not query_tokens:
        return True

    return query_tokens.issubset(
        title_tokens
    )


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
    accessory_mode: bool = False,
):
    # --------------------------------------------------------
    # Для аксессуаров характеристики самого устройства
    # вроде 256 GB не являются обязательными.
    # --------------------------------------------------------

    if not accessory_mode:

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

    # --------------------------------------------------------
    # Pampers
    # --------------------------------------------------------

    query_pampers = extract_pampers_size(
        query
    )

    if query_pampers is not None:

        title_pampers = (
            extract_pampers_size(
                title
            )
        )

        if title_pampers != query_pampers:
            return False

    return True


# ============================================================
# MAIN MATCHER
# ============================================================

def is_relevant_result(
    query: str,
    item: dict,
) -> bool:

    title = item.get(
        "title"
    ) or ""

    if not title.strip():
        return False

    # ========================================================
    # MODE
    # ========================================================

    accessory_mode = has_accessory_marker(
        query
    )

    title_is_accessory = (
        has_accessory_marker(title)
    )

    # ========================================================
    # ACCESSORY / PRODUCT TYPE
    # ========================================================

    # Если пользователь ищет сам товар,
    # аксессуары отбрасываем.
    if not accessory_mode:

        if title_is_accessory:
            return False

    # Если пользователь ищет аксессуар,
    # сам телефон/товар не подходит.
    else:

        if not title_is_accessory:
            return False

    # ========================================================
    # BRAND
    # ========================================================

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

    # ========================================================
    # VARIANTS
    # ========================================================

    if not variants_match(
        query,
        title,
    ):
        return False

    # ========================================================
    # ATTRIBUTES
    # ========================================================

    if not attributes_match(
        query,
        title,
        accessory_mode=accessory_mode,
    ):
        return False

    # ========================================================
    # IDENTITY
    # ========================================================

    if accessory_mode:

        if not accessory_identity_match(
            query,
            title,
        ):
            return False

    else:

        if not regular_identity_match(
            query,
            title,
        ):
            return False

    return True
