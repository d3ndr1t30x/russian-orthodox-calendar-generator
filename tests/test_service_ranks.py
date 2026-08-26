from datetime import date

from pypdf import PdfReader

from orthodox_calendar.data_sources.holy_trinity import parse_day
from orthodox_calendar.database.database import Database
from orthodox_calendar.models import (
    CalendarDay, FastLevel, Fasting, PublicHoliday, ServiceRank, ServiceRankInfo, Source,
)
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer
from orthodox_calendar.service_ranks import (
    highest_rank, localized_rank_name, normalize_holy_trinity_code, normalize_term,
)


EXPECTED_CODES = {
    6: ServiceRank.GREAT_FEAST, 5: ServiceRank.VIGIL, 4: ServiceRank.POLYELEOS,
    3: ServiceRank.DOXOLOGY, 2: ServiceRank.SIX_STICHERA,
    1: ServiceRank.NO_SIGN, 0: ServiceRank.NO_SIGN,
}


def info(rank: ServiceRank) -> ServiceRankInfo:
    return ServiceRankInfo(rank)


def test_holy_trinity_typikon_codes_map_exactly_without_name_inference():
    for code, expected in EXPECTED_CODES.items():
        result = normalize_holy_trinity_code(code, "https://example/rank")
        assert result.normalized_rank == expected
        assert result.source_rank_text == str(code)
        assert result.status == "source_mapped"
    assert normalize_holy_trinity_code(99).normalized_rank == ServiceRank.UNKNOWN
    assert normalize_holy_trinity_code(None).normalized_rank == ServiceRank.NO_DATA


def test_source_terms_and_language_labels_are_independent():
    polyeleos = normalize_term("Полиелейная служба")
    assert polyeleos.normalized_rank == ServiceRank.POLYELEOS
    assert localized_rank_name(polyeleos, "English") == "Polyeleos"
    assert localized_rank_name(polyeleos, "Russian") == "Полиелейная служба"
    assert normalize_term("Unmapped source rubric").normalized_rank == ServiceRank.UNKNOWN


def test_rank_hierarchy_selects_only_highest_day_marker():
    values = [info(ServiceRank.NO_SIGN), info(ServiceRank.DOXOLOGY), info(ServiceRank.POLYELEOS)]
    assert highest_rank(values).normalized_rank == ServiceRank.POLYELEOS
    values.append(info(ServiceRank.VIGIL)); values.append(info(ServiceRank.GREAT_FEAST))
    assert highest_rank(values).normalized_rank == ServiceRank.GREAT_FEAST


def test_parser_and_database_preserve_rank_provenance_and_override(tmp_path):
    html = """<span class='dataheader'>January 2, 2027 / December 20, 2026</span>
    <span class='headerheader'>Week. Tone two.</span>
    <span class='normaltext'><span class='typicon-4'>4</span>Source commemoration.<br></span>"""
    parsed = parse_day(html, date(2027, 1, 2), "en", "https://example/day")
    assert parsed.entries[0].service_rank == ServiceRank.POLYELEOS
    db = Database(tmp_path / "rank.sqlite3"); db.initialize()
    db.replace_holy_trinity_year(2027, [parsed], Source("Authoritative Test", "https://example", source_year=2027), False)
    metadata = db.day_metadata_for_year(2027, "en")[date(2027, 1, 2)][2]
    assert metadata.normalized_rank == ServiceRank.POLYELEOS
    assert metadata.source_rank_text == "4" and metadata.source_url == "https://example/day"
    db.set_service_rank_override(date(2027, 1, 2), ServiceRank.DOXOLOGY)
    overridden = db.day_metadata_for_year(2027, "en")[date(2027, 1, 2)][2]
    assert overridden.normalized_rank == ServiceRank.DOXOLOGY and overridden.user_override


def test_rank_fasting_and_australian_holiday_remain_separate():
    day = CalendarDay(
        date(2027, 1, 26), date(2027, 1, 13),
        fasting=Fasting(FastLevel.FISH, "Fast", "Fish allowed"),
        public_holidays=[PublicHoliday("Australia Day", "Queensland", Source("Australia holidays"))],
        service_rank=info(ServiceRank.POLYELEOS),
    )
    assert PdfRenderer.rank_icon_name(day) == "polyeleos"
    assert PdfRenderer.permission_icons(day) == ["fish"]
    assert day.public_holidays[0].name == "Australia Day"


def test_each_supported_rank_selects_a_distinct_icon():
    ranks = (ServiceRank.GREAT_FEAST, ServiceRank.VIGIL, ServiceRank.POLYELEOS, ServiceRank.DOXOLOGY, ServiceRank.SIX_STICHERA, ServiceRank.NO_SIGN)
    names = {PdfRenderer.rank_icon_name(CalendarDay(date(2027, 1, 1), date(2026, 12, 19), service_rank=info(rank))) for rank in ranks}
    assert names == {"great_feast", "vigil", "polyeleos", "doxology", "six_stichera", "no_sign"}


def test_pdf_embeds_every_rank_icon_and_cyrillic_rank_legend(tmp_path):
    ranks = (ServiceRank.GREAT_FEAST, ServiceRank.VIGIL, ServiceRank.POLYELEOS, ServiceRank.DOXOLOGY, ServiceRank.SIX_STICHERA, ServiceRank.NO_SIGN)
    days = [CalendarDay(date(2027, 1, index), date(2026, 12, 18 + index), service_rank=info(rank)) for index, rank in enumerate(ranks, 1)]
    output = tmp_path / "all-ranks.pdf"
    PdfRenderer().render(output, days, PdfOptions(2027, "Queensland", language="Russian", months=[1], include_fasting_legend=False))
    page = PdfReader(output).pages[0]; text = page.extract_text() or ""
    assert "Полиелейная служба" in text and "Славословная служба" in text and "Без знака" in text
    xobjects = page["/Resources"]["/XObject"].get_object()
    images = [obj for obj in xobjects.values() if obj.get_object().get("/Subtype") == "/Image"]
    assert len(images) >= 6
