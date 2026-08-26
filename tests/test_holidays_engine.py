from datetime import date

import pytest

from orthodox_calendar.calendar_engine.australian_holidays import JURISDICTIONS, holidays_for_year


@pytest.mark.parametrize("jurisdiction", [name for name in JURISDICTIONS if not name.startswith("None")])
def test_all_jurisdictions_have_core_holidays(jurisdiction):
    result = holidays_for_year(2027, jurisdiction)
    assert date(2027, 1, 1) in result
    assert any("Australia Day" in h.name for h in result[date(2027, 1, 26)])


def test_international_has_no_australian_holidays():
    assert holidays_for_year(2027, "None / International") == {}

