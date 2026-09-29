import unittest
from unittest.mock import patch

import search_cache


class SearchFailureCacheTests(unittest.TestCase):
    def setUp(self):
        search_cache._RECENT_FAILURES.clear()

    def test_reuses_recent_failure(self):
        error = RuntimeError("provider unavailable")
        search_cache.record_search_failure(
            "shopping",
            "Добрый кола 1 л",
            "Москва",
            error,
        )

        failure = search_cache.get_recent_failure(
            "shopping",
            "  добрый   КОЛА  1 Л ",
            " москва ",
        )

        self.assertEqual(
            failure,
            "RuntimeError: provider unavailable",
        )

    def test_expired_failure_is_removed(self):
        with patch.object(search_cache.time, "monotonic", return_value=10):
            search_cache.record_search_failure(
                "shopping",
                "товар",
                None,
                RuntimeError("temporary"),
            )

        with patch.object(search_cache.time, "monotonic", return_value=71):
            failure = search_cache.get_recent_failure(
                "shopping",
                "товар",
                None,
                max_age_seconds=60,
            )

        self.assertIsNone(failure)

    def test_success_clears_failure(self):
        search_cache.record_search_failure(
            "retailer",
            "товар",
            "Москва",
            RuntimeError("temporary"),
        )
        search_cache.clear_search_failure(
            "retailer",
            "товар",
            "Москва",
        )

        self.assertIsNone(
            search_cache.get_recent_failure(
                "retailer",
                "товар",
                "Москва",
            )
        )


if __name__ == "__main__":
    unittest.main()
