from __future__ import annotations

import calendar
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
from orthodox_calendar.models import CalendarDay, FastLevel, ServiceRank, ServiceRankInfo
from orthodox_calendar.paths import asset_path
from orthodox_calendar.service_ranks import localized_rank_name
from .layout import REFERENCE_LAYOUT, ReferenceLayout


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
    sunday = HexColor("#C00000")
    weekday = HexColor("#006FEF")
    strict = HexColor("#C7C7C7")
    feast_wash = HexColor("#F8CACA")
    feast = HexColor("#D00000")
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
        return {ServiceRank.GREAT_FEAST: "great_feast", ServiceRank.VIGIL: "vigil", ServiceRank.POLYELEOS: "polyeleos", ServiceRank.DOXOLOGY: "doxology", ServiceRank.SIX_STICHERA: "six_stichera", ServiceRank.NO_SIGN: "no_sign"}.get(day.service_rank.normalized_rank)

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
            c.setFont(self.fonts["sans_bold"], 7.5)
            c.drawCentredString(x + (index + .5) * col, top - 3.25 * mm, label)
        title_y = top - self.layout.weekday_height - self.layout.title_height
        c.setFillColor(self.palette.white)
        c.rect(x, title_y, width, self.layout.title_height, fill=1, stroke=1)
        title = MONTHS_RU[month] if options.language == "Russian" else calendar.month_name[month]
        c.setFillColor(self.palette.ink)
        c.setFont(self.fonts["serif"], 28)
        c.drawCentredString(x + width / 2, title_y + 4.0 * mm, title)
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
        if day.fasting and day.fasting.level == FastLevel.STRICT:
            return "strict_fast"
        return "normal"

    def draw(self, c: Canvas, day: CalendarDay, x: float, y: float, w: float, h: float, options: PdfOptions) -> None:
        state = self.visual_state(day)
        background = self.palette.feast_wash if state in {"great_feast", "vigil"} else self.palette.strict if state == "strict_fast" else self.palette.white
        c.setFillColor(background)
        c.rect(x + .25, y + .25, w - .5, h - .5, fill=1, stroke=0)
        pad = self.layout.cell_padding
        is_sunday = day.civil_date.weekday() == 6
        date_colour = self.palette.feast if state in {"great_feast", "vigil"} or is_sunday else self.palette.ink
        c.setFillColor(date_colour)
        c.setFont(self.fonts["serif"], 21)
        date_y = y + h - 7.7 * mm
        c.drawString(x + pad, date_y, str(day.civil_date.day))
        civil_w = pdfmetrics.stringWidth(str(day.civil_date.day), self.fonts["serif"], 21)
        if options.include_julian:
            c.setFont(self.fonts["serif"], 9)
            c.drawString(x + pad + civil_w + .5 * mm, date_y + .4 * mm, str(day.julian_date.day))

        right = x + w - pad
        rank = self.icons.rank_name(day)
        if options.include_service_rank_icons and rank in self.icons.rank:
            right -= self.layout.rank_icon_size
            IconRenderer.draw(c, self.icons.rank, [rank], right, y + h - 6.9 * mm, self.layout.rank_icon_size)
            right -= .7 * mm
        fasting_icons = self.icons.permissions(day) if options.include_fasting_icons else []
        fasting_icons = [name for name in fasting_icons if name != "strict_fast"]
        if fasting_icons:
            icons_width = len(fasting_icons) * self.layout.fasting_icon_size * 1.08
            right -= icons_width
            IconRenderer.draw(c, self.icons.fasting, fasting_icons, right, y + h - 6.5 * mm, self.layout.fasting_icon_size)

        cursor = y + h - 10.1 * mm
        holiday_space = 6.0 * mm if options.include_holidays and day.public_holidays else 1.8 * mm
        bottom = y + holiday_space
        line_gap = 2.55 * mm
        text_width = w - 2 * pad
        entries: list[tuple[str, str, bool]] = []
        for feast in day.feasts:
            entries.append((feast.name, "feast", feast.rank.value == "Great Feast"))
        for saint in (saint for saint in day.saints if saint.selected):
            entries.append((saint.display_name, "saint", saint.service_rank in {ServiceRank.VIGIL, ServiceRank.POLYELEOS}))
        for note in day.notes:
            entries.append((note, "note", False))

        omitted = 0
        for text, kind, prominent in entries:
            available = int((cursor - bottom) // line_gap)
            if available <= 0:
                omitted += 1
                continue
            major = kind == "feast" and (state in {"great_feast", "vigil"} or prominent)
            font = self.fonts["sans_bold"] if major or kind == "note" else self.fonts["sans"]
            size = 6.4 if major else (5.5 if kind == "note" else 5.75)
            lines = TextFitter.lines(text, font, size, text_width, min(3 if major else 2, available))
            c.setFillColor(self.palette.note if kind == "note" else (self.palette.feast if major or prominent else self.palette.ink))
            c.setFont(font, size)
            for line in lines:
                if cursor < bottom:
                    omitted += 1
                    break
                (c.drawCentredString(x + w / 2, cursor, line) if major else c.drawString(x + pad, cursor, line))
                cursor -= line_gap
        if omitted and cursor >= bottom:
            c.setFont(self.fonts["sans"], 5.2)
            c.setFillColor(self.palette.muted)
            c.drawString(x + pad, cursor, f"+{omitted} ещё" if options.language == "Russian" else f"+{omitted} more")

        if options.include_holidays and day.public_holidays:
            c.setFillColor(self.palette.holiday)
            c.setFont(self.fonts["sans_bold"], 5.5)
            lines = TextFitter.lines(day.public_holidays[0].name, self.fonts["sans_bold"], 5.5, text_width, 2)
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
            names = [name for name in ("fish", "wine", "oil") if name in self.icons.fasting]
            IconRenderer.draw(c, self.icons.fasting, names, cursor, y + .3 * mm, 3 * mm)
            cursor += len(names) * 3.3 * mm
            c.drawString(cursor, y + 1.2 * mm, "разрешается" if options.language == "Russian" else "permitted")
            cursor += 19 * mm
        if options.include_service_rank_legend:
            for rank, name in ((ServiceRank.GREAT_FEAST, "great_feast"), (ServiceRank.VIGIL, "vigil"), (ServiceRank.POLYELEOS, "polyeleos"), (ServiceRank.DOXOLOGY, "doxology"), (ServiceRank.SIX_STICHERA, "six_stichera"), (ServiceRank.NO_SIGN, "no_sign")):
                if cursor > x + width - 28 * mm:
                    break
                IconRenderer.draw(c, self.icons.rank, [name], cursor, y + .3 * mm, 3 * mm)
                label = localized_rank_name(ServiceRankInfo(normalized_rank=rank), options.language, options.rank_labels_en, options.rank_labels_ru)
                c.setFillColor(self.palette.ink)
                c.setFont(self.fonts["sans"], 4.35)
                c.drawString(cursor + 3.5 * mm, y + 1.2 * mm, label)
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
                    IconRenderer.draw(c, self.icons.fasting, [name], left, cursor_y - 1.2 * mm, 3.4 * mm)
                c.setFillColor(self.palette.ink); c.drawString(left + 5 * mm, cursor_y, label)
                cursor_y -= 5 * mm
            return
        entries = ((ServiceRank.GREAT_FEAST, "great_feast"), (ServiceRank.VIGIL, "vigil"), (ServiceRank.POLYELEOS, "polyeleos"), (ServiceRank.DOXOLOGY, "doxology"), (ServiceRank.SIX_STICHERA, "six_stichera"), (ServiceRank.NO_SIGN, "no_sign"))
        for rank, name in entries:
            if cursor_y < y + 2 * mm:
                break
            IconRenderer.draw(c, self.icons.rank, [name], left, cursor_y - 1.2 * mm, 3.4 * mm)
            label = localized_rank_name(ServiceRankInfo(normalized_rank=rank), options.language, options.rank_labels_en, options.rank_labels_ru)
            c.setFillColor(self.palette.ink); c.drawString(left + 5 * mm, cursor_y, label)
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
        c.setFont(self.fonts["sans"], 4.0)
        footer = options.custom_footer or ("Данные требуют проверки по официальному церковному календарю." if options.language == "Russian" else "Verify calendar data against the current official church calendar.")
        c.drawString(x, 1.6 * mm, footer)
        c.drawRightString(x + width, 1.6 * mm, f"{page}/{total} | {options.year} | {options.jurisdiction}")


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
        definitions = {"sans": ("NotoSans", asset_path("fonts", "NotoSans-Regular.ttf")), "sans_bold": ("NotoSans-Bold", asset_path("fonts", "NotoSans-Bold.ttf")), "serif": ("NotoSerif", asset_path("fonts", "NotoSerif-Regular.ttf")), "serif_bold": ("NotoSerif-Bold", asset_path("fonts", "NotoSerif-Bold.ttf"))}
        for name, path in definitions.values():
            if path.exists() and name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
        return {key: name if path.exists() else ("Helvetica-Bold" if "bold" in key else "Helvetica") for key, (name, path) in definitions.items()}

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
