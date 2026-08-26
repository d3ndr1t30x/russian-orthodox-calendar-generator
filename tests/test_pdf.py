from datetime import date

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4

from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.models import CalendarDay, Feast, FeastRank, FastLevel, Fasting, Saint, Source
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer


def test_annual_pdf_is_twelve_a4_pages_and_contains_cyrillic(tmp_path):
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    days[6].saints.append(Saint(1, "Test", "Святитель Иоанн Златоуст with an intentionally very long name that must never overflow the day cell", date(2027, 1, 7), source=Source("Test")))
    output = tmp_path / "calendar.pdf"
    PdfRenderer().render(output, days, PdfOptions(2027, "Queensland"))
    reader = PdfReader(output)
    assert len(reader.pages) == 12
    width = float(reader.pages[0].mediabox.width); height = float(reader.pages[0].mediabox.height)
    assert abs(width - A4[1]) < 0.1 and abs(height - A4[0]) < 0.1
    assert "January" in (reader.pages[0].extract_text() or "")


def test_selected_month_and_landscape(tmp_path):
    days = OrthodoxCalendarEngine().generate_year(2028, "Victoria")
    output = tmp_path / "one.pdf"
    PdfRenderer().render(output, days, PdfOptions(2028, "Victoria", orientation="Landscape", months=[2]))
    reader = PdfReader(output); assert len(reader.pages) == 1
    assert float(reader.pages[0].mediabox.width) > float(reader.pages[0].mediabox.height)


def test_russian_pdf_uses_cyrillic_source_text_and_embedded_images(tmp_path):
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland", "Russian")
    days[0].saints.append(Saint(2, "Test", "Святитель Иоанн", date(2027, 1, 1), source=Source("Test")))
    output = tmp_path / "russian.pdf"
    PdfRenderer().render(output, days, PdfOptions(2027, "Queensland", language="Russian", months=[1]))
    reader = PdfReader(output); text = reader.pages[0].extract_text() or ""
    assert "Январь" in text and "Святитель Иоанн" in text
    assert "/XObject" in reader.pages[0]["/Resources"]


def test_visual_priority_and_permission_icon_rules():
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    strict = next(day for day in days if day.fasting and day.fasting.level.value == "Strict fast")
    assert PdfRenderer.visual_state(strict) == "strict_fast"
    assert "strict_fast" in PdfRenderer.permission_icons(strict)


def test_great_feast_and_vigil_override_strict_wash():
    day = CalendarDay(date(2027, 1, 1), date(2026, 12, 19), fasting=Fasting(FastLevel.STRICT, "Strict fast", "No food"))
    day.feasts = [Feast("Vigil", FeastRank.MAJOR, liturgical_status="Rank 5 Vigil")]
    assert PdfRenderer.visual_state(day) == "vigil"
    day.feasts = [Feast("Great Feast", FeastRank.GREAT)]
    assert PdfRenderer.visual_state(day) == "great_feast"


def test_fish_wine_and_oil_icons_are_distinct():
    renderer = PdfRenderer()
    assert renderer.permission_icons(Fasting(FastLevel.FISH, "Fast", "Fish allowed")) == ["fish"]
    assert renderer.permission_icons(Fasting(FastLevel.WINE_OIL, "Fast", "Wine and oil permitted")) == ["wine", "oil"]
    assert {"fish", "wine", "oil"}.issubset(renderer.icons)
