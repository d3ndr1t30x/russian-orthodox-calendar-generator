from datetime import date

from orthodox_calendar.calendar_engine.date_conversion import gregorian_to_julian, julian_to_gregorian


def test_modern_known_conversion():
    assert gregorian_to_julian(date(2027, 1, 7)) == date(2026, 12, 25)
    assert julian_to_gregorian(date(2026, 12, 25)) == date(2027, 1, 7)


def test_offset_is_not_hard_coded():
    assert gregorian_to_julian(date(2101, 3, 15)) == date(2101, 3, 1)


def test_round_trip_across_supported_range():
    for value in (date(1600, 1, 1), date(1900, 3, 1), date(2026, 8, 26), date(2400, 12, 31)):
        assert julian_to_gregorian(gregorian_to_julian(value)) == value

