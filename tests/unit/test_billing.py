from decimal import Decimal

import pytest

from app.services.billing import compute_cost


def test_flat_rate_at_or_below_30_fields():
    assert compute_cost(pages=10, field_count=25) == Decimal("0.4000")
    assert compute_cost(pages=10, field_count=30) == Decimal("0.4000")


def test_extra_fields_increment_per_page():
    assert compute_cost(pages=10, field_count=35) == Decimal("0.4250")


def test_zero_pages_zero_cost():
    assert compute_cost(pages=0, field_count=27) == Decimal("0.0000")


def test_negative_inputs_raise():
    with pytest.raises(ValueError):
        compute_cost(pages=-1, field_count=10)
    with pytest.raises(ValueError):
        compute_cost(pages=1, field_count=-1)
