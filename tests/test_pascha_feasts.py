from datetime import date

import pytest

from orthodox_calendar.calendar_engine.feasts import feasts_for_year
from orthodox_calendar.calendar_engine.pascha import orthodox_pascha


@pytest.mark.parametrize(("year", "expected"), [(2024, date(2024, 5, 5)), (2025, date(2025, 4, 20)), (2026, date(2026, 4, 12)), (2027, date(2027, 5, 2)), (2030, date(2030, 4, 28))])
def test_known_orthodox_pascha_dates(year, expected):
    assert orthodox_pascha(year) == expected


def test_fixed_and_movable_feasts():
    feasts = feasts_for_year(2027)
    assert any("Nativity of Christ" == item.name for item in feasts[date(2027, 1, 7)])
    assert any("Holy Pascha" in item.name for item in feasts[date(2027, 5, 2)])
    assert any("Ascension" in item.name for item in feasts[date(2027, 6, 10)])

