import hashlib
import os
import re
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")


def normalize_identity(value: Any) -> str:
    text = str(value or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def build_product_key(
    title: str,
    store: str,
    link: str | None,
) -> str:
    """
    Создаёт стабильный идентификатор товара.

    В первую очередь используем ссылку.
    Если ссылки нет — магазин + название.
    """

    if link:
        raw = (
            f"link|"
            f"{normalize_identity(link)}"
        )
    else:
        raw = (
            f"product|"
            f"{normalize_identity(store)}|"
            f"{normalize_identity(title)}"
        )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


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
    Создаёт таблицу истории цен,
    если её ещё нет.
    """

    connection = get_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

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

                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_price_history_product_key
                    ON price_history(product_key);
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


def save_price_and_get_previous(
    title: str,
    store: str,
    link: str | None,
    price: float,
) -> dict[str, Any]:

    product_key = build_product_key(
        title=title,
        store=store,
        link=link,
    )

    connection = get_connection()

    try:
        with connection:
            with connection.cursor(
                cursor_factory=RealDictCursor
            ) as cursor:

                cursor.execute(
                    """
                    SELECT
                        price,
                        observed_at
                    FROM price_history
                    WHERE product_key = %s
                    ORDER BY observed_at DESC
                    LIMIT 1;
                    """,
                    (product_key,),
                )

                previous = cursor.fetchone()

                cursor.execute(
                    """
                    INSERT INTO price_history (
                        product_key,
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
                        %s
                    );
                    """,
                    (
                        product_key,
                        title,
                        store,
                        link,
                        price,
                    ),
                )

                return {
                    "previous_price": (
                        float(previous["price"])
                        if previous
                        else None
                    ),
                    "previous_observed_at": (
                        previous["observed_at"]
                        if previous
                        else None
                    ),
                }

    finally:
        connection.close()


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
