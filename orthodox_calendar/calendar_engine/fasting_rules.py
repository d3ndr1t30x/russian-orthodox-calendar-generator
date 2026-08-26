from __future__ import annotations

from datetime import date, timedelta

from orthodox_calendar.models import FastLevel, Fasting, Source
from .date_conversion import gregorian_to_julian, julian_to_gregorian
from .pascha import orthodox_pascha

SOURCE = Source("General Russian Orthodox fasting rules - verify with the current parish typikon", version="1.0")


def _entry(level: FastLevel, period: str, detail: str) -> Fasting:
    return Fasting(level, period, detail, SOURCE)


def fasting_for_date(day: date) -> Fasting:
    pascha = orthodox_pascha(day.year)
    offset = (day - pascha).days
    old = gregorian_to_julian(day)

    if -70 <= offset <= -64:
        return _entry(FastLevel.FREE, "Publican and Pharisee week", "Fast-free week")
    if -55 <= offset <= -49:
        return _entry(FastLevel.ORDINARY, "Cheesefare week", "Abstinence from meat; local practice may vary")
    if -48 <= offset <= -8:
        level = FastLevel.WINE_OIL if day.weekday() in (5, 6) else FastLevel.STRICT
        return _entry(level, "Great Lent", "Great Lenten fast; permissions depend on the typikon")
    if -7 <= offset <= -1:
        return _entry(FastLevel.STRICT, "Holy Week", "Strict fast; follow parish guidance")
    if 0 <= offset <= 6:
        return _entry(FastLevel.FREE, "Bright Week", "Fast-free week")
    if 50 <= offset <= 56:
        return _entry(FastLevel.FREE, "Trinity Week", "Fast-free week")

    apostles_start = pascha + timedelta(days=57)
    apostles_end = julian_to_gregorian(date(day.year, 6, 28))
    if apostles_start <= apostles_end and apostles_start <= day <= apostles_end:
        level = FastLevel.FISH if day.weekday() not in (2, 4) else FastLevel.STRICT
        return _entry(level, "Apostles' Fast", "Fish permissions and exceptions depend on the typikon")

    if (old.month, old.day) >= (8, 1) and (old.month, old.day) <= (8, 14):
        level = FastLevel.WINE_OIL if day.weekday() in (5, 6) else FastLevel.STRICT
        return _entry(level, "Dormition Fast", "Dormition fast; permissions depend on the typikon")
    if (old.month == 11 and old.day >= 15) or (old.month == 12 and old.day <= 24):
        level = FastLevel.FISH if day.weekday() not in (2, 4) else FastLevel.STRICT
        return _entry(level, "Nativity Fast", "Nativity fast; permissions change late in the fast")
    if (old.month, old.day) in {(1, 5), (1, 18), (8, 29), (9, 14)}:
        return _entry(FastLevel.STRICT, "One-day fast", "Strict fast; exceptions may apply")
    if day.weekday() in (2, 4):
        return _entry(FastLevel.ORDINARY, "Weekly fast", "Wednesday/Friday fast; feast-day exceptions may apply")
    return _entry(FastLevel.FREE, "No general fast", "Fast-free")
