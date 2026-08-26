from datetime import date

from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.data_sources.holy_trinity import HolyTrinityDay, HolyTrinityEntry, build_url, parse_day
from orthodox_calendar.database.database import Database
from orthodox_calendar.models import FastLevel, ServiceRank, Source


ENGLISH = """<p><span class="dataheader">Thursday January 7, 2027 / December 25, 2026</span></p>
<p><span class="headerheader">32<SUP>nd</SUP> Week after Pentecost. Tone six.<br><span class="headernofast">Sviatki. Fast-free</span></span></p>
<span class="normaltext"><span class="typicon-6">6</span><b>The Nativity of Christ</b>.<br>
<span class="typicon-2">2</span>Venerable Test of Brisbane (2027).<br>
<span class="typicon-0">0</span><i>From December 25 till January 5 is a Fast-free period.</i><br></span>"""

RUSSIAN = """<p><span class="dataheader">7 января 2027 / 25 декабря 2026</span></p>
<p><span class="headerheader">Седмица 32-я по Пятидесятнице. Глас 6.<br><span class="headernofast">Поста нет</span></span></p>
<span class="normaltext"><span class="typicon-6">6</span><b>Рождество Христово</b>.<br>
<span class="typicon-2">2</span>Преподобный Тест.<br></span>"""


def test_builds_same_endpoint_shape_as_legacy_binary():
    url = build_url(date(2027, 1, 7), "en")
    assert "holytrinityorthodox.com/htc/ocalendar/v2calendar.php" in url
    assert "year=2027" in url and "month=1" in url and "today=7" in url and "sid=em" in url
    assert "/ru/v2calendar.php" in build_url(date(2027, 1, 7), "ru")


def test_parser_preserves_rank_week_tone_fast_and_bilingual_text():
    english = parse_day(ENGLISH, date(2027, 1, 7), "en")
    russian = parse_day(RUSSIAN, date(2027, 1, 7), "ru")
    assert english.julian_label == "December 25, 2026"
    assert english.liturgical_week.startswith("32nd Week") and english.tone == 6
    assert english.fasting_text == "Sviatki. Fast-free"
    assert english.entries[0].is_feast and english.entries[0].rank == 7
    assert english.entries[0].service_rank == ServiceRank.GREAT_FEAST
    assert len(english.entries) == 2
    assert russian.entries[0].name == "Рождество Христово."


def test_database_and_engine_select_language_and_source_fasting(tmp_path):
    db = Database(tmp_path / "db.sqlite3"); db.initialize()
    en = parse_day(ENGLISH, date(2027, 1, 7), "en", "https://example/en")
    ru = parse_day(RUSSIAN, date(2027, 1, 7), "ru", "https://example/ru")
    counts = db.replace_holy_trinity_year(2027, [en, ru], Source("Holy Trinity Orthodox Calendar", "https://example", source_year=2027), False)
    assert counts == {"saints": 2, "feasts": 2, "fasting": 2, "days": 2}
    english_day = OrthodoxCalendarEngine(db).generate_year(2027, "Queensland", "English")[6]
    russian_day = OrthodoxCalendarEngine(db).generate_year(2027, "Queensland", "Russian / Русский")[6]
    assert english_day.saints[0].display_name.startswith("Venerable Test")
    assert russian_day.saints[0].display_name == "Преподобный Тест."
    assert english_day.fasting.level == FastLevel.FREE
    assert english_day.tone == 6
    assert english_day.service_rank.normalized_rank == ServiceRank.GREAT_FEAST
    assert russian_day.service_rank.normalized_rank == ServiceRank.GREAT_FEAST
    assert russian_day.service_rank.name_ru == "Бдение на великие праздники"
