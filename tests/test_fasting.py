from datetime import date, timedelta

from orthodox_calendar.calendar_engine.fasting_rules import fasting_for_date
from orthodox_calendar.calendar_engine.pascha import orthodox_pascha
from orthodox_calendar.models import FastLevel


def test_great_lent_and_bright_week():
    pascha = orthodox_pascha(2027)
    assert fasting_for_date(pascha - timedelta(days=20)).period == "Great Lent"
    assert fasting_for_date(pascha - timedelta(days=3)).period == "Holy Week"
    assert fasting_for_date(pascha + timedelta(days=2)).level == FastLevel.FREE


def test_fixed_fasts_old_calendar():
    assert fasting_for_date(date(2027, 8, 20)).period == "Dormition Fast"
    assert fasting_for_date(date(2027, 12, 20)).period == "Nativity Fast"


def test_non_fast_tuesday_is_free():
    value = date(2027, 7, 27)
    assert value.weekday() == 1
    assert fasting_for_date(value).level == FastLevel.FREE

