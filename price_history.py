import hashlib
import os
import re
from typing import Any
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_identity(value: Any) -> str:
    text = str(value or "").lower().strip()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def make_hash(value: str) -> str:
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


# ============================================================
# KEYS
# ============================================================

def build_market_key(
    product_query: str,
) -> str:
    """
    Один ключ для одного пользовательского запроса.

    Например:

    iPhone 17 Pro 256 GB

    будет одинаковым для:

    Apple Store
    iStore
    Distiphone
    i4you
    и т.д.
    """

    normalized = normalize_identity(
        product_query
    )

    return make_hash(
        f"market|{normalized}"
    )


def normalize_store_domain(
    link: str | None,
) -> str:
    """Возвращает стабильный домен магазина без пути и параметров."""

    if not link:
        return ""

    raw_link = str(link).strip()

    try:
        parsed = urlparse(raw_link)

        if not parsed.hostname and "://" not in raw_link:
            parsed = urlparse(f"//{raw_link}")

        hostname = (
            parsed.hostname
            or ""
        ).lower().rstrip(".")
    except (TypeError, ValueError):
        return ""

    if hostname.startswith("www."):
        hostname = hostname[4:]

    # Ссылки-посредники Google не идентифицируют продавца.
    if (
        hostname in {"google.com", "google.ru"}
        or hostname.endswith(".google.com")
        or hostname.endswith(".google.ru")
    ):
        return ""

    return hostname


def build_store_key(
    product_query: str,
    store: str,
    link: str | None,
) -> str:
    """Стабильный ключ магазина внутри истории конкретного товара."""

    store_identity = (
        normalize_store_domain(link)
        or normalize_identity(store)
        or "unknown-store"
    )

    return make_hash(
        f"store|{store_identity}"
    )


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    if not DATABASE_URL:

        raise RuntimeError(
            "DATABASE_URL is not configured"
        )

    return psycopg2.connect(
        DATABASE_URL,
        connect_timeout=5,
    )


def init_database() -> None:
    """
    Создаёт/обновляет структуру базы.

    Старые записи не удаляются.
    """

    connection = get_connection()

    try:

        with connection:

            with connection.cursor() as cursor:

                # ------------------------------------------------
                # Existing table
                # ------------------------------------------------

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS price_history (
                        id BIGSERIAL PRIMARY KEY,
                        product_key TEXT NOT NULL,
                        title TEXT NOT NULL,
                        store TEXT,
                        link TEXT,
                        price NUMERIC(14, 2) NOT NULL,
                        observed_at TIMESTAMPTZ
                            NOT NULL DEFAULT NOW()
                    );
                    """
                )


                # ------------------------------------------------
                # New columns
                # ------------------------------------------------

                cursor.execute(
                    """
                    ALTER TABLE price_history
                    ADD COLUMN IF NOT EXISTS
                    market_key TEXT;
                    """
                )

                cursor.execute(
                    """
                    ALTER TABLE price_history
                    ADD COLUMN IF NOT EXISTS
                    store_key TEXT;
                    """
                )


                # ------------------------------------------------
                # Compatibility
                # ------------------------------------------------

                cursor.execute(
                    """
                    UPDATE price_history
                    SET market_key = product_key
                    WHERE market_key IS NULL;
                    """
                )


                cursor.execute(
                    """
                    UPDATE price_history
                    SET store_key = product_key
                    WHERE store_key IS NULL;
                    """
                )


                # ------------------------------------------------
                # Indexes
                # ------------------------------------------------

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_price_history_market_key
                    ON price_history(market_key);
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_price_history_store_key
                    ON price_history(store_key);
                    """
                )

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_price_history_observed_at
                    ON price_history(observed_at);
                    """
                )

    finally:

        connection.close()


# ============================================================
# SAVE + HISTORY
# ============================================================

def save_price_and_get_history(
    product_query: str,
    title: str,
    store: str,
    link: str | None,
    price: float,
) -> dict[str, Any]:

    market_key = build_market_key(
        product_query
    )

    store_key = build_store_key(
        product_query,
        store,
        link,
    )

    normalized_store = normalize_identity(
        store
    )

    connection = get_connection()

    try:

        with connection:

            with connection.cursor(
                cursor_factory=RealDictCursor
            ) as cursor:

                # =================================================
                # STORE HISTORY
                # =================================================

                cursor.execute(
                    """
                    SELECT
                        price,
                        observed_at
                    FROM price_history
                    WHERE market_key = %s
                      AND (
                          store_key = %s
                          OR LOWER(
                              TRIM(
                                  COALESCE(store, '')
                              )
                          ) = %s
                      )
                    ORDER BY observed_at DESC
                    LIMIT 1;
                    """,
                    (
                        market_key,
                        store_key,
                        normalized_store,
                    ),
                )

                store_previous = (
                    cursor.fetchone()
                )


                # =================================================
                # MARKET HISTORY
                # =================================================

                cursor.execute(
                    """
                    SELECT
                        MIN(price) AS min_price,
                        MAX(price) AS max_price,
                        COUNT(*) AS observations
                    FROM price_history
                    WHERE market_key = %s;
                    """,
                    (
                        market_key,
                    ),
                )

                market_stats = (
                    cursor.fetchone()
                )


                previous_market_min = (
                    float(
                        market_stats["min_price"]
                    )
                    if (
                        market_stats
                        and market_stats["min_price"]
                        is not None
                    )
                    else None
                )


                previous_market_max = (
                    float(
                        market_stats["max_price"]
                    )
                    if (
                        market_stats
                        and market_stats["max_price"]
                        is not None
                    )
                    else None
                )


                observations = int(
                    market_stats["observations"]
                    or 0
                )


                # =================================================
                # INSERT CURRENT OBSERVATION
                # =================================================

                cursor.execute(
                    """
                    INSERT INTO price_history (
                        product_key,
                        market_key,
                        store_key,
                        title,
                        store,
                        link,
                        price
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s
                    );
                    """,
                    (
                        market_key,
                        market_key,
                        store_key,
                        title,
                        store,
                        link,
                        price,
                    ),
                )


                # =================================================
                # RETURN HISTORY
                # =================================================

                return {

                    "market_key":
                        market_key,

                    "store_key":
                        store_key,

                    "store_previous_price": (

                        float(
                            store_previous["price"]
                        )

                        if store_previous

                        else None

                    ),

                    "store_previous_observed_at": (

                        store_previous[
                            "observed_at"
                        ]

                        if store_previous

                        else None

                    ),

                    "market_min_price": (
                        previous_market_min
                    ),

                    "market_max_price": (
                        previous_market_max
                    ),

                    "market_observations": (
                        observations
                    ),

                }

    finally:

        connection.close()


# ============================================================
# PRICE CHANGE
# ============================================================

def calculate_price_change(
    current_price: float,
    previous_price: float | None,
) -> float | None:

    if previous_price is None:
        return None

    if previous_price <= 0:
        return None

    return (
        (
            current_price
            - previous_price
        )
        / previous_price
        * 100
    )


def calculate_market_difference(
    current_price: float,
    previous_min_price: float | None,
) -> float | None:

    if previous_min_price is None:
        return None

    if previous_min_price <= 0:
        return None

    return (
        (
            current_price
            - previous_min_price
        )
        / previous_min_price
        * 100
    )
