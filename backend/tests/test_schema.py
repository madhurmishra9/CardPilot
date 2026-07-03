"""CI guard: every card file must validate, reference known categories, and
carry provenance. A YAML typo fails the build instead of poisoning the math."""

from datetime import date

import pytest

from app.catalog import load_card_rules, load_categories
from app.schema import CardRules, is_stale

CATALOG = load_card_rules()
CATEGORY_KEYS = {c["key"] for c in load_categories()}


@pytest.mark.parametrize("card_id", sorted(CATALOG))
def test_card_file_validates(card_id):
    CardRules.model_validate(CATALOG[card_id])


@pytest.mark.parametrize("card_id", sorted(CATALOG))
def test_earn_categories_exist_in_taxonomy(card_id):
    rules = CATALOG[card_id]
    for entry in rules["earn_rules"]["rates"]:
        assert entry["category"] in CATEGORY_KEYS, \
            f"{card_id}: unknown earn category '{entry['category']}'"
    for cat in rules["earn_rules"].get("excluded_categories", []):
        assert cat in CATEGORY_KEYS, f"{card_id}: unknown excluded category '{cat}'"


@pytest.mark.parametrize("card_id", sorted(CATALOG))
def test_card_id_matches_filename_convention(card_id):
    assert CATALOG[card_id]["card_id"] == card_id


def test_staleness_detection():
    assert not is_stale("2026-07-01", today=date(2026, 7, 3))
    assert not is_stale("2026-02-01", today=date(2026, 7, 3))   # 5 months
    assert is_stale("2026-01-01", today=date(2026, 7, 3))       # 6 months
    assert is_stale("garbage")


def test_schema_rejects_bad_files():
    from pydantic import ValidationError
    good = dict(CATALOG["icici_coral"])
    bad = good | {"annual_fee": -5}
    with pytest.raises(ValidationError):
        CardRules.model_validate(bad)
    missing_provenance = {k: v for k, v in good.items() if k != "last_verified"}
    with pytest.raises(ValidationError):
        CardRules.model_validate(missing_provenance)
