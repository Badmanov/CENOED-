import unittest

from location_profile import (
    compose_search_location,
    normalize_store_location,
)


class StoreLocationTests(unittest.TestCase):
    def test_normalizes_whitespace(self):
        self.assertEqual(
            normalize_store_location(
                "  Красное & Белое,   ул. Тверская, 12  "
            ),
            "Красное & Белое, ул. Тверская, 12",
        )

    def test_preserves_human_readable_address(self):
        self.assertEqual(
            normalize_store_location("Пятёрочка у метро Сокол"),
            "Пятёрочка у метро Сокол",
        )

    def test_combines_store_with_city_for_local_search(self):
        self.assertEqual(
            compose_search_location(
                "Москва, Россия",
                "Красное & Белое, ул. Тверская, 12",
            ),
            "Красное & Белое, ул. Тверская, 12, Москва, Россия",
        )


if __name__ == "__main__":
    unittest.main()
