import unittest

from offer_display import has_preferred_offers, select_display_offers


class OfferDisplayTests(unittest.TestCase):
    PREFERRED = {"Пятёрочка", "Перекрёсток", "Ozon"}

    @staticmethod
    def offer(store: str, price: float) -> dict:
        return {
            "store": store,
            "link": "",
            "numeric_price": price,
        }

    def test_major_retailers_come_before_unknown_stores(self):
        offers = [
            self.offer("Неизвестный", 50),
            self.offer("Пятёрочка", 100),
            self.offer("Ozon", 90),
        ]

        selected = select_display_offers(
            offers,
            self.PREFERRED,
            lambda store, link: store,
        )

        self.assertEqual(
            [item["store"] for item in selected],
            ["Ozon", "Пятёрочка", "Неизвестный"],
        )

    def test_only_three_unknown_stores_are_shown(self):
        offers = [
            self.offer(f"Магазин {index}", float(index))
            for index in range(1, 8)
        ]

        selected = select_display_offers(
            offers,
            self.PREFERRED,
            lambda store, link: store,
        )

        self.assertEqual(len(selected), 3)
        self.assertEqual(
            [item["numeric_price"] for item in selected],
            [1.0, 2.0, 3.0],
        )

    def test_major_retailers_do_not_use_unknown_store_quota(self):
        offers = [
            self.offer("Пятёрочка", 100),
            self.offer("Перекрёсток", 110),
            *[
                self.offer(f"Магазин {index}", float(index))
                for index in range(1, 6)
            ],
        ]

        selected = select_display_offers(
            offers,
            self.PREFERRED,
            lambda store, link: store,
        )

        self.assertEqual(len(selected), 5)
        self.assertEqual(
            [item["store"] for item in selected[:2]],
            ["Пятёрочка", "Перекрёсток"],
        )

    def test_detects_when_major_retailer_has_a_price(self):
        offers = [
            self.offer("Неизвестный", 50),
            self.offer("Пятёрочка", 100),
        ]

        self.assertTrue(
            has_preferred_offers(
                offers,
                self.PREFERRED,
                lambda store, link: store,
            )
        )

    def test_reports_no_major_retailer_price(self):
        offers = [self.offer("Неизвестный", 50)]

        self.assertFalse(
            has_preferred_offers(
                offers,
                self.PREFERRED,
                lambda store, link: store,
            )
        )


if __name__ == "__main__":
    unittest.main()
