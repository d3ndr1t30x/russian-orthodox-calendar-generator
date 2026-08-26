from __future__ import annotations

from datetime import date

import holidays

from orthodox_calendar.models import PublicHoliday, Source

JURISDICTIONS = {
    "None / International": None,
    "Australian Capital Territory": "ACT",
    "New South Wales": "NSW",
    "Northern Territory": "NT",
    "Queensland": "QLD",
    "South Australia": "SA",
    "Tasmania": "TAS",
    "Victoria": "VIC",
    "Western Australia": "WA",
}

SOURCE = Source("python-holidays: Australia rules", "https://github.com/vacanza/holidays", version=holidays.__version__)


def holidays_for_year(year: int, jurisdiction: str) -> dict[date, list[PublicHoliday]]:
    subdiv = JURISDICTIONS.get(jurisdiction, jurisdiction if jurisdiction in JURISDICTIONS.values() else None)
    if not subdiv:
        return {}
    rules = holidays.Australia(years=[year], subdiv=subdiv, observed=True, language="en_AU")
    return {day: [PublicHoliday(name, subdiv, SOURCE)] for day, name in rules.items()}

