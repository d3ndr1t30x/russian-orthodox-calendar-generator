from __future__ import annotations

import calendar
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from orthodox_calendar import __version__
from orthodox_calendar.models import CalendarDay, FastLevel, ServiceRank
from orthodox_calendar.service_ranks import (
    legend_label_for, localized_rank_name, rank_text_is_red, symbol_colour_for, symbol_for,
)
from .pdf_renderer import IconRenderer, PdfOptions, PdfRenderer
from .publication import is_primary_saint, ordered_selected_saints


MONTHS_RU = ("", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")
WEEKDAYS_EN = ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")
WEEKDAYS_RU = ("ВОСК", "ПОН", "ВТОР", "СРЕД", "ЧЕТ", "ПЯТ", "СУБ")


def _set_cell_shading(cell, colour: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr(); shading = tc_pr.find(qn("w:shd"))
    if shading is None:
        shading = OxmlElement("w:shd"); tc_pr.append(shading)
    shading.set(qn("w:fill"), colour)


def _set_cell_margins(cell, value_dxa: int = 115) -> None:
    tc_pr = cell._tc.get_or_add_tcPr(); margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar"); tc_pr.append(margins)
    for edge in ("top", "left", "bottom", "right"):
        node = margins.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}"); margins.append(node)
        node.set(qn("w:w"), str(value_dxa)); node.set(qn("w:type"), "dxa")


def _prevent_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    if tr_pr.find(qn("w:cantSplit")) is None:
        tr_pr.append(OxmlElement("w:cantSplit"))


def _set_table_geometry(table, total_width_dxa: int) -> None:
    table.autofit = False; column_width = total_width_dxa // 7
    tbl_pr = table._tbl.tblPr; layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout"); tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")
    width = tbl_pr.find(qn("w:tblW"))
    if width is None:
        width = OxmlElement("w:tblW"); tbl_pr.append(width)
    width.set(qn("w:w"), str(total_width_dxa)); width.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid): grid.remove(child)
    for _ in range(7):
        col = OxmlElement("w:gridCol"); col.set(qn("w:w"), str(column_width)); grid.append(col)
    for row in table.rows:
        for cell in row.cells:
            tc_w = cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
            if tc_w is None:
                tc_w = OxmlElement("w:tcW"); cell._tc.get_or_add_tcPr().append(tc_w)
            tc_w.set(qn("w:w"), str(column_width)); tc_w.set(qn("w:type"), "dxa")


def _format_run(run, size: float, bold: bool = False, colour: str = "111111", font: str = "Arial Narrow") -> None:
    run.font.name = font; run.font.size = Pt(size); run.bold = bold; run.font.color.rgb = RGBColor.from_string(colour)
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn("w:ascii"), font); r_fonts.set(qn("w:hAnsi"), font); r_fonts.set(qn("w:eastAsia"), font)


def _format_symbol_run(run, size: float, colour: str, emoji: bool = False) -> None:
    font = "Segoe UI Emoji" if emoji else "Arial Narrow"
    run.font.name = font; run.font.size = Pt(size); run.font.color.rgb = RGBColor.from_string(colour)
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn("w:ascii"), font); r_fonts.set(qn("w:hAnsi"), font)
    r_fonts.set(qn("w:cs"), "Segoe UI Symbol")


def _add_ranked_text(paragraph, text: str, rank: ServiceRank, size: float = 8, bold: bool = False, colour: str = "111111") -> None:
    glyph = symbol_for(rank)
    if glyph:
        _format_symbol_run(paragraph.add_run(glyph), size, symbol_colour_for(rank))
        _format_run(paragraph.add_run(" "), size, colour=colour)
    text_colour = "C00000" if rank_text_is_red(rank) else colour
    _format_run(paragraph.add_run(text), size, bold, text_colour)


def _add_shaded_swatch(paragraph, colour: str = "BFBFBF") -> None:
    run = paragraph.add_run("   ")
    shading = OxmlElement("w:shd"); shading.set(qn("w:fill"), colour)
    run._element.get_or_add_rPr().append(shading)


def _paragraph(cell, before: float = 0, after: float = 0):
    paragraph = cell.add_paragraph() if cell.paragraphs[0].text else cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(before); paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.line_spacing = 0.88
    return paragraph


def _compact(text: str, limit: int = 44) -> str:
    value = " ".join(text.split())
    return value if len(value) <= limit else value[:limit - 1].rstrip() + "…"


class DocxRenderer:
    """Generate an editable Word calendar directly from resolved CalendarDay data."""

    def render(self, output: Path, days: list[CalendarDay], options: PdfOptions) -> Path:
        output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
        document = Document(); section = document.sections[0]
        if options.orientation == "Landscape":
            section.orientation = WD_ORIENT.LANDSCAPE; section.page_width = Mm(297); section.page_height = Mm(210)
        else:
            section.orientation = WD_ORIENT.PORTRAIT; section.page_width = Mm(210); section.page_height = Mm(297)
        section.left_margin = section.right_margin = Mm(7)
        section.top_margin = section.bottom_margin = Mm(5)
        section.header_distance = section.footer_distance = Mm(3)
        normal = document.styles["Normal"]
        normal.font.name = "Arial Narrow"; normal.font.size = Pt(8)
        normal.paragraph_format.space_before = normal.paragraph_format.space_after = Pt(0)
        document.core_properties.title = f"Russian Orthodox Calendar {options.year} - {options.jurisdiction}"
        document.core_properties.author = "Russian Orthodox Calendar Generator"
        document.core_properties.comments = f"Editable calendar generated directly from resolved project data by version {__version__}."
        footer = section.footer.paragraphs[0]; footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        footer_text = options.custom_footer or f"Russian Orthodox Calendar {options.year} - {options.jurisdiction}"
        _format_run(footer.add_run(footer_text), 9, colour="555555")

        usable_mm = (297 if options.orientation == "Landscape" else 210) - 14
        total_width_dxa = round(usable_mm / 25.4 * 1440)
        self._detail_days: list[CalendarDay] = []
        for page_number, month in enumerate(options.months, 1):
            self._add_month(document, [day for day in days if day.civil_date.month == month], month, options, total_width_dxa)
            if page_number < len(options.months): document.add_page_break()
        if self._detail_days:
            detail_section = document.add_section(WD_SECTION.NEW_PAGE)
            detail_section.orientation = section.orientation; detail_section.page_width = section.page_width; detail_section.page_height = section.page_height
            detail_section.left_margin = detail_section.right_margin = Mm(7); detail_section.top_margin = detail_section.bottom_margin = Mm(5)
            columns = detail_section._sectPr.xpath("./w:cols")[0]; columns.set(qn("w:num"), "3"); columns.set(qn("w:space"), "240")
            self._add_daily_details(document, options)
        document.save(output)
        return output

    def _add_month(self, document: Document, days: list[CalendarDay], month: int, options: PdfOptions, total_width_dxa: int) -> None:
        month_name = MONTHS_RU[month] if options.language == "Russian" else calendar.month_name[month]
        weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(options.year, month)
        table = document.add_table(rows=2, cols=7); table.style = "Table Grid"
        labels = WEEKDAYS_RU if options.language == "Russian" else WEEKDAYS_EN
        for index, (cell, label) in enumerate(zip(table.rows[0].cells, labels)):
            _set_cell_shading(cell, "990000" if index == 0 else "0066FF"); _set_cell_margins(cell, 0)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]; paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _format_run(paragraph.add_run(label), 9, True, "FFFFFF", "Segoe UI")
        table.rows[0].height = Mm(4.6); table.rows[0].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST; _prevent_split(table.rows[0])

        title_cell = table.rows[1].cells[0].merge(table.rows[1].cells[-1])
        _set_cell_margins(title_cell, 0)
        title_cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        title = title_cell.paragraphs[0]; title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _format_run(title.add_run(month_name), 40, False, "111111", "Times New Roman")
        table.rows[1].height = Mm(17.37); table.rows[1].height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST; _prevent_split(table.rows[1])

        by_number = {day.civil_date.day: day for day in days}
        # Leave room for Word's mandatory paragraph after the final table so
        # a one-month export does not acquire a blank trailing page.
        # Keep the complete editable grid on one Word page. The source's visible
        # five-row rhythm is 30 mm; six-row months compress proportionally.
        row_height = (150.0 if len(weeks) == 5 else 140.0) / len(weeks)
        week_rows = []
        for week in weeks:
            row = table.add_row(); row.height = Mm(row_height); row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST; _prevent_split(row)
            week_rows.append(row)
        _set_table_geometry(table, total_width_dxa)
        title_width = title_cell._tc.get_or_add_tcPr().find(qn("w:tcW"))
        title_width.set(qn("w:w"), str(total_width_dxa)); title_width.set(qn("w:type"), "dxa")
        column_width_mm = total_width_dxa / 1440 * 25.4 / 7
        for week, row in zip(weeks, week_rows):
            for number, cell in zip(week, row.cells):
                _set_cell_margins(cell); cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                if number and number in by_number: self._fill_day(cell, by_number[number], options, column_width_mm)
        self._add_grid_legends(table, weeks, options)

    def _fill_day(self, cell, day: CalendarDay, options: PdfOptions, column_width_mm: float) -> None:
        state = PdfRenderer.visual_state(day)
        if state in {"great_feast", "vigil"}: _set_cell_shading(cell, "FFCCCC")
        elif state == "fast_day": _set_cell_shading(cell, "BFBFBF")
        date_line = cell.paragraphs[0]; date_line.paragraph_format.space_after = Pt(0)
        date_line.paragraph_format.tab_stops.add_tab_stop(Mm(max(18, column_width_mm - 3)), WD_TAB_ALIGNMENT.RIGHT)
        date_colour = "C00000" if day.civil_date.weekday() == 6 or state in {"great_feast", "vigil"} else "111111"
        _format_run(date_line.add_run(str(day.civil_date.day)), 28, False, date_colour, "Times New Roman")
        if options.include_julian: _format_run(date_line.add_run(str(day.julian_date.day)), 14, False, date_colour, "Times New Roman")
        fasting_symbols = IconRenderer.fasting_symbol_names(day) if options.include_fasting_icons else []
        if fasting_symbols:
            _format_run(date_line.add_run("\t"), 8)
            glyph = "🐟" if fasting_symbols[0] == "fish" else "🌢"
            _format_symbol_run(date_line.add_run(glyph), 14, "00AEEF" if fasting_symbols[0] == "fish" else "FFC000", emoji=True)

        if options.include_liturgical_week_tone and (day.liturgical_week or day.tone):
            tone = ("Глас " if options.language == "Russian" else "Tone ") + str(day.tone) if day.tone else ""
            value = " · ".join(part for part in (day.liturgical_week, tone) if part)
            _format_run(_paragraph(cell).add_run(value), 8, True, "111111")

        saints = ordered_selected_saints(day)
        shown_feasts = day.feasts[:1]
        shown_saints = saints[:2]
        day_rank = day.service_rank.normalized_rank; day_rank_used = False
        for feast in shown_feasts:
            paragraph = _paragraph(cell); major = feast.rank.value == "Great Feast" or state in {"great_feast", "vigil"}
            rank = feast.service_rank
            if not symbol_for(rank) and not day_rank_used and symbol_for(day_rank): rank = day_rank; day_rank_used = True
            elif symbol_for(rank): day_rank_used = True
            _add_ranked_text(paragraph, _compact(feast.name), rank, 10 if major else 8, major, "CC0000" if major else "222222")
        for saint in shown_saints:
            paragraph = _paragraph(cell)
            rank = saint.service_rank
            if not symbol_for(rank) and not day_rank_used and is_primary_saint(day, saint) and symbol_for(day_rank): rank = day_rank; day_rank_used = True
            elif symbol_for(rank): day_rank_used = True
            _add_ranked_text(paragraph, _compact(saint.display_name), rank, 8, is_primary_saint(day, saint), "111111")
        omitted = len(day.feasts) - len(shown_feasts) + len(saints) - len(shown_saints)
        displayed_texts = [item.name for item in shown_feasts] + [item.display_name for item in shown_saints]
        needs_detail = bool(omitted or any(len(" ".join(value.split())) > 44 for value in displayed_texts)
                            or len(day.notes) > 1 or any(len(value) > 44 for value in day.notes)
                            or len(day.public_holidays) > 1 or any(len(value.name) > 44 for value in day.public_holidays))
        if needs_detail and all(item.civil_date != day.civil_date for item in self._detail_days): self._detail_days.append(day)
        if omitted:
            label = f"+{omitted} ещё - см. подробности" if options.language == "Russian" else f"+{omitted} more - see daily details"
            _format_run(_paragraph(cell).add_run(label), 7, False, "555555")
        if options.include_holidays:
            for holiday in day.public_holidays[:1]:
                _format_run(_paragraph(cell).add_run(_compact(holiday.name)), 8, True, "243CFF")
        for note in day.notes[:1]:
            _format_run(_paragraph(cell).add_run(_compact(note)), 8, True, "008A18")

    def _add_grid_legends(self, table, weeks: list[list[int]], options: PdfOptions) -> None:
        if not (options.include_fasting_legend or options.include_service_rank_legend):
            return
        segments = []
        leading = [index for index, value in enumerate(weeks[0]) if not value]
        trailing = [index for index, value in enumerate(weeks[-1]) if not value]
        if leading: segments.append((table.rows[2], leading))
        if trailing: segments.append((table.rows[len(weeks) + 1], trailing))
        if not segments:
            return
        slots: list[tuple[object, list[int], str]] = []
        if len(segments) == 1 and len(segments[0][1]) >= 2:
            row, indices = segments[0]; split = max(1, len(indices) // 2)
            slots = [(row, indices[:split], "fasting"), (row, indices[split:], "rank")]
        else:
            if segments: slots.append((segments[0][0], segments[0][1], "fasting"))
            if len(segments) > 1: slots.append((segments[-1][0], segments[-1][1], "rank"))
        for row, indices, kind in slots:
            if not indices or (kind == "fasting" and not options.include_fasting_legend) or (kind == "rank" and not options.include_service_rank_legend):
                continue
            cell = row.cells[indices[0]]
            if len(indices) > 1: cell = cell.merge(row.cells[indices[-1]])
            _set_cell_margins(cell, 90)
            self._fill_legend_cell(cell, kind, options)

    @staticmethod
    def _fill_legend_cell(cell, kind: str, options: PdfOptions) -> None:
        for paragraph in cell.paragraphs: paragraph.clear()
        heading = cell.paragraphs[0]
        heading_text = ("ПОСТ" if options.language == "Russian" else "FASTING") if kind == "fasting" else ("ЛИТУРГИЧЕСКИЙ РАНГ" if options.language == "Russian" else "LITURGICAL RANK")
        _format_run(heading.add_run(heading_text), 7, True, "111111")
        if kind == "fasting":
            strict = _paragraph(cell); _add_shaded_swatch(strict); _format_run(strict.add_run(" Strict fast" if options.language == "English" else " Строгий пост"), 6.5)
            for glyph, colour, english, russian in (("🌢", "FFC000", "Oil permitted", "Разрешается раст. масло"), ("🐟", "00AEEF", "Fish permitted", "Разрешается рыба")):
                paragraph = _paragraph(cell); _format_symbol_run(paragraph.add_run(glyph), 9, colour, emoji=True); _format_run(paragraph.add_run(" " + (russian if options.language == "Russian" else english)), 6.5)
            return
        for rank in (ServiceRank.GREAT_FEAST, ServiceRank.VIGIL, ServiceRank.POLYELEOS, ServiceRank.DOXOLOGY, ServiceRank.SIX_STICHERA, ServiceRank.NO_SIGN):
            paragraph = _paragraph(cell); glyph = symbol_for(rank)
            if glyph: _format_symbol_run(paragraph.add_run(glyph), 7, symbol_colour_for(rank))
            label = legend_label_for(rank, options.language, options.rank_labels_en, options.rank_labels_ru)
            _format_run(paragraph.add_run((" " if glyph else "") + label), 6.2, False, "111111")

    def _add_daily_details(self, document: Document, options: PdfOptions) -> None:
        title = document.add_paragraph(); title.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _format_run(title.add_run("ПОДРОБНОСТИ ПО ДНЯМ" if options.language == "Russian" else "DAILY CALENDAR DETAILS"), 15, True, "8B1E2D", "Arial")
        intro = document.add_paragraph()
        _format_run(intro.add_run("Полные редактируемые списки памятей, не поместившиеся в компактную месячную сетку." if options.language == "Russian" else "Complete editable commemoration lists that did not fit in the compact monthly grid."), 8, False, "555555", "Arial")
        for day in self._detail_days:
            paragraph = document.add_paragraph(); paragraph.paragraph_format.space_before = Pt(1.5); paragraph.paragraph_format.space_after = Pt(0); paragraph.paragraph_format.line_spacing = 0.82
            date_label = (f"{day.civil_date.day} {MONTHS_RU[day.civil_date.month].lower()} {day.civil_date.year}" if options.language == "Russian" else day.civil_date.strftime("%d %B %Y"))
            _format_run(paragraph.add_run(date_label), 6.2, True, "8B1E2D", "Arial Narrow")
            rank = localized_rank_name(day.service_rank, options.language, options.rank_labels_en, options.rank_labels_ru)
            if rank: _format_run(paragraph.add_run(" | " + rank), 5.2, True, "555555", "Arial Narrow")
            separator = " — "
            for feast in day.feasts:
                _format_run(paragraph.add_run(separator + feast.name), 5.3, True, "B00000", "Arial Narrow"); separator = "; "
            for saint in ordered_selected_saints(day):
                _format_run(paragraph.add_run(separator + saint.display_name), 5.2, is_primary_saint(day, saint), "111111", "Arial Narrow"); separator = "; "
            if day.fasting and day.fasting.level != FastLevel.FREE:
                _format_run(paragraph.add_run(" | " + (day.fasting.period or day.fasting.detail or day.fasting.level.value)), 5.1, True, "444444", "Arial Narrow")
            for holiday in day.public_holidays:
                _format_run(paragraph.add_run(" | " + holiday.name), 5.1, True, "243CFF", "Arial Narrow")
            for note in day.notes:
                _format_run(paragraph.add_run(" | " + note), 5.1, True, "008A18", "Arial Narrow")
