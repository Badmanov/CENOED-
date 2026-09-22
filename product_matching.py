import re


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Приводит текст к нормальному виду.
    """

    text = str(text or "").lower()

    text = text.replace(
        "ё",
        "е",
    )

    replacements = {
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
        r"[^\w\s.+&/-]",
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
    "cases",
    "cover",
    "covers",

    "стекло",
    "glass",

    "пленка",
    "пленку",
    "film",

    "защитное",
    "защитная",

    "кабель",
    "cable",

    "зарядка",
    "зарядное",
    "зарядник",
    "charger",

    "адаптер",
    "adapter",

    "переходник",

    "наушники",
    "headphones",
    "гарнитура",
    "earbuds",

    "держатель",
    "holder",

    "крепление",

    "ремешок",
    "strap",

    "бампер",
    "накладка",

    "powerbank",
    "пауэрбанк",

    "штатив",

    "сумка",
    "bag",

    "аксессуар",
    "аксессуары",
    "accessory",
    "accessories",
}


def has_accessory_marker(
    text: str,
) -> bool:

    normalized = normalize_text(
        text
    )

    tokens = set(
        normalized.split()
    )

    return bool(
        tokens.intersection(
            ACCESSORY_WORDS
        )
    )


# ============================================================
# STORAGE
# ============================================================

def extract_storage(
    text: str,
):
    """
    256 GB -> 256
    512 GB -> 512
    1 TB -> 1024
    """

    normalized = normalize_text(
        text
    )

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(gb|tb)\b",
        normalized,
    )

    if not matches:
        return None

    result = []

    for value, unit in matches:

        number = float(
            value.replace(
                ",",
                ".",
            )
        )

        if unit == "tb":

            number *= 1024

        result.append(
            int(number)
        )

    return result


# ============================================================
# VOLUME
# ============================================================

def extract_volume(
    text: str,
):

    normalized = normalize_text(
        text
    )

    matches = re.findall(
        r"\b(\d+(?:[.,]\d+)?)\s*(ml|l)\b",
        normalized,
    )

    if not matches:
        return None

    result = []

    for value, unit in matches:

        number = float(
            value.replace(
                ",",
                ".",
            )
        )

        if unit == "l":

            number *= 1000

        result.append(
            round(
                number,
                2,
            )
        )

    return result


# ============================================================
# WEIGHT
# ============================================================

def extract_weight(
    text: str,
):

    normalized = normalize_text(
        text
    )

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
            value.replace(
                ",",
                ".",
            )
        )

        if unit == "kg":

            number *= 1000

        result.append(
            round(
                number,
                2,
            )
        )

    return result


# ============================================================
# COUNT
# ============================================================

def extract_count(
    text: str,
):

    normalized = normalize_text(
        text
    )

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


# ============================================================
# PAMPERS SIZE
# ============================================================

def extract_pampers_size(
    text: str,
):

    normalized = normalize_text(
        text
    )

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

        r"\bpampers\s+"
        r"(?:premium\s+care\s+)?"
        r"([1-7])\b",

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
}


# ============================================================
# TOKENIZATION
# ============================================================

def tokens_without_attributes(
    text: str,
    accessory_mode: bool = False,
):

    normalized = normalize_text(
        text
    )

    tokens = normalized.split()

    result = []

    index = 0

    while index < len(tokens):

        token = tokens[index]

        # --------------------------------------------
        # Число + единица измерения
        #
        # 256 GB
        # 1 KG
        # 500 ML
        #
        # Для идентичности пропускаем.
        # --------------------------------------------

        if re.fullmatch(
            r"\d+(?:[.,]\d+)?",
            token,
        ):

            if (
                index + 1 < len(tokens)
                and tokens[index + 1]
                in {
                    "gb",
                    "tb",
                    "kg",
                    "g",
                    "ml",
                    "l",
                    "шт",
                    "pcs",
                    "pieces",
                }
            ):

                index += 2

                continue

            # Обычное число —
            # это часть модели.
            result.append(
                token
            )

            index += 1

            continue

        # --------------------------------------------
        # Единица измерения
        # --------------------------------------------

        if token in {
            "gb",
            "tb",
            "kg",
            "g",
            "ml",
            "l",
            "шт",
            "pcs",
            "pieces",
        }:

            index += 1

            continue

        # --------------------------------------------
        # Стоп-слова
        # --------------------------------------------

        if token in STOP_WORDS:

            index += 1

            continue

        # --------------------------------------------
        # Слова аксессуара
        # --------------------------------------------

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

    return set(
        result
    )


# ============================================================
# MODEL VARIANT
# ============================================================

def get_variant(
    text: str,
):
    """
    Возвращает модификацию модели.

    Pro Max
    Pro
    Plus
    Ultra
    Mini
    Air
    и т.д.
    """

    normalized = normalize_text(
        text
    )

    if re.search(
        r"\bpro\s+max\b",
        normalized,
    ):

        return "pro max"

    variants = (
        "pro",
        "plus",
        "ultra",
        "mini",
        "air",
        "lite",
        "fe",
        "max",
        "fold",
        "flip",
    )

    for variant in variants:

        if re.search(
            rf"\b{re.escape(variant)}\b",
            normalized,
        ):

            return variant

    return None


# ============================================================
# MODEL IDENTITY
# ============================================================

def model_identity_matches(
    query: str,
    title: str,
    accessory_mode: bool,
):

    query_tokens = (
        tokens_without_attributes(
            query,
            accessory_mode=True,
        )
    )

    title_tokens = (
        tokens_without_attributes(
            title,
            accessory_mode=True,
        )
    )

    if not query_tokens:

        return False

    # --------------------------------------------------------
    # Все ключевые слова модели должны присутствовать.
    #
    # iPhone 17 Pro
    #
    # должно найти:
    #
    # iPhone 17 Pro Case
    #
    # но не:
    #
    # iPhone 16 Pro Case
    # iPhone 17 Pro Max Case
    # --------------------------------------------------------

    if not query_tokens.issubset(
        title_tokens
    ):

        return False

    # --------------------------------------------------------
    # Отдельно проверяем вариант.
    # --------------------------------------------------------

    query_variant = get_variant(
        query
    )

    title_variant = get_variant(
        title
    )

    if query_variant:

        if title_variant != query_variant:

            return False

    return True


# ============================================================
# ATTRIBUTE MATCHING
# ============================================================

def attributes_match(
    query: str,
    title: str,
    accessory_mode: bool,
):

    # Для аксессуаров характеристики
    # самого устройства не проверяем.
    #
    # Например:
    #
    # iPhone 17 Pro 256 GB чехол
    #
    # и
    #
    # чехол iPhone 17 Pro
    #
    # считаются совместимыми.

    if accessory_mode:

        return True

    # --------------------------------------------------------
    # Storage
    # --------------------------------------------------------

    query_storage = extract_storage(
        query
    )

    if query_storage:

        title_storage = extract_storage(
            title
        )

        if not title_storage:

            return False

        if not all(
            value in title_storage
            for value in query_storage
        ):

            return False

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------

    query_volume = extract_volume(
        query
    )

    if query_volume:

        title_volume = extract_volume(
            title
        )

        if not title_volume:

            return False

        if not all(
            value in title_volume
            for value in query_volume
        ):

            return False

    # --------------------------------------------------------
    # Weight
    # --------------------------------------------------------

    query_weight = extract_weight(
        query
    )

    if query_weight:

        title_weight = extract_weight(
            title
        )

        if not title_weight:

            return False

        if not all(
            value in title_weight
            for value in query_weight
        ):

            return False

    # --------------------------------------------------------
    # Count
    # --------------------------------------------------------

    query_count = extract_count(
        query
    )

    if query_count:

        title_count = extract_count(
            title
        )

        if not title_count:

            return False

        if not all(
            value in title_count
            for value in query_count
        ):

            return False

    # --------------------------------------------------------
    # Pampers
    # --------------------------------------------------------

    query_pampers = (
        extract_pampers_size(
            query
        )
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
    # ACCESSORY MODE
    # ========================================================

    accessory_mode = has_accessory_marker(
        normalized_query
    )

    title_is_accessory = (
        has_accessory_marker(
            normalized_title
        )
    )

    # --------------------------------------------------------
    # Если ищем аксессуар —
    # результат обязан быть аксессуаром.
    # --------------------------------------------------------

    if accessory_mode:

        if not title_is_accessory:

            return False

    # --------------------------------------------------------
    # Если ищем сам товар —
    # аксессуары исключаем.
    # --------------------------------------------------------

    else:

        if title_is_accessory:

            return False

    # ========================================================
    # MODEL
    # ========================================================

    if not model_identity_matches(
        normalized_query,
        normalized_title,
        accessory_mode,
    ):

        return False

    # ========================================================
    # ATTRIBUTES
    # ========================================================

    if not attributes_match(
        normalized_query,
        normalized_title,
        accessory_mode,
    ):

        return False

    return True
