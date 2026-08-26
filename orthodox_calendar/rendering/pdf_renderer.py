from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from pathlib import Path

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
from .templates import STYLES


MONTHS_RU = ("", "ЯНВАРЬ", "ФЕВРАЛЬ", "МАРТ", "АПРЕЛЬ", "МАЙ", "ИЮНЬ", "ИЮЛЬ", "АВГУСТ", "СЕНТЯБРЬ", "ОКТЯБРЬ", "НОЯБРЬ", "ДЕКАБРЬ")
MONTHS_RU_SHORT = ("", "янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек")


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


class PdfRenderer:
    def __init__(self):
        self.regular, self.bold = "Helvetica", "Helvetica-Bold"
        regular, bold = asset_path("fonts", "NotoSans-Regular.ttf"), asset_path("fonts", "NotoSans-Bold.ttf")
        if regular.exists() and bold.exists():
            if "NotoSans" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("NotoSans", regular)); pdfmetrics.registerFont(TTFont("NotoSans-Bold", bold))
            self.regular, self.bold = "NotoSans", "NotoSans-Bold"
        self.icons = {name: ImageReader(str(asset_path("icons", f"{name}.png"))) for name in ("fish", "wine", "oil", "strict_fast", "feast", "vigil", "holiday") if asset_path("icons", f"{name}.png").exists()}
        self.rank_icons = {name: ImageReader(str(asset_path("icons", "rank", f"{name}.png"))) for name in ("great_feast", "vigil", "polyeleos", "doxology", "six_stichera", "no_sign") if asset_path("icons", "rank", f"{name}.png").exists()}

    @staticmethod
    def _fit(text: str, max_chars: int) -> str:
        text = " ".join(text.split()); return text if len(text) <= max_chars else text[:max(1, max_chars - 3)].rstrip() + "..."

    @staticmethod
    def _fit_width(text: str, font: str, size: float, width: float) -> str:
        text = " ".join(text.split())
        if pdfmetrics.stringWidth(text, font, size) <= width:
            return text
        suffix, low, high = "...", 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if pdfmetrics.stringWidth(text[:middle].rstrip() + suffix, font, size) <= width: low = middle
            else: high = middle - 1
        return text[:low].rstrip() + suffix

    @staticmethod
    def visual_state(day: CalendarDay) -> str:
        if day.service_rank.normalized_rank == ServiceRank.GREAT_FEAST or any(feast.rank.value == "Great Feast" for feast in day.feasts):
            return "great_feast"
        if day.service_rank.normalized_rank == ServiceRank.VIGIL or any("rank 5" in feast.liturgical_status.casefold() or "vigil" in feast.liturgical_status.casefold() or "бден" in feast.liturgical_status.casefold() for feast in day.feasts):
            return "vigil"
        if day.fasting and day.fasting.level == FastLevel.STRICT:
            return "strict_fast"
        return "normal"

    @staticmethod
    def permission_icons(day_or_fasting) -> list[str]:
        fasting = getattr(day_or_fasting, "fasting", day_or_fasting)
        if not fasting or fasting.level == FastLevel.FREE:
            return []
        text = f"{fasting.period} {fasting.detail}".casefold()
        result: list[str] = []
        if "fish" in text or "рыб" in text: result.append("fish")
        if "wine" in text or "вино" in text: result.append("wine")
        explicit_oil = "food with oil" in text or "oil permitted" in text or "еле" in text or "масл" in text
        if explicit_oil: result.append("oil")
        if fasting.level == FastLevel.WINE_OIL and not any(value in result for value in ("wine", "oil")):
            result.extend(["wine", "oil"])
        if fasting.level == FastLevel.STRICT: result.append("strict_fast")
        return result

    @staticmethod
    def rank_icon_name(day: CalendarDay) -> str | None:
        return {
            ServiceRank.GREAT_FEAST: "great_feast", ServiceRank.VIGIL: "vigil",
            ServiceRank.POLYELEOS: "polyeleos", ServiceRank.DOXOLOGY: "doxology",
            ServiceRank.SIX_STICHERA: "six_stichera", ServiceRank.NO_SIGN: "no_sign",
        }.get(day.service_rank.normalized_rank)

    def render(self, output: Path, days: list[CalendarDay], options: PdfOptions) -> Path:
        output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
        page_size = landscape(A4) if options.orientation == "Landscape" else A4
        c = Canvas(str(output), pagesize=page_size, pageCompression=1)
        russian = options.language == "Russian"
        c.setTitle(("Русский православный календарь" if russian else "Russian Orthodox Calendar") + f" {options.year} - {options.jurisdiction}")
        c.setAuthor("Russian Orthodox Calendar Generator"); c.setSubject("Russian Orthodox Church Liturgical Calendar"); c.setCreator(f"Russian Orthodox Calendar Generator {__version__}")
        for page, month in enumerate(options.months, 1):
            month_days = [day for day in days if day.civil_date.month == month]
            self._draw_month(c, page_size, month_days, month, page, len(options.months), options); c.showPage()
        c.save(); return output

    def _draw_month(self, c: Canvas, page_size, days: list[CalendarDay], month: int, page: int, total: int, options: PdfOptions) -> None:
        width, height = page_size; style = STYLES.get(options.template, STYLES["Traditional"]); russian = options.language == "Russian"
        margin = 10 * mm if options.orientation == "Landscape" else 9 * mm
        header_h = 20 * mm if options.orientation == "Landscape" else 27 * mm
        legend_rows = int(options.include_fasting_legend) + int(options.include_service_rank_legend)
        footer_h = (10 + 5 * legend_rows) * mm
        grid_x, grid_y = margin, margin + footer_h
        grid_w, grid_h = width - 2 * margin, height - 2 * margin - header_h - footer_h
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(options.year, month)
        cell_w, cell_h = grid_w / 7, grid_h / len(weeks)

        c.setFillColor(style.pale); c.rect(0, height - margin - header_h, width, header_h + margin, fill=1, stroke=0)
        c.setStrokeColor(style.accent); c.setLineWidth(2.0); c.line(margin, height - margin - header_h + 1.8 * mm, width - margin, height - margin - header_h + 1.8 * mm)
        c.setFillColor(style.accent); c.setFont(self.bold, 20 if options.orientation == "Landscape" else 22)
        title = MONTHS_RU[month] if russian else calendar.month_name[month].upper(); c.drawString(margin, height - margin - 10 * mm, title)
        c.setFillColor(style.ink); c.setFont(self.regular, 10); c.drawRightString(width - margin, height - margin - 6 * mm, str(options.year))
        c.setFont(self.regular, 7.2); publication = options.custom_header or options.parish_name or ("РУССКИЙ ПРАВОСЛАВНЫЙ КАЛЕНДАРЬ" if russian else "RUSSIAN ORTHODOX CALENDAR")
        c.drawRightString(width - margin, height - margin - 11 * mm, self._fit(publication, 75))
        civil = "Григорианские гражданские даты" if russian else "Civil dates are Gregorian"
        c.setFont(self.regular, 6.2); c.drawRightString(width - margin, height - margin - 16 * mm, f"{options.jurisdiction} | {civil}")

        weekdays = ("ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС") if russian else ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
        c.setFillColor(style.ink); c.setFont(self.bold, 7)
        for col, label in enumerate(weekdays): c.drawCentredString(grid_x + (col + .5) * cell_w, grid_y + grid_h + 2.1 * mm, label)

        by_number = {day.civil_date.day: day for day in days}
        for row, week in enumerate(weeks):
            for col, number in enumerate(week):
                x, y = grid_x + col * cell_w, grid_y + (len(weeks) - 1 - row) * cell_h
                c.setStrokeColor(style.ink); c.setLineWidth(style.border_width); c.rect(x, y, cell_w, cell_h, fill=0, stroke=1)
                if number and number in by_number: self._draw_day(c, by_number[number], x, y, cell_w, cell_h, col == 6, options, style)

        self._draw_footer(c, width, margin, options, days, page, total, style)

    def _draw_day(self, c: Canvas, day: CalendarDay, x: float, y: float, w: float, h: float, sunday: bool, options: PdfOptions, style) -> None:
        pad, russian = 1.15 * mm, options.language == "Russian"; state = self.visual_state(day)
        background = {"great_feast": style.great_feast_background, "vigil": style.vigil_background, "strict_fast": style.strict_fast_background}.get(state, style.pale if sunday else style.normal_background)
        c.setFillColor(background); c.rect(x + .35, y + .35, w - .7, h - .7, fill=1, stroke=0)
        feast_state = state in {"great_feast", "vigil"}
        c.setFillColor(style.feast_text if feast_state else (style.accent if sunday else style.ink)); c.setFont(self.bold, 9.2); c.drawString(x + pad, y + h - 4 * mm, str(day.civil_date.day))
        if options.include_service_rank_icons and (rank_icon := self.rank_icon_name(day)) in self.rank_icons:
            c.drawImage(self.rank_icons[rank_icon], x + pad + 7 * mm, y + h - 6.2 * mm, 4.2 * mm, 4.2 * mm, mask="auto", preserveAspectRatio=True)
        if options.include_julian:
            month_abbr = MONTHS_RU_SHORT[day.julian_date.month] if russian else calendar.month_abbr[day.julian_date.month]
            c.setFillColor(style.secondary_text); c.setFont(self.regular, 4.8); c.drawRightString(x + w - pad, y + h - 3.6 * mm, f"O.S. {day.julian_date.day} {month_abbr}")
        if day.tone:
            tone = f"Глас {day.tone}" if russian else f"Tone {day.tone}"
            c.setFont(self.regular, 4.7); c.drawRightString(x + w - pad, y + h - 6 * mm, tone)

        cursor, bottom_limit = y + h - 8 * mm, y + 7 * mm
        visible_saints = [saint for saint in day.saints if saint.selected]
        lines: list[tuple[str, str]] = [("feast", feast.name) for feast in day.feasts[:2]] + [("saint", saint.display_name) for saint in visible_saints[:3]]
        hidden = max(0, len(day.feasts) - 2) + max(0, len(visible_saints) - 3)
        if hidden: lines.append(("more", (f"+{hidden} ещё" if russian else f"+{hidden} more")))
        if options.include_holidays and day.public_holidays: lines.append(("holiday", ("ГРАЖД.: " if russian else "CIVIL: ") + day.public_holidays[0].name))
        for kind, text in lines:
            if cursor < bottom_limit: break
            font = self.bold if kind in {"feast", "holiday"} else self.regular; size = 5.0
            c.setFont(font, size); c.setFillColor(style.feast_text if kind == "feast" else (style.holiday_indicator if kind == "holiday" else style.ink))
            c.drawString(x + pad, cursor, self._fit_width(text, font, size, w - 2 * pad)); cursor -= 2.25 * mm

        fasting = day.fasting
        if fasting and fasting.level != FastLevel.FREE:
            label = fasting.period or fasting.level.value
            if russian and re.search(r"[A-Za-z]", label) and not re.search(r"[А-Яа-яЁё]", label):
                label = "EN source: " + label
            c.setFillColor(style.ink); c.setFont(self.bold, 4.9)
            icon_names = self.permission_icons(fasting) if options.include_fasting_icons else []
            icon_w = len(icon_names) * 3.7 * mm
            c.drawString(x + pad, y + 1.8 * mm, self._fit_width(label, self.bold, 4.9, w - 2 * pad - icon_w))
            self._draw_icons(c, icon_names, x + w - pad - icon_w, y + .8 * mm, 3.2 * mm)

    def _draw_icons(self, c: Canvas, names: list[str], x: float, y: float, size: float) -> None:
        for index, name in enumerate(names):
            if name in self.icons: c.drawImage(self.icons[name], x + index * (size + .45 * mm), y, size, size, mask="auto", preserveAspectRatio=True)

    def _draw_footer(self, c: Canvas, width: float, margin: float, options: PdfOptions, days: list[CalendarDay], page: int, total: int, style) -> None:
        russian = options.language == "Russian"
        if options.include_fasting_legend:
            y = margin + (12.2 if options.include_service_rank_legend else 7.2) * mm; c.setFont(self.regular, 5.2); c.setFillColor(style.ink)
            strict_label = "строгий пост" if russian else "strict fast"; permission_label = "разрешено" if russian else "permitted"; holiday_label = "гражданский праздник" if russian else "civil holiday"
            c.setFillColor(style.strict_fast_background); c.rect(margin, y - .8 * mm, 4 * mm, 3 * mm, fill=1, stroke=1); c.setFillColor(style.ink); c.drawString(margin + 5 * mm, y, strict_label)
            cursor = margin + 30 * mm; icon_names = [name for name in ("fish", "wine", "oil") if name in self.icons]; self._draw_icons(c, icon_names, cursor, y - 1.5 * mm, 3 * mm)
            cursor += len(icon_names) * 3.5 * mm; c.drawString(cursor, y, permission_label)
            cursor += 21 * mm; self._draw_icons(c, ["holiday"], cursor, y - 1.5 * mm, 3 * mm); c.drawString(cursor + 4 * mm, y, holiday_label)
            cursor += 30 * mm; c.setFillColor(style.great_feast_background); c.rect(cursor, y - .8 * mm, 4 * mm, 3 * mm, fill=1, stroke=1); c.setFillColor(style.feast_text); c.drawString(cursor + 5 * mm, y, "бдение / великий праздник" if russian else "vigil / Great Feast")

        if options.include_service_rank_legend:
            y = margin + 7.2 * mm; cursor = margin; c.setFont(self.regular, 4.7); c.setFillColor(style.ink)
            rank_entries = (
                (ServiceRank.GREAT_FEAST, "great_feast"), (ServiceRank.VIGIL, "vigil"),
                (ServiceRank.POLYELEOS, "polyeleos"), (ServiceRank.DOXOLOGY, "doxology"),
                (ServiceRank.SIX_STICHERA, "six_stichera"), (ServiceRank.NO_SIGN, "no_sign"),
            )
            for rank, icon_name in rank_entries:
                if icon_name in self.rank_icons:
                    c.drawImage(self.rank_icons[icon_name], cursor, y - 1.7 * mm, 3.2 * mm, 3.2 * mm, mask="auto", preserveAspectRatio=True)
                label = localized_rank_name(ServiceRankInfo(normalized_rank=rank), options.language, options.rank_labels_en, options.rank_labels_ru)
                c.setFillColor(style.ink); c.drawString(cursor + 3.8 * mm, y, label)
                cursor += max(30 * mm, pdfmetrics.stringWidth(label, self.regular, 4.7) + 7 * mm)

        availability = bool(days) and all(day.authoritative_data_available for day in days)
        if russian:
            status = "Данные Свято-Троицкого календаря загружены - сверяйте с официальным календарём" if availability else "НЕТ ДАННЫХ О СВЯТЫХ - только расчётные праздники и посты; требуется проверка"
            standard_footer = "Календарь: Holy Trinity Orthodox Calendar | Гражданские праздники: Australia | Не является церковным авторитетом."
        else:
            status = "Holy Trinity source data loaded - verify against the current official calendar" if availability else "SAINT DATA NOT AVAILABLE - calculated feasts/fasts only; verify before liturgical use"
            standard_footer = "Calendar: Holy Trinity Orthodox Calendar | Civil holidays: Australia | Not ecclesiastical authority."
        y = margin + 3.2 * mm; c.setFillColor(style.ink); c.setFont(self.bold if not availability else self.regular, 5.2); c.drawString(margin, y, self._fit(status, 105))
        footer = options.custom_footer or (standard_footer if options.include_sources else ("Внешние данные требуют проверки." if russian else "External calendar information requires verification."))
        c.setFont(self.regular, 4.9); c.drawRightString(width - margin, y, self._fit(footer, 108))
        page_label = f"Страница {page} из {total}" if russian else f"Page {page} of {total}"; c.drawRightString(width - margin, margin - .5 * mm, page_label)
