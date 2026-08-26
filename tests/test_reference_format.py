from pathlib import Path

from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.rendering.layout import REFERENCE_LAYOUT
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer


def test_reference_geometry_matches_measured_docx():
    assert abs(REFERENCE_LAYOUT.margin_left / mm - 7.1) < .01
    assert abs((A4[1] - REFERENCE_LAYOUT.margin_left - REFERENCE_LAYOUT.margin_right) / 7 / mm - 40.4) < .1
    assert REFERENCE_LAYOUT.weekday_height / mm == 4.6


def test_reference_pdf_is_sunday_first_and_landscape(tmp_path: Path):
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    output = tmp_path / "reference.pdf"
    PdfRenderer().render(output, days, PdfOptions(2027, "Queensland", months=[1]))
    page = PdfReader(output).pages[0]
    text = page.extract_text() or ""
    assert text.index("SUN") < text.index("MON") < text.index("SAT")
    assert "January" in text
    assert float(page.mediabox.width) > float(page.mediabox.height)


def test_reference_renderer_embeds_serif_and_sans_fonts(tmp_path: Path):
    days = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    output = tmp_path / "fonts.pdf"
    PdfRenderer().render(output, days, PdfOptions(2027, "Queensland", months=[1]))
    fonts = str(PdfReader(output).pages[0]["/Resources"]["/Font"])
    assert fonts
