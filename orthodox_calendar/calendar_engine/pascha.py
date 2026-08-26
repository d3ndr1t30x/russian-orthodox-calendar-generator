from __future__ import annotations

from datetime import date

from .date_conversion import julian_to_gregorian


def orthodox_pascha(year: int) -> date:
    """Meeus Julian algorithm, converted to the Gregorian civil calendar."""
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = ((d + e + 114) % 31) + 1
    return julian_to_gregorian(date(year, month, day))
