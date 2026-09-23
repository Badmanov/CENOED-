import os
import secrets
from decimal import Decimal
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor


DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg2.connect(DATABASE_URL, connect_timeout=5)


def init_subscriptions() -> None:
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS price_subscriptions (
                        id BIGSERIAL PRIMARY KEY,
                        telegram_user_id BIGINT NOT NULL,
                        chat_id BIGINT NOT NULL,
                        product_query TEXT NOT NULL,
                        search_query TEXT NOT NULL,
                        baseline_price NUMERIC(14, 2) NOT NULL,
                        last_seen_price NUMERIC(14, 2) NOT NULL,
                        last_notified_price NUMERIC(14, 2),
                        active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        checked_at TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        UNIQUE (telegram_user_id, product_query)
                    );
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_price_subscriptions_active
                    ON price_subscriptions(active, checked_at);
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS subscription_candidates (
                        token TEXT PRIMARY KEY,
                        telegram_user_id BIGINT NOT NULL,
                        chat_id BIGINT NOT NULL,
                        product_query TEXT NOT NULL,
                        search_query TEXT NOT NULL,
                        current_price NUMERIC(14, 2) NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_subscription_candidates_created_at
                    ON subscription_candidates(created_at);
                    """
                )
    finally:
        connection.close()


def create_watch_candidate(
    telegram_user_id: int,
    chat_id: int,
    product_query: str,
    search_query: str,
    current_price: float,
) -> str:
    token = secrets.token_urlsafe(8)
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM subscription_candidates
                    WHERE created_at < NOW() - INTERVAL '24 hours';
                    """
                )
                cursor.execute(
                    """
                    INSERT INTO subscription_candidates (
                        token,
                        telegram_user_id,
                        chat_id,
                        product_query,
                        search_query,
                        current_price
                    )
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    (
                        token,
                        telegram_user_id,
                        chat_id,
                        product_query,
                        search_query,
                        current_price,
                    ),
                )
        return token
    finally:
        connection.close()


def activate_subscription(
    token: str,
    telegram_user_id: int,
) -> dict[str, Any] | None:
    connection = get_connection()
    try:
        with connection:
            with connection.cursor(
                cursor_factory=RealDictCursor
            ) as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM subscription_candidates
                    WHERE token = %s
                      AND telegram_user_id = %s
                      AND created_at >= NOW() - INTERVAL '24 hours';
                    """,
                    (token, telegram_user_id),
                )
                candidate = cursor.fetchone()
                if candidate is None:
                    return None

                cursor.execute(
                    """
                    INSERT INTO price_subscriptions (
                        telegram_user_id,
                        chat_id,
                        product_query,
                        search_query,
                        baseline_price,
                        last_seen_price,
                        active,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW())
                    ON CONFLICT (telegram_user_id, product_query)
                    DO UPDATE SET
                        chat_id = EXCLUDED.chat_id,
                        search_query = EXCLUDED.search_query,
                        baseline_price = EXCLUDED.baseline_price,
                        last_seen_price = EXCLUDED.last_seen_price,
                        last_notified_price = NULL,
                        active = TRUE,
                        checked_at = NULL,
                        updated_at = NOW()
                    RETURNING *;
                    """,
                    (
                        candidate["telegram_user_id"],
                        candidate["chat_id"],
                        candidate["product_query"],
                        candidate["search_query"],
                        candidate["current_price"],
                        candidate["current_price"],
                    ),
                )
                subscription = cursor.fetchone()
                cursor.execute(
                    "DELETE FROM subscription_candidates WHERE token = %s;",
                    (token,),
                )
                return dict(subscription)
    finally:
        connection.close()


def list_subscriptions(
    telegram_user_id: int,
) -> list[dict[str, Any]]:
    connection = get_connection()
    try:
        with connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT
                    id,
                    product_query,
                    baseline_price,
                    last_seen_price,
                    created_at
                FROM price_subscriptions
                WHERE telegram_user_id = %s
                  AND active = TRUE
                ORDER BY created_at DESC;
                """,
                (telegram_user_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def deactivate_subscription(
    subscription_id: int,
    telegram_user_id: int,
) -> bool:
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE price_subscriptions
                    SET active = FALSE,
                        updated_at = NOW()
                    WHERE id = %s
                      AND telegram_user_id = %s
                      AND active = TRUE;
                    """,
                    (subscription_id, telegram_user_id),
                )
                return cursor.rowcount > 0
    finally:
        connection.close()


def get_due_subscriptions(
    limit: int = 25,
) -> list[dict[str, Any]]:
    connection = get_connection()
    try:
        with connection.cursor(
            cursor_factory=RealDictCursor
        ) as cursor:
            cursor.execute(
                """
                SELECT *
                FROM price_subscriptions
                WHERE active = TRUE
                  AND (
                      checked_at IS NULL
                      OR checked_at < NOW() - INTERVAL '1 hour'
                  )
                ORDER BY checked_at NULLS FIRST, id
                LIMIT %s;
                """,
                (limit,),
            )
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()


def record_price_check(
    subscription_id: int,
    current_price: float | None,
    notified: bool = False,
) -> None:
    connection = get_connection()
    try:
        with connection:
            with connection.cursor() as cursor:
                if current_price is None:
                    cursor.execute(
                        """
                        UPDATE price_subscriptions
                        SET checked_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s;
                        """,
                        (subscription_id,),
                    )
                    return

                if notified:
                    cursor.execute(
                        """
                        UPDATE price_subscriptions
                        SET last_seen_price = %s,
                            last_notified_price = %s,
                            checked_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s;
                        """,
                        (current_price, current_price, subscription_id),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE price_subscriptions
                        SET last_seen_price = %s,
                            checked_at = NOW(),
                            updated_at = NOW()
                        WHERE id = %s;
                        """,
                        (current_price, subscription_id),
                    )
    finally:
        connection.close()


def should_notify(
    current_price: float,
    last_seen_price: Decimal | float,
    last_notified_price: Decimal | float | None,
) -> bool:
    current = round(float(current_price), 2)
    previous = round(float(last_seen_price), 2)
    if current >= previous:
        return False
    if last_notified_price is None:
        return True
    return current != round(float(last_notified_price), 2)
