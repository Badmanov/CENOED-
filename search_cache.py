import copy
import hashlib
import json
import os
import threading
from typing import Any

_TABLE_READY = False
_TABLE_LOCK = threading.Lock()
_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT_SEARCHES: dict[str, threading.Event] = {}


def _database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    return value.strip() if value and value.strip() else None


def _cache_key(namespace: str, query: str, location: str | None) -> str:
    normalized = "|".join(
        (
            namespace,
            " ".join(query.casefold().split()),
            " ".join((location or "").casefold().split()),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def begin_search(
    namespace: str,
    query: str,
    location: str | None,
) -> tuple[bool, threading.Event]:
    """Elect one caller to perform an identical external search."""
    key = _cache_key(namespace, query, location)
    with _INFLIGHT_LOCK:
        existing = _INFLIGHT_SEARCHES.get(key)
        if existing is not None:
            return False, existing
        event = threading.Event()
        _INFLIGHT_SEARCHES[key] = event
        return True, event


def finish_search(
    namespace: str,
    query: str,
    location: str | None,
) -> None:
    key = _cache_key(namespace, query, location)
    with _INFLIGHT_LOCK:
        event = _INFLIGHT_SEARCHES.pop(key, None)
    if event is not None:
        event.set()


def _connect(database_url: str):
    import psycopg2

    return psycopg2.connect(database_url, connect_timeout=5)


def _ensure_table(database_url: str) -> None:
    global _TABLE_READY
    if _TABLE_READY:
        return

    with _TABLE_LOCK:
        if _TABLE_READY:
            return
        with _connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS search_result_cache (
                        cache_key TEXT PRIMARY KEY,
                        namespace TEXT NOT NULL,
                        query_text TEXT NOT NULL,
                        location_text TEXT,
                        results JSONB NOT NULL,
                        expires_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS
                        idx_search_result_cache_expires_at
                    ON search_result_cache(expires_at);
                    """
                )
        _TABLE_READY = True


def get_persistent_results(
    namespace: str,
    query: str,
    location: str | None,
) -> list[dict[str, Any]] | None:
    database_url = _database_url()
    if not database_url:
        return None

    try:
        _ensure_table(database_url)
        with _connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT results
                    FROM search_result_cache
                    WHERE cache_key = %s
                      AND expires_at > NOW();
                    """,
                    (_cache_key(namespace, query, location),),
                )
                row = cursor.fetchone()
        if not row:
            return None
        results = row[0]
        if isinstance(results, str):
            results = json.loads(results)
        if not isinstance(results, list):
            return None
        return copy.deepcopy(results)
    except Exception as error:
        print(
            f"SEARCH CACHE READ ERROR: {type(error).__name__}",
            flush=True,
        )
        return None


def save_persistent_results(
    namespace: str,
    query: str,
    location: str | None,
    results: list[dict[str, Any]],
    ttl_seconds: int,
) -> None:
    database_url = _database_url()
    if not database_url or ttl_seconds <= 0:
        return

    try:
        from psycopg2.extras import Json

        _ensure_table(database_url)
        with _connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO search_result_cache (
                        cache_key,
                        namespace,
                        query_text,
                        location_text,
                        results,
                        expires_at,
                        updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        NOW() + (%s * INTERVAL '1 second'),
                        NOW()
                    )
                    ON CONFLICT (cache_key) DO UPDATE SET
                        results = EXCLUDED.results,
                        expires_at = EXCLUDED.expires_at,
                        updated_at = NOW();
                    """,
                    (
                        _cache_key(namespace, query, location),
                        namespace,
                        query,
                        location,
                        Json(results),
                        ttl_seconds,
                    ),
                )
    except Exception as error:
        print(
            f"SEARCH CACHE WRITE ERROR: {type(error).__name__}",
            flush=True,
        )
