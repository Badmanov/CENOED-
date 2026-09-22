import re


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Приводит текст к единому виду.

    Примеры:

    256GB -> 256 GB
    iPhone17 -> iPhone 17
    ё -> е
    """

    text = str(text or "").lower().replace(
        "ё",
        "е",
    )

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

        text = text.replace(
            old,
            new,
        )

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

    # Убираем лишнюю пунктуацию.
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
    # Cases
    "чехол",
    "чехлы",
    "case",
    "cases",
    "cover",
    "covers",

    # Glass / film
    "стекло",
    "glass",
    "защитное",
    "защитная",
    "пленка",
    "пленку",
    "film",

    # Cable / charging
    "кабель",
    "cable",
    "charger",
    "зарядка",
    "зарядное",
    "зарядник",

    # Adapters
    "адаптер",
    "adapter",
    "переходник",

    # Audio
    "наушники",
    "headphones",
    "гарнитура",
    "earbuds",

    # Holders
    "держатель",
    "holder",
    "крепление",
    "крепеж",

    # Straps
    "ремешок",
    "strap",

    # Cases / bumpers
    "бампер",
    "накладка",

    # Power
    "powerbank",
    "пауэрбанк",

    # Tripods
    "штатив",

    # Bags
    "сумка",
    "bag",

    # Generic
    "аксессуар",
    "аксессуары",
    "accessory",
    "accessories",
}


def has_accessory_marker(
    text: str,
) -> bool:

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
    256 GB -> 256
    512 GB -> 512
    1 TB -> 1024
    """

    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(gb|tb)\b",
        normalized,
    )

    if not matches:
        return None

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

    return result


def extract_volume(text: str):
    """
    1.5 l -> 1500
    500 ml -> 500
    """

    normalized = normalize_text(text)

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(ml|l)\b",
        normalized,
    )

    if not matches:
        return None

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

    return result


def extract_weight(text: str):
    """
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

    if not matches:
        return None

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

    return result


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

    patterns = (
        r"\bpremium\s+care\s+([1-7])\b",
        r"\bpampers\s+(?:premium\s+care\s+)?([1-7])\b",
        r"\bразмер\s*([1-7])\b",
        r"\bsize\s*([1-7])\b",
    )

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
    "от",
    "до",

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


# ============================================================
# BRAND ALIASES
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

                    found.add(
                        canonical
                    )

                    break

            else:

                if alias_normalized in tokens:

                    found.add(
                        canonical
                    )

                    break

    return found


# ============================================================
# MODEL / VARIANT
# ============================================================

def extract_variants(text: str):

    normalized = normalize_text(text)

    found = set()

    # ВАЖНО:
    # сначала проверяем PRO MAX,
    # чтобы он не превращался в PRO.

    if re.search(
        r"\bpro\s+max\b",
        normalized,
    ):

        found.add(
            "pro max"
        )

    elif re.search(
        r"\bpro\b",
        normalized,
    ):

        found.add(
            "pro"
        )

    for variant in (
        "plus",
        "ultra",
        "air",
        "mini",
        "fe",
        "lite",
        "zero",
        "light",
        "diet",
        "classic",
        "fold",
        "flip",
        "max",
    ):

        if re.search(
            rf"(?<!\w){re.escape(variant)}(?!\w)",
            normalized,
        ):

            found.add(
                variant
            )

    return found


def variants_match(
    query: str,
    title: str,
) -> bool:

    query_variants = extract_variants(
        query
    )

    title_variants = extract_variants(
        title
    )

    # --------------------------------------------------------
    # Если пользователь указал конкретный вариант,
    # он обязан присутствовать в результате.
    # --------------------------------------------------------

    if query_variants:

        for variant in query_variants:

            if variant not in title_variants:

                return False

    # --------------------------------------------------------
    # PRO != PRO MAX
    # --------------------------------------------------------

    if "pro" in query_variants:

        if "pro max" in title_variants:

            return False

    if "pro max" in query_variants:

        if "pro" not in title_variants:

            return False

    # --------------------------------------------------------
    # Если пользователь не указал вариант,
    # не подставляем другой вариант.
    # --------------------------------------------------------

    if not query_variants:

        incompatible = {
            "pro",
            "pro max",
            "plus",
            "ultra",
            "air",
            "mini",
            "fe",
            "lite",
            "fold",
            "flip",
        }

        if title_variants.intersection(
            incompatible
        ):

            return False

    return True


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

    normalized = normalize_text(text)

    tokens = [
        token
        for token in normalized.split()
        if token not in STOP_WORDS
        and len(token) >= 2
    ]

    result = []

    index = 0

    while index < len(tokens):

        token = tokens[index]

        # ----------------------------------------------------
        # Число + единица.
        #
        # 256 GB
        # 1 kg
        # 500 ml
        #
        # не являются текстовой идентичностью.
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

                index += 2

                continue

            # Обычное число:
            # 17, 16, 15 и т.д.
            #
            # Это часть модели.

            result.append(
                token
            )

            index += 1

            continue

        # ----------------------------------------------------
        # Единица измерения.
        # ----------------------------------------------------

        if token in ATTRIBUTE_UNITS:

            index += 1

            continue

        # ----------------------------------------------------
        # Аксессуарные слова не являются моделью устройства.
        # ----------------------------------------------------

        if (
            accessory_mode
            and token in ACCESSORY_WORDS
        ):

            index += 1

            continue

        result.append(
            token
        )

        index += 1

    return set(result)


# ============================================================
# ACCESSORY IDENTITY
# ============================================================

def accessory_identity_match(
    query: str,
    title: str,
) -> bool:

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

    # Каждый обязательный элемент модели
    # должен присутствовать в названии результата.

    if not query_tokens.issubset(
        title_tokens
    ):

        return False

    return True


# ============================================================
# REGULAR PRODUCT IDENTITY
# ============================================================

def regular_identity_match(
    query: str,
    title: str,
) -> bool:

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

    if not query_tokens.issubset(
        title_tokens
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
    accessory_mode: bool = False,
) -> bool:

    # --------------------------------------------------------
    # Для обычного товара проверяем характеристики.
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

        # ----------------------------------------------------
        # Диагональ
        # ----------------------------------------------------

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

        title_pampers = extract_pampers_size(
            title
        )

        if title_pampers != query_pampers:

            return False

    return True


# ============================================================
# ACCESSORY TYPE DETECTION
# ============================================================

def title_is_probably_accessory(
    title: str,
) -> bool:

    return has_accessory_marker(
        title
    )


# ============================================================
# MAIN MATCHER
# ============================================================

def is_relevant_result(
    query: str,
    item: dict,
) -> bool:

    title = (
        item.get("title")
        or ""
    ).strip()

    if not title:

        return False

    normalized_query = normalize_text(
        query
    )

    normalized_title = normalize_text(
        title
    )

    # ========================================================
    # MODE
    # ========================================================

    accessory_mode = has_accessory_marker(
        normalized_query
    )

    title_is_accessory = (
        title_is_probably_accessory(
            normalized_title
        )
    )

    # ========================================================
    # PRODUCT TYPE
    # ========================================================

    # --------------------------------------------------------
    # Пользователь ищет сам товар.
    #
    # Чехол / стекло / кабель и т.д.
    # не должны попадать в выдачу.
    # --------------------------------------------------------

    if not accessory_mode:

        if title_is_accessory:

            return False

    # --------------------------------------------------------
    # Пользователь ищет аксессуар.
    #
    # Сам телефон не подходит.
    # --------------------------------------------------------

    else:

        if not title_is_accessory:

            return False

    # ========================================================
    # BRAND
    # ========================================================

    query_brands = detect_brands(
        normalized_query
    )

    title_brands = detect_brands(
        normalized_title
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
        normalized_query,
        normalized_title,
    ):

        return False

    # ========================================================
    # ATTRIBUTES
    # ========================================================

    if not attributes_match(
        normalized_query,
        normalized_title,
        accessory_mode=accessory_mode,
    ):

        return False

    # ========================================================
    # IDENTITY
    # ========================================================

    if accessory_mode:

        if not accessory_identity_match(
            normalized_query,
            normalized_title,
        ):

            return False

    else:

        if not regular_identity_match(
            normalized_query,
            normalized_title,
        ):

            return False

    return True
