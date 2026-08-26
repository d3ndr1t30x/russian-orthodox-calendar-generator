from __future__ import annotations

from datetime import date, timedelta

from orthodox_calendar.database.database import Database
from orthodox_calendar.models import CalendarDay, ServiceRank, ServiceRankInfo
from orthodox_calendar.service_ranks import labels_for
from .australian_holidays import holidays_for_year
from .date_conversion import gregorian_to_julian
from .fasting_rules import fasting_for_date
from .feasts import feasts_for_year
from .pascha import orthodox_pascha


class OrthodoxCalendarEngine:
    def __init__(self, database: Database | None = None):
        self.database = database

    def generate_year(self, year: int, jurisdiction: str, language: str = "English") -> list[CalendarDay]:
        if not 1583 <= year <= 4099:
            raise ValueError("Supported years are 1583-4099")
        feast_map = feasts_for_year(year)
        holiday_map = holidays_for_year(year, jurisdiction)
        language_code = "ru" if language.lower().startswith("russian") else "en"
        saints = self.database.saints_for_year(year, language_code) if self.database else {}
        imported_feasts = self.database.feasts_for_year(year, language_code) if self.database else {}
        imported_fasting = self.database.fasting_for_year(year, language_code) if self.database else {}
        metadata = self.database.day_metadata_for_year(year, language_code) if self.database else {}
        authoritative = self.database.has_authoritative_year(year) if self.database else False
        pascha = orthodox_pascha(year)
        result: list[CalendarDay] = []
        day = date(year, 1, 1)
        while day.year == year:
            offset = (day - pascha).days
            source_feasts = imported_feasts.get(day, [])
            existing = {item.name.casefold() for item in source_feasts}
            if language_code == "ru" and source_feasts:
                merged_feasts = source_feasts
            else:
                merged_feasts = source_feasts + [item for item in feast_map.get(day, []) if item.name.casefold() not in existing]
            liturgical_week, source_tone, service_rank = metadata.get(day, ("", None, ServiceRankInfo()))
            if service_rank.normalized_rank == ServiceRank.NO_DATA and any(feast.rank.value == "Great Feast" for feast in merged_feasts):
                name_en, name_ru = labels_for(ServiceRank.GREAT_FEAST)
                service_rank = ServiceRankInfo(ServiceRank.GREAT_FEAST, name_en, name_ru, "Calculated liturgical rules", "", "", "calculated_rule")
            result.append(CalendarDay(
                civil_date=day,
                julian_date=gregorian_to_julian(day),
                saints=saints.get(day, []),
                feasts=merged_feasts,
                fasting=imported_fasting.get(day, fasting_for_date(day)),
                public_holidays=holiday_map.get(day, []),
                paschal_offset=offset,
                liturgical_week=liturgical_week,
                tone=source_tone if source_tone is not None else (((offset // 7) % 8 + 1) if offset >= 7 and day.weekday() == 6 else None),
                authoritative_data_available=authoritative,
                service_rank=service_rank,
            ))
            day += timedelta(days=1)
        return result
