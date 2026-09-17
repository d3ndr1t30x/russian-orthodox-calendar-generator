from __future__ import annotations

import calendar
import os
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from orthodox_calendar import __version__
from orthodox_calendar.models import CalendarDay, FastLevel, ServiceRank
from orthodox_calendar.paths import asset_path
from orthodox_calendar.service_ranks import (
    icon_name_for, legend_label_for, rank_text_is_red, symbol_colour_for, symbol_for,
)
from .layout import REFERENCE_LAYOUT, ReferenceLayout
from .publication import is_primary_saint, ordered_selected_saints


MONTHS_RU = ("", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")
WEEKDAYS_EN = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
WEEKDAYS_RU = ("ВОСК", "ПОН", "ВТОР", "СРЕД", "ЧЕТ", "ПЯТ", "СУБ")


@dataclass(slots=True)
class PdfOptions:
    year: int
    jurisdiction: str
    template: str = "Traditional"
    orientation: str = "Landscape"
    language: str = "English"
    include_julian: bool = True
    include_holidays: bool = True
    include_sources: bool = True
    include_fasting_icons: bool = True
    include_fasting_legend: bool = True
    include_service_rank_icons: bool = True
    include_service_rank_legend: bool = True
    include_liturgical_week_tone: bool = True
    rank_labels_en: dict[str, str] = field(default_factory=dict)
    rank_labels_ru: dict[str, str] = field(default_factory=dict)
    months: list[int] = field(default_factory=lambda: list(range(1, 13)))
    parish_name: str = ""
    parish_logo: str = ""
    custom_header: str = ""
    custom_footer: str = ""


@dataclass(frozen=True, slots=True)
class PublicationPalette:
    ink = HexColor("#111111")
    sunday = HexColor("#971F25")
    weekday = HexColor("#3E62B0")
    strict = HexColor("#BFBFBF")
    feast_wash = HexColor("#FFCCCC")
    feast = HexColor("#CC0000")
    holiday = HexColor("#243CFF")
    note = HexColor("#009B16")
    white = HexColor("#FFFFFF")
    muted = HexColor("#555555")


class TextFitter:
    @staticmethod
    def lines(text: str, font: str, size: float, width: float, maximum: int) -> list[str]:
        words = " ".join(text.split()).split(" ") if text else []
        result: list[str] = []
        current = ""
        for word in words:
            trial = word if not current else f"{current} {word}"
            if pdfmetrics.stringWidth(trial, font, size) <= width:
                current = trial
            else:
                if current:
                    result.append(current)
                current = word
                if len(result) >= maximum:
                    break
        if current and len(result) < maximum:
            result.append(current)
        if result and " ".join(result) != " ".join(text.split()):
            while result[-1] and pdfmetrics.stringWidth(result[-1] + "…", font, size) > width:
                result[-1] = result[-1][:-1]
            result[-1] = result[-1].rstrip() + "…"
        return result


class IconRenderer:
    def __init__(self, layout: ReferenceLayout):
        self.layout = layout
        self.fasting = self._load("icons", ("fish", "wine", "oil", "strict_fast", "holiday"))
        self.rank = self._load("icons/rank", ("great_feast", "vigil", "polyeleos", "doxology", "six_stichera", "no_sign"))

    @staticmethod
    def _load(folder: str, names: tuple[str, ...]) -> dict[str, ImageReader]:
        result: dict[str, ImageReader] = {}
        for name in names:
            path = asset_path(*folder.split("/"), f"{name}.png")
            if path.exists():
                result[name] = ImageReader(str(path))
        return result

    @staticmethod
    def rank_name(day: CalendarDay) -> str | None:
        return icon_name_for(day.service_rank)

    @staticmethod
    def permissions(day_or_fasting) -> list[str]:
        fasting = getattr(day_or_fasting, "fasting", day_or_fasting)
        if not fasting or fasting.level == FastLevel.FREE:
            return []
        text = f"{fasting.period} {fasting.detail}".casefold()
        result: list[str] = []
        if "fish" in text or "рыб" in text:
            result.append("fish")
        if "wine" in text or "вино" in text:
            result.append("wine")
        if "food with oil" in text or "oil permitted" in text or "масл" in text or "елей" in text:
            result.append("oil")
        if fasting.level == FastLevel.WINE_OIL and not result:
            result.extend(("wine", "oil"))
        if fasting.level == FastLevel.STRICT:
            result.append("strict_fast")
        return result

    @staticmethod
    def draw(c: Canvas, source: dict[str, ImageReader], names: list[str], x: float, y: float, size: float) -> None:
        for index, name in enumerate(names):
            if name in source:
                c.drawImage(source[name], x + index * size * 1.08, y, size, size, mask="auto", preserveAspectRatio=True)

    @staticmethod
    def fasting_symbol_names(day_or_fasting) -> list[str]:
        names = IconRenderer.permissions(day_or_fasting)
        if "fish" in names:
            return ["fish"]
        if "oil" in names or "wine" in names:
            return ["oil"]
        return []


class HeaderRenderer:
    def __init__(self, layout: ReferenceLayout, fonts: dict[str, str], palette: PublicationPalette):
        self.layout, self.fonts, self.palette = layout, fonts, palette

    def draw(self, c: Canvas, x: float, top: float, width: float, month: int, options: PdfOptions) -> float:
        col = width / 7
        labels = WEEKDAYS_RU if options.language == "Russian" else WEEKDAYS_EN
        for index, label in enumerate(labels):
            c.setFillColor(self.palette.sunday if index == 0 else self.palette.weekday)
            c.rect(x + index * col, top - self.layout.weekday_height, col, self.layout.weekday_height, fill=1, stroke=1)
            c.setFillColor(self.palette.white)
            c.setFont(self.fonts["sans_bold"], 9)
            c.drawCentredString(x + (index + .5) * col, top - 3.45 * mm, label)
        title_y = top - self.layout.weekday_height - self.layout.title_height
        c.setFillColor(self.palette.white)
        c.rect(x, title_y, width, self.layout.title_height, fill=1, stroke=1)
        title = MONTHS_RU[month] if options.language == "Russian" else calendar.month_name[month]
        c.setFillColor(self.palette.ink)
        c.setFont(self.fonts["serif"], 40)
        c.drawCentredString(x + width / 2, title_y + 3.8 * mm, title)
        if options.custom_header or options.parish_name:
            c.setFont(self.fonts["sans"], 5.4)
            c.drawRightString(x + width - 2 * mm, title_y + 2 * mm, options.custom_header or options.parish_name)
        return title_y


class DayCellRenderer:
    def __init__(self, layout: ReferenceLayout, fonts: dict[str, str], palette: PublicationPalette, icons: IconRenderer):
        self.layout, self.fonts, self.palette, self.icons = layout, fonts, palette, icons

    @staticmethod
    def visual_state(day: CalendarDay) -> str:
        if day.service_rank.normalized_rank == ServiceRank.GREAT_FEAST or any(f.rank.value == "Great Feast" for f in day.feasts):
            return "great_feast"
        if day.service_rank.normalized_rank == ServiceRank.VIGIL or any("vigil" in f.liturgical_status.casefold() or "бден" in f.liturgical_status.casefold() for f in day.feasts):
            return "vigil"
        if day.fasting and day.fasting.level != FastLevel.FREE:
            return "fast_day"
        return "normal"

    def draw(self, c: Canvas, day: CalendarDay, x: float, y: float, w: float, h: float, options: PdfOptions) -> None:
        state = self.visual_state(day)
        background = self.palette.feast_wash if state in {"great_feast", "vigil"} else self.palette.strict if state == "fast_day" else self.palette.white
        c.setFillColor(background)
        c.rect(x + .25, y + .25, w - .5, h - .5, fill=1, stroke=0)
        pad = self.layout.cell_padding
        is_sunday = day.civil_date.weekday() == 6
        date_colour = self.palette.feast if state in {"great_feast", "vigil"} or is_sunday else self.palette.ink
        c.setFillColor(date_colour)
        c.setFont(self.fonts["serif"], 28)
        date_y = y + h - 9.5 * mm
        c.drawString(x + pad, date_y, str(day.civil_date.day))
        civil_w = pdfmetrics.stringWidth(str(day.civil_date.day), self.fonts["serif"], 28)
        if options.include_julian:
            c.setFont(self.fonts["serif"], 14)
            c.drawString(x + pad + civil_w + .5 * mm, date_y + .4 * mm, str(day.julian_date.day))

        fasting_symbols = self.icons.fasting_symbol_names(day) if options.include_fasting_icons else []
        if fasting_symbols:
            glyph = "🐟" if fasting_symbols[0] == "fish" else "🌢"
            colour = "#00AEEF" if fasting_symbols[0] == "fish" else "#FFC000"
            c.setFont(self.fonts["symbols"], 12.5)
            c.setFillColor(HexColor(colour))
            c.drawRightString(x + w - pad, y + h - 6.5 * mm, glyph)

        cursor = y + h - 13.0 * mm
        holiday_space = 6.0 * mm if options.include_holidays and day.public_holidays else 1.8 * mm
        bottom = y + holiday_space
        line_gap = 2.8 * mm
        text_width = w - 2 * pad
        if options.include_liturgical_week_tone and (day.liturgical_week or day.tone):
            tone = ("Глас " if options.language == "Russian" else "Tone ") + str(day.tone) if day.tone else ""
            week_tone = " · ".join(part for part in (day.liturgical_week, tone) if part)
            c.setFont(self.fonts["sans_bold"], 5.4)
            c.setFillColor(self.palette.ink)
            for line in TextFitter.lines(week_tone, self.fonts["sans_bold"], 5.4, text_width, 2):
                if cursor < bottom:
                    break
                c.drawString(x + pad, cursor, line)
                cursor -= line_gap

        entries: list[tuple[str, str, bool, ServiceRank]] = []
        day_rank = day.service_rank.normalized_rank
        day_rank_used = False
        for feast in day.feasts:
            rank = feast.service_rank
            if not symbol_for(rank) and not day_rank_used and symbol_for(day_rank):
                rank = day_rank; day_rank_used = True
            elif symbol_for(rank):
                day_rank_used = True
            entries.append((feast.name, "feast", feast.rank.value == "Great Feast", rank))
        for saint in ordered_selected_saints(day):
            rank = saint.service_rank
            if not symbol_for(rank) and not day_rank_used and is_primary_saint(day, saint) and symbol_for(day_rank):
                rank = day_rank; day_rank_used = True
            elif symbol_for(rank):
                day_rank_used = True
            entries.append((saint.display_name, "saint", is_primary_saint(day, saint) or rank in {ServiceRank.VIGIL, ServiceRank.POLYELEOS}, rank))
        for note in day.notes:
            entries.append((note, "note", False, ServiceRank.NONE))

        omitted = 0
        for text, kind, prominent, rank in entries:
            available = int((cursor - bottom) // line_gap)
            if available <= 0:
                omitted += 1
                continue
            major = kind == "feast" and (state in {"great_feast", "vigil"} or prominent)
            font = self.fonts["sans_bold"] if major or prominent or kind == "note" else self.fonts["sans"]
            size = 10 if major else 8
            glyph = symbol_for(rank) if options.include_service_rank_icons else ""
            symbol_size = 8
            symbol_advance = (pdfmetrics.stringWidth(glyph, self.fonts["symbols"], symbol_size) + .8 * mm) if glyph else 0
            lines = TextFitter.lines(text, font, size, text_width - symbol_advance, min(3 if major else 2, available))
            text_colour = self.palette.note if kind == "note" else (self.palette.feast if major or rank_text_is_red(rank) else self.palette.ink)
            for index, line in enumerate(lines):
                if cursor < bottom:
                    omitted += 1
                    break
                line_symbol = glyph if index == 0 else ""
                advance = symbol_advance if line_symbol else (symbol_advance if glyph and not major else 0)
                if major:
                    composite_width = pdfmetrics.stringWidth(line, font, size) + (symbol_advance if line_symbol else 0)
                    text_x = x + (w - composite_width) / 2 + (symbol_advance if line_symbol else 0)
                    symbol_x = x + (w - composite_width) / 2
                else:
                    symbol_x = x + pad
                    text_x = x + pad + advance
                if line_symbol:
                    c.setFont(self.fonts["symbols"], symbol_size)
                    c.setFillColor(HexColor("#" + symbol_colour_for(rank)))
                    c.drawString(symbol_x, cursor - .25, line_symbol)
                c.setFont(font, size)
                c.setFillColor(text_colour)
                c.drawString(text_x, cursor, line)
                cursor -= line_gap
        if omitted and cursor >= bottom:
            c.setFont(self.fonts["sans"], 7)
            c.setFillColor(self.palette.muted)
            c.drawString(x + pad, cursor, f"+{omitted} ещё" if options.language == "Russian" else f"+{omitted} more")

        if options.include_holidays and day.public_holidays:
            c.setFillColor(self.palette.holiday)
            c.setFont(self.fonts["sans_bold"], 8)
            lines = TextFitter.lines(day.public_holidays[0].name, self.fonts["sans_bold"], 8, text_width, 2)
            for index, line in enumerate(reversed(lines)):
                c.drawCentredString(x + w / 2, y + 1.8 * mm + index * 2.3 * mm, line)


class LegendRenderer:
    def __init__(self, layout: ReferenceLayout, fonts: dict[str, str], palette: PublicationPalette, icons: IconRenderer):
        self.layout, self.fonts, self.palette, self.icons = layout, fonts, palette, icons

    def draw(self, c: Canvas, x: float, y: float, width: float, options: PdfOptions) -> None:
        c.setFillColor(self.palette.white)
        c.rect(x, y, width, self.layout.footer_height, fill=1, stroke=1)
        cursor = x + 2 * mm
        c.setFont(self.fonts["sans"], 4.7)
        if options.include_fasting_legend:
            c.setFillColor(self.palette.strict)
            c.rect(cursor, y + .8 * mm, 2.4 * mm, 2.4 * mm, fill=1, stroke=1)
            c.setFillColor(self.palette.ink)
            c.drawString(cursor + 3.2 * mm, y + 1.2 * mm, "Строгий пост" if options.language == "Russian" else "Strict fast")
            cursor += 24 * mm
            c.setFont(self.fonts["symbols"], 7.5)
            c.setFillColor(HexColor("#00AEEF")); c.drawString(cursor, y + 1.0 * mm, "🐟")
            c.setFillColor(HexColor("#FFC000")); c.drawString(cursor + 4 * mm, y + 1.0 * mm, "🌢")
            cursor += 8 * mm
            c.setFillColor(self.palette.ink); c.setFont(self.fonts["sans"], 4.7)
            c.drawString(cursor, y + 1.2 * mm, "разрешается" if options.language == "Russian" else "permitted")
            cursor += 19 * mm
        if options.include_service_rank_legend:
            for rank, name in ((ServiceRank.GREAT_FEAST, "great_feast"), (ServiceRank.VIGIL, "vigil"), (ServiceRank.POLYELEOS, "polyeleos"), (ServiceRank.DOXOLOGY, "doxology"), (ServiceRank.SIX_STICHERA, "six_stichera"), (ServiceRank.NO_SIGN, "no_sign")):
                if cursor > x + width - 28 * mm:
                    break
                glyph = symbol_for(rank)
                if glyph:
                    c.setFont(self.fonts["symbols"], 7.0); c.setFillColor(HexColor("#" + symbol_colour_for(rank)))
                    c.drawString(cursor, y + 1.0 * mm, glyph)
                label = legend_label_for(rank, options.language, options.rank_labels_en, options.rank_labels_ru)
                c.setFillColor(self.palette.ink)
                c.setFont(self.fonts["sans"], 4.35)
                c.drawString(cursor + (3.5 * mm if glyph else 0), y + 1.2 * mm, label)
                cursor += max(20 * mm, pdfmetrics.stringWidth(label, self.fonts["sans"], 4.35) + 5 * mm)

    def draw_integrated(self, c: Canvas, x: float, y: float, width: float, height: float, options: PdfOptions, kind: str) -> None:
        c.setFillColor(self.palette.white)
        c.rect(x, y, width, height, fill=1, stroke=1)
        cursor_y = y + height - 5 * mm
        left = x + 3 * mm
        c.setFillColor(self.palette.ink)
        c.setFont(self.fonts["sans"], 6.0)
        if kind == "fasting":
            entries = [("strict_fast", "Строгий пост" if options.language == "Russian" else "Strict fast"), ("oil", "Разрешается пост. масло" if options.language == "Russian" else "Oil permitted"), ("fish", "Разрешается рыба" if options.language == "Russian" else "Fish permitted")]
            for name, label in entries:
                if cursor_y < y + 3 * mm:
                    break
                if name == "strict_fast":
                    c.setFillColor(self.palette.strict); c.rect(left, cursor_y - .8 * mm, 3 * mm, 3 * mm, fill=1, stroke=1)
                else:
                    glyph = "🐟" if name == "fish" else "🌢"
                    c.setFont(self.fonts["symbols"], 8.0); c.setFillColor(HexColor("#00AEEF" if name == "fish" else "#FFC000"))
                    c.drawString(left, cursor_y - .3 * mm, glyph)
                c.setFillColor(self.palette.ink); c.setFont(self.fonts["sans"], 6.0); c.drawString(left + 5 * mm, cursor_y, label)
                cursor_y -= 5 * mm
            return
        entries = ((ServiceRank.GREAT_FEAST, "great_feast"), (ServiceRank.VIGIL, "vigil"), (ServiceRank.POLYELEOS, "polyeleos"), (ServiceRank.DOXOLOGY, "doxology"), (ServiceRank.SIX_STICHERA, "six_stichera"), (ServiceRank.NO_SIGN, "no_sign"))
        for rank, name in entries:
            if cursor_y < y + 2 * mm:
                break
            glyph = symbol_for(rank)
            if glyph:
                c.setFont(self.fonts["symbols"], 8.0); c.setFillColor(HexColor("#" + symbol_colour_for(rank)))
                c.drawString(left, cursor_y - .3 * mm, glyph)
            label = legend_label_for(rank, options.language, options.rank_labels_en, options.rank_labels_ru)
            c.setFillColor(self.palette.ink); c.setFont(self.fonts["sans"], 6.0); c.drawString(left + (5 * mm if glyph else 0), cursor_y, label)
            cursor_y -= 4.2 * mm


class MonthRenderer:
    def __init__(self, layout: ReferenceLayout, fonts: dict[str, str], palette: PublicationPalette, icons: IconRenderer):
        self.layout, self.fonts, self.palette = layout, fonts, palette
        self.header = HeaderRenderer(layout, fonts, palette)
        self.cell = DayCellRenderer(layout, fonts, palette, icons)
        self.legend = LegendRenderer(layout, fonts, palette, icons)

    def draw(self, c: Canvas, page_size: tuple[float, float], days: list[CalendarDay], month: int, page: int, total: int, options: PdfOptions) -> None:
        page_w, page_h = page_size
        x = self.layout.margin_left
        width = page_w - self.layout.margin_left - self.layout.margin_right
        top = page_h - self.layout.margin_top
        grid_top = self.header.draw(c, x, top, width, month, options)
        grid_bottom = self.layout.margin_bottom
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(options.year, month)
        cell_w, cell_h = width / 7, (grid_top - grid_bottom) / len(weeks)
        by_day = {day.civil_date.day: day for day in days}
        c.setStrokeColor(self.palette.ink)
        c.setLineWidth(self.layout.border_width)
        for row, week in enumerate(weeks):
            y = grid_top - (row + 1) * cell_h
            for col, number in enumerate(week):
                cell_x = x + col * cell_w
                c.rect(cell_x, y, cell_w, cell_h, fill=0, stroke=1)
                if number in by_day:
                    self.cell.draw(c, by_day[number], cell_x, y, cell_w, cell_h, options)
        leading = next((index for index, number in enumerate(weeks[0]) if number), 7)
        if leading and options.include_fasting_legend:
            self.legend.draw_integrated(c, x, grid_top - cell_h, leading * cell_w, cell_h, options, "fasting")
        trailing = next((index for index, number in enumerate(reversed(weeks[-1])) if number), 7)
        if trailing and options.include_service_rank_legend:
            self.legend.draw_integrated(c, x + (7 - trailing) * cell_w, grid_bottom, trailing * cell_w, cell_h, options, "rank")
        c.setFillColor(self.palette.muted)
        c.setFont(self.fonts["sans"], 8)
        footer = options.custom_footer or f"Russian Orthodox Calendar {options.year} - {options.jurisdiction}"
        c.drawCentredString(x + width / 2, 1.5 * mm, footer)


class PdfRenderer:
    def __init__(self):
        self.layout = REFERENCE_LAYOUT
        self.palette = PublicationPalette()
        self.fonts = self._register_fonts()
        icon_renderer = IconRenderer(self.layout)
        self.month_renderer = MonthRenderer(self.layout, self.fonts, self.palette, icon_renderer)
        self.regular, self.bold = self.fonts["sans"], self.fonts["sans_bold"]
        self.rank_icons, self.icons = icon_renderer.rank, icon_renderer.fasting

    @staticmethod
    def _register_fonts() -> dict[str, str]:
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        candidates = {
            "sans": (("ArialNarrow", fonts_dir / "ARIALN.TTF"), ("NotoSans", asset_path("fonts", "NotoSans-Regular.ttf"))),
            "sans_bold": (("ArialNarrow-Bold", fonts_dir / "ARIALNB.TTF"), ("NotoSans-Bold", asset_path("fonts", "NotoSans-Bold.ttf"))),
            "serif": (("TimesNewRoman", fonts_dir / "times.ttf"), ("NotoSerif", asset_path("fonts", "NotoSerif-Regular.ttf"))),
            "serif_bold": (("TimesNewRoman-Bold", fonts_dir / "timesbd.ttf"), ("NotoSerif-Bold", asset_path("fonts", "NotoSerif-Bold.ttf"))),
            "symbols": (("SegoeUISymbol", fonts_dir / "seguisym.ttf"),),
        }
        result: dict[str, str] = {}
        for key, choices in candidates.items():
            name, path = next(((name, path) for name, path in choices if path.exists()), ("", Path()))
            if name and name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
            result[key] = name or ("Helvetica-Bold" if "bold" in key else "Helvetica")
        return result

    visual_state = staticmethod(DayCellRenderer.visual_state)
    permission_icons = staticmethod(IconRenderer.permissions)
    rank_icon_name = staticmethod(IconRenderer.rank_name)

    def render(self, output: Path, days: list[CalendarDay], options: PdfOptions) -> Path:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        page_size = landscape(A4) if options.orientation == "Landscape" else A4
        c = Canvas(str(output), pagesize=page_size, pageCompression=1)
        title = "Русский православный календарь" if options.language == "Russian" else "Russian Orthodox Calendar"
        c.setTitle(f"{title} {options.year} - {options.jurisdiction}")
        c.setAuthor("Russian Orthodox Calendar Generator")
        c.setSubject("Russian Orthodox Church Liturgical Calendar")
        c.setCreator(f"Russian Orthodox Calendar Generator {__version__}")
        for page, month in enumerate(options.months, 1):
            month_days = [day for day in days if day.civil_date.month == month]
            self.month_renderer.draw(c, page_size, month_days, month, page, len(options.months), options)
            c.showPage()
        c.save()
        return output
