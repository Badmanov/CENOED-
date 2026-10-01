import copy

def configured_cache_ttl_seconds(
    default_seconds: int = 6 * 60 * 60,
) -> int:
    """Read a bounded cache lifetime without risking a startup failure."""
    raw_value = os.getenv("SEARCH_CACHE_TTL_SECONDS", "").strip()
    if not raw_value:
        return default_seconds
    try:
        requested = int(raw_value)
    except ValueError:
        return default_seconds
    return min(max(requested, 5 * 60), 24 * 60 * 60)

import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from typing import Any

_TABLE_READY = False
_TABLE_LOCK = threading.Lock()
_INFLIGHT_LOCK = threading.Lock()
_INFLIGHT_SEARCHES: dict[str, threading.Event] = {}
_FAILURE_LOCK = threading.Lock()
_RECENT_FAILURES: dict[str, tuple[float, str]] = {}


def _database_url() -> str | None:
    value = os.getenv("DATABASE_URL")
    return value.strip() if value and value.strip() else None


def normalize_search_text(value: str | None) -> str:
    """Canonicalize harmless spelling and formatting differences."""
    text = unicodedata.normalize("NFKC", value or "")
    text = text.casefold().replace("ё", "е")
    text = re.sub(r"(?<=\d)[,.](?=\d)", ".", text)
    tokens = re.findall(r"\d+(?:\.\d+)?|[^\W\d_]+", text)
    unit_aliases = {
        "литр": "л",
        "литра": "л",
        "литров": "л",
        "миллилитр": "мл",
        "миллилитра": "мл",
        "миллилитров": "мл",
        "килограмм": "кг",
        "килограмма": "кг",
        "килограммов": "кг",
        "грамм": "г",
        "грамма": "г",
        "граммов": "г",
    }
    return " ".join(unit_aliases.get(token, token) for token in tokens)


def _legacy_cache_key(
    namespace: str,
    query: str,
    location: str | None,
) -> str:
    normalized = "|".join(
        (
            namespace,
            " ".join(query.casefold().split()),
            " ".join((location or "").casefold().split()),
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _cache_key(namespace: str, query: str, location: str | None) -> str:
    normalized = "|".join(
        (
            namespace,
            normalize_search_text(query),
            normalize_search_text(location),
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


def get_recent_failure(
    namespace: str,
    query: str,
    location: str | None,
    max_age_seconds: int = 60,
) -> str | None:
    """Return a recent provider failure without calling it again."""
    key = _cache_key(namespace, query, location)
    now = time.monotonic()
    with _FAILURE_LOCK:
        failure = _RECENT_FAILURES.get(key)
        if failure is None:
            return None
        created_at, message = failure
        if now - created_at <= max_age_seconds:
            return message
        _RECENT_FAILURES.pop(key, None)
    return None


def record_search_failure(
    namespace: str,
    query: str,
    location: str | None,
    error: Exception,
) -> None:
    key = _cache_key(namespace, query, location)
    message = f"{type(error).__name__}: {error}"
    with _FAILURE_LOCK:
        _RECENT_FAILURES[key] = (time.monotonic(), message)


def clear_search_failure(
    namespace: str,
    query: str,
    location: str | None,
) -> None:
    key = _cache_key(namespace, query, location)
    with _FAILURE_LOCK:
        _RECENT_FAILURES.pop(key, None)


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
                current_key = _cache_key(namespace, query, location)
                legacy_key = _legacy_cache_key(namespace, query, location)
                cursor.execute(
                    """
                    SELECT results
                    FROM search_result_cache
                    WHERE cache_key IN (%s, %s)
                      AND expires_at > NOW();
                    """,
                    (current_key, legacy_key),
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
