from decimal import Decimal

BASE_PER_PAGE = Decimal("0.0400")
PER_EXTRA_FIELD = Decimal("0.0005")
FIELD_THRESHOLD = 30


def compute_cost(*, pages: int, field_count: int) -> Decimal:
    if pages < 0 or field_count < 0:
        raise ValueError("pages and field_count must be non-negative")
    extras = max(0, field_count - FIELD_THRESHOLD)
    per_page = BASE_PER_PAGE + extras * PER_EXTRA_FIELD
    return (Decimal(pages) * per_page).quantize(Decimal("0.0001"))
