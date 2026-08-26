from __future__ import annotations

from dataclasses import replace

from orthodox_calendar.models import ServiceRank, ServiceRankInfo


# Holy Trinity's own Typikon Signs key:
# https://www.holytrinityorthodox.com/htc/ocalendar/TipikonSigns.htm
HOLY_TRINITY_CODE_MAP = {
    6: ServiceRank.GREAT_FEAST,
    5: ServiceRank.VIGIL,
    4: ServiceRank.POLYELEOS,
    3: ServiceRank.DOXOLOGY,
    2: ServiceRank.SIX_STICHERA,
    1: ServiceRank.NO_SIGN,
    0: ServiceRank.NO_SIGN,
}

RANK_LABELS = {
    ServiceRank.GREAT_FEAST: ("Great Feast", "Бдение на великие праздники"),
    ServiceRank.VIGIL: ("Vigil", "Бдение"),
    ServiceRank.POLYELEOS: ("Polyeleos", "Полиелейная служба"),
    ServiceRank.DOXOLOGY: ("Doxology", "Славословная служба"),
    ServiceRank.SIX_STICHERA: ("Six Stichera", "Шестеричная служба"),
    ServiceRank.NO_SIGN: ("Ordinary Daily Service", "Без знака"),
    ServiceRank.OTHER: ("Other Service Rank", "Другой ранг службы"),
    ServiceRank.UNKNOWN: ("Unknown Service Rank", "Неизвестный ранг службы"),
    ServiceRank.NO_DATA: ("No Rank Data", "Нет данных о ранге"),
    ServiceRank.NONE: ("No Applicable Rank", "Ранг не применяется"),
}

RANK_PRIORITY = {
    ServiceRank.GREAT_FEAST: 70,
    ServiceRank.VIGIL: 60,
    ServiceRank.POLYELEOS: 50,
    ServiceRank.DOXOLOGY: 40,
    ServiceRank.SIX_STICHERA: 30,
    ServiceRank.NO_SIGN: 20,
    ServiceRank.OTHER: 10,
    ServiceRank.UNKNOWN: 5,
    ServiceRank.NO_DATA: 0,
    ServiceRank.NONE: 0,
}

TERM_MAP = {
    "great feast": ServiceRank.GREAT_FEAST,
    "бдение на великие праздники": ServiceRank.GREAT_FEAST,
    "vigil": ServiceRank.VIGIL,
    "бдение": ServiceRank.VIGIL,
    "polyeleos": ServiceRank.POLYELEOS,
    "polyeleos service": ServiceRank.POLYELEOS,
    "полиелей": ServiceRank.POLYELEOS,
    "полиелейная служба": ServiceRank.POLYELEOS,
    "doxology": ServiceRank.DOXOLOGY,
    "славословная служба": ServiceRank.DOXOLOGY,
    "со славословием": ServiceRank.DOXOLOGY,
    "six stichera": ServiceRank.SIX_STICHERA,
    "six-stichera": ServiceRank.SIX_STICHERA,
    "шестеричная служба": ServiceRank.SIX_STICHERA,
    "шестерик": ServiceRank.SIX_STICHERA,
    "no sign": ServiceRank.NO_SIGN,
    "ordinary daily service": ServiceRank.NO_SIGN,
    "без знака": ServiceRank.NO_SIGN,
}


def labels_for(rank: ServiceRank, overrides_en: dict[str, str] | None = None, overrides_ru: dict[str, str] | None = None) -> tuple[str, str]:
    english, russian = RANK_LABELS[rank]
    key = rank.value
    return (overrides_en or {}).get(key, english), (overrides_ru or {}).get(key, russian)


def normalize_holy_trinity_code(code: int | str | None, source_url: str = "", source_name: str = "Holy Trinity Orthodox Calendar") -> ServiceRankInfo:
    if code is None or str(code).strip() == "":
        rank, status, raw = ServiceRank.NO_DATA, "no_data", ""
    else:
        raw = str(code).strip()
        try:
            numeric = int(raw)
        except ValueError:
            rank = TERM_MAP.get(raw.casefold(), ServiceRank.UNKNOWN)
            status = "source_mapped" if rank != ServiceRank.UNKNOWN else "unresolved"
        else:
            rank = HOLY_TRINITY_CODE_MAP.get(numeric, ServiceRank.UNKNOWN)
            status = "source_mapped" if rank != ServiceRank.UNKNOWN else "unresolved"
    en, ru = labels_for(rank)
    return ServiceRankInfo(rank, en, ru, source_name, source_url, raw, status)


def normalize_term(term: str | None, source_url: str = "", source_name: str = "") -> ServiceRankInfo:
    if not term or not term.strip():
        return normalize_holy_trinity_code(None, source_url, source_name)
    raw = term.strip(); rank = TERM_MAP.get(raw.casefold(), ServiceRank.UNKNOWN); en, ru = labels_for(rank)
    return ServiceRankInfo(rank, en, ru, source_name, source_url, raw, "source_mapped" if rank != ServiceRank.UNKNOWN else "unresolved")


def highest_rank(infos: list[ServiceRankInfo]) -> ServiceRankInfo:
    if not infos:
        return normalize_holy_trinity_code(None)
    return max(infos, key=lambda item: RANK_PRIORITY[item.normalized_rank])


def localized_rank_name(info: ServiceRankInfo, language: str, overrides_en: dict[str, str] | None = None, overrides_ru: dict[str, str] | None = None) -> str:
    english, russian = labels_for(info.normalized_rank, overrides_en, overrides_ru)
    return russian if language == "Russian" else english


def with_labels(info: ServiceRankInfo, name_en: str, name_ru: str) -> ServiceRankInfo:
    return replace(info, name_en=name_en, name_ru=name_ru)
