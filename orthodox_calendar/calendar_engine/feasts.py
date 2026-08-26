from __future__ import annotations

from datetime import date, timedelta

from orthodox_calendar.models import Feast, FeastRank, Source
from .date_conversion import gregorian_to_julian
from .pascha import orthodox_pascha

CALCULATED_SOURCE = Source("Calculated from the Julian calendar and Orthodox Paschalion", version="1.0")

FIXED_FEASTS: dict[tuple[int, int], tuple[str, FeastRank]] = {
    (1, 6): ("Theophany of Our Lord", FeastRank.GREAT),
    (2, 2): ("Meeting of Our Lord in the Temple", FeastRank.GREAT),
    (3, 25): ("Annunciation of the Most Holy Theotokos", FeastRank.GREAT),
    (6, 24): ("Nativity of St John the Baptist", FeastRank.MAJOR),
    (6, 29): ("Holy Apostles Peter and Paul", FeastRank.MAJOR),
    (8, 6): ("Transfiguration of Our Lord", FeastRank.GREAT),
    (8, 15): ("Dormition of the Most Holy Theotokos", FeastRank.GREAT),
    (8, 29): ("Beheading of St John the Baptist", FeastRank.MAJOR),
    (9, 8): ("Nativity of the Most Holy Theotokos", FeastRank.GREAT),
    (9, 14): ("Exaltation of the Holy Cross", FeastRank.GREAT),
    (11, 21): ("Entry of the Most Holy Theotokos into the Temple", FeastRank.GREAT),
    (12, 25): ("Nativity of Christ", FeastRank.GREAT),
}


def feasts_for_year(year: int) -> dict[date, list[Feast]]:
    result: dict[date, list[Feast]] = {}
    start = date(year, 1, 1)
    current = start
    while current.year == year:
        old = gregorian_to_julian(current)
        if (old.month, old.day) in FIXED_FEASTS:
            name, rank = FIXED_FEASTS[(old.month, old.day)]
            result.setdefault(current, []).append(Feast(name, rank, source=CALCULATED_SOURCE, calculated=True))
        current += timedelta(days=1)
    pascha = orthodox_pascha(year)
    offsets = {
        -8: ("Lazarus Saturday", FeastRank.MAJOR),
        -7: ("Entry of Our Lord into Jerusalem (Palm Sunday)", FeastRank.GREAT),
        0: ("Holy Pascha - Resurrection of Christ", FeastRank.GREAT),
        39: ("Ascension of Our Lord", FeastRank.GREAT),
        49: ("Holy Pentecost", FeastRank.GREAT),
        56: ("Sunday of All Saints", FeastRank.MAJOR),
    }
    for offset, (name, rank) in offsets.items():
        target = pascha + timedelta(days=offset)
        if target.year == year:
            result.setdefault(target, []).append(Feast(name, rank, source=CALCULATED_SOURCE, calculated=True))
    return result

