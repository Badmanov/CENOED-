def normalize_store_location(store_location: str) -> str:
    return " ".join(store_location.strip().split())


def compose_search_location(
    city: str,
    store_location: str | None,
) -> str:
    if not store_location:
        return city
    return f"{store_location}, {city}"
