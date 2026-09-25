import re


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Приводит текст к единому виду.
    """

    text = str(text or "").lower()

    text = text.replace(
        "ё",
        "е",
    )

    text = re.sub(
        r"\bл\b",
        "l",
        text,
    )

    grocery_replacements = (
        (
            r"\bфарш(?:а|у|ем|е)?\b",
            "фарш",
        ),
        (
            r"\bговядин(?:а|ы|е|у|ой)\b",
            "говяжий",
        ),
        (
            r"\bговяж(?:ий|ья|ье|ьи|его|ему|им|их|ую|ей)\b",
            "говяжий",
        ),
        (
            r"\bкуриц(?:а|ы|е|у|ей)\b",
            "куриный",
        ),
        (
            r"\bцыпл(?:енок|енка|енку|ята|ят|ятами)\b",
            "куриный",
        ),
        (
            r"\bкурин(?:ый|ая|ое|ые|ого|ому|ым|ых|ую|ой)\b",
            "куриный",
        ),
        (
            r"\bиндейк(?:а|и|е|у|ой)\b",
            "индюшиный",
        ),
        (
            r"\bиндюш(?:иный|иная|иное|иные|иного|иную|иной)\b",
            "индюшиный",
        ),
        (
            r"\bсвинин(?:а|ы|е|у|ой)\b",
            "свиной",
        ),
        (
            r"\bсвин(?:ой|ая|ое|ые|ого|ому|ым|ых|ую)\b",
            "свиной",
        ),
    )

    for pattern, replacement in grocery_replacements:
        text = re.sub(
            pattern,
            replacement,
            text,
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
        "килограммов": "kg",

        "мл": "ml",
        "миллилитров": "ml",
        "миллилитра": "ml",

        "литров": "l",
        "литра": "l",
        "литры": "l",
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

    # Decimal comma: 0,45 л -> 0.45 л
    text = re.sub(
        r"(?<=\d),(?=\d)",
        ".",
        text,
    )

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
# MULTIPACK
# ============================================================

def extract_pack_count(
    text: str,
):
    normalized = normalize_text(
        text
    )

    patterns = (
        r"\b(\d+)\s*[xх]\s*\d",
        r"\b\d+(?:\.\d+)?\s*(?:ml|l|kg|g)\s*[xх]\s*(\d+)\b",
        (
            r"\b(?:упаковка|набор|pack)\s*"
            r"(?:из|of)?\s*(\d+)\b"
        ),
        (
            r"\b(\d+)\s*"
            r"(?:бутылок|бутылки|банок|банки|"
            r"пачек|пачки|упаковок|упаковки)\b"
        ),
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

    return None


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

        # ----------------------------------------------------
        # Число + характеристика
        #
        # 256 GB
        # 1 KG
        # 500 ML
        # ----------------------------------------------------

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
            # часть модели.
            result.append(
                token
            )

            index += 1

            continue

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

        if token in STOP_WORDS:

            index += 1

            continue

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
# DEVICE MODEL EXTRACTION
# ============================================================

DEVICE_FAMILIES = {
    "iphone",
    "ipad",

    "galaxy",
    "samsung",

    "pixel",

    "redmi",
    "poco",

    "xiaomi",

    "oneplus",

    "honor",

    "huawei",

    "oppo",

    "realme",
}


DEVICE_VARIANTS = {
    "pro",
    "pro max",
    "plus",
    "ultra",
    "mini",
    "air",
    "lite",
    "fe",
    "max",
    "fold",
    "flip",
}


def extract_device_signature(
    text: str,
):
    """
    Извлекает именно модель устройства.

    Ключевой момент:

    iPhone 17 Pro Case
    ->
    iPhone / 17 / Pro

    iPhone 17 Case CamShield Pro
    ->
    iPhone / 17 / None

    Поэтому Pro в названии самого чехла
    не будет принят за Pro телефона.
    """

    normalized = normalize_text(
        text
    )

    tokens = normalized.split()

    for index, token in enumerate(tokens):

        if token not in DEVICE_FAMILIES:

            continue

        # ----------------------------------------------------
        # Ищем номер модели сразу после семейства.
        # ----------------------------------------------------

        model_number = None
        model_index = None

        for offset in range(
            1,
            4,
        ):

            position = index + offset

            if position >= len(tokens):
                break

            candidate = tokens[position]

            # Например:
            # iPhone 17
            # Galaxy S25
            # Pixel 9

            if re.fullmatch(
                r"[a-z]?\d+[a-z]?",
                candidate,
            ):

                model_number = candidate
                model_index = position

                break

        if model_number is None:

            # Для моделей вроде:
            # iPhone SE
            # Galaxy Fold

            continue

        # ----------------------------------------------------
        # Вариант должен идти НЕПОСРЕДСТВЕННО
        # после номера модели.
        #
        # iPhone 17 Pro
        #             ^
        #
        # Но:
        #
        # iPhone 17 Case CamShield Pro
        #                              ^
        #
        # этот Pro уже не относится к телефону.
        # ----------------------------------------------------

        variant = None

        if (
            model_index + 2
            < len(tokens)
        ):

            first = tokens[
                model_index + 1
            ]

            second = tokens[
                model_index + 2
            ]

            if (
                first == "pro"
                and second == "max"
            ):

                variant = "pro max"

            elif first in DEVICE_VARIANTS:

                variant = first

        if variant is None:

            if (
                model_index + 1
                < len(tokens)
            ):

                next_token = tokens[
                    model_index + 1
                ]

                if (
                    next_token
                    in DEVICE_VARIANTS
                ):

                    variant = next_token

        return (
            token,
            model_number,
            variant,
        )

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
    # Все основные элементы модели должны присутствовать.
    # --------------------------------------------------------

    if not query_tokens.issubset(
        title_tokens
    ):

        return False

    # ========================================================
    # ОБЫЧНЫЙ ТОВАР
    # ========================================================

    if not accessory_mode:

        query_signature = (
            extract_device_signature(
                query
            )
        )

        title_signature = (
            extract_device_signature(
                title
            )
        )

        if query_signature:

            if not title_signature:

                return False

            if (
                query_signature[0]
                != title_signature[0]
            ):

                return False

            if (
                query_signature[1]
                != title_signature[1]
            ):

                return False

            if (
                query_signature[2]
                != title_signature[2]
            ):

                return False

        return True

    # ========================================================
    # АКСЕССУАР
    # ========================================================

    query_signature = (
        extract_device_signature(
            query
        )
    )

    title_signature = (
        extract_device_signature(
            title
        )
    )

    # --------------------------------------------------------
    # Если в запросе есть понятная модель
    # устройства, название аксессуара тоже
    # должно содержать эту модель.
    # --------------------------------------------------------

    if query_signature:

        if not title_signature:

            return False

        # ----------------------------------------------------
        # Семейство устройства
        # ----------------------------------------------------

        if (
            query_signature[0]
            != title_signature[0]
        ):

            return False

        # ----------------------------------------------------
        # Поколение / номер
        # ----------------------------------------------------

        if (
            query_signature[1]
            != title_signature[1]
        ):

            return False

        # ----------------------------------------------------
        # Вариант устройства
        #
        # ВАЖНО:
        #
        # iPhone 17 Pro
        # !=
        # iPhone 17
        #
        # и
        #
        # iPhone 17 Pro
        # !=
        # iPhone 17 Pro Max
        # ----------------------------------------------------

        query_variant = (
            query_signature[2]
        )

        title_variant = (
            title_signature[2]
        )

        if query_variant != title_variant:

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

    # --------------------------------------------------------
    # Для аксессуара характеристики самого
    # устройства игнорируем.
    #
    # iPhone 17 Pro 256 GB чехол
    #
    # совместим с:
    #
    # iPhone 17 Pro Case
    # --------------------------------------------------------

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
    # Multipack
    # --------------------------------------------------------

    query_pack_count = extract_pack_count(
        query
    )

    if query_pack_count is not None:

        title_pack_count = extract_pack_count(
            title
        )

        if title_pack_count != query_pack_count:

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

        if (
            title_pampers
            != query_pampers
        ):

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

    accessory_mode = (
        has_accessory_marker(
            normalized_query
        )
    )

    title_is_accessory = (
        has_accessory_marker(
            normalized_title
        )
    )

    # --------------------------------------------------------
    # Если ищем аксессуар —
    # результат должен быть аксессуаром.
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
