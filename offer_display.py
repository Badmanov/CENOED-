from collections.abc import Callable, Collection
from typing import Any


def has_preferred_offers(
    offers: list[dict[str, Any]],
    preferred_retailers: Collection[str],
    retailer_formatter: Callable[[Any, Any], str],
) -> bool:
    """Return whether at least one priced offer belongs to a major retailer."""
    return any(
        retailer_formatter(
            offer.get("store"),
            offer.get("link"),
        ) in preferred_retailers
        for offer in offers
    )


def select_display_offers(
    offers: list[dict[str, Any]],
    preferred_retailers: Collection[str],
    retailer_formatter: Callable[[Any, Any], str],
    limit: int = 10,
    secondary_limit: int = 3,
) -> list[dict[str, Any]]:
    """Keep major retailers prominent without flooding users with unknowns."""
    preferred = []
    secondary = []

    for offer in offers:
        retailer = retailer_formatter(
            offer.get("store"),
            offer.get("link"),
        )
        target = (
            preferred
            if retailer in preferred_retailers
            else secondary
        )
        target.append(offer)

    preferred.sort(
        key=lambda item: item["numeric_price"]
    )
    secondary.sort(
        key=lambda item: item["numeric_price"]
    )

    return (
        preferred[:limit]
        + secondary[:secondary_limit]
    )[:limit]
