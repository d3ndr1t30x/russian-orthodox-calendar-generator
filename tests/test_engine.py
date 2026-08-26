from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine


def test_leap_year_is_complete_and_layers_are_distinct():
    days = OrthodoxCalendarEngine().generate_year(2028, "Queensland")
    assert len(days) == 366
    australia_day = days[25]
    assert australia_day.public_holidays and all("Australia" not in feast.name for feast in australia_day.feasts)
    assert all(day.julian_date for day in days)

