"""Reproducible create/edit/save/reopen/language/PDF project smoke test."""
from __future__ import annotations

import argparse
from pathlib import Path

from orthodox_calendar.projects import ProjectStore
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer
from orthodox_calendar.rendering.docx_renderer import DocxRenderer


def render(project, output: Path) -> None:
    settings = project.settings
    options = PdfOptions(
        settings.year, settings.jurisdiction, settings.template, settings.orientation,
        settings.language, settings.include_julian, settings.include_holidays,
        settings.include_sources, settings.include_fasting_icons,
        settings.include_fasting_legend, settings.include_service_rank_icons,
        settings.include_service_rank_legend, settings.rank_labels_en,
        settings.rank_labels_ru, list(range(1, 13)), settings.parish_name, "",
        settings.custom_header, settings.custom_footer,
    )
    PdfRenderer().render(output, project.resolve_days(), options)


def render_docx(project, output: Path) -> None:
    settings = project.settings
    options = PdfOptions(
        settings.year, settings.jurisdiction, settings.template, "Landscape",
        settings.language, settings.include_julian, settings.include_holidays,
        settings.include_sources, settings.include_fasting_icons,
        settings.include_fasting_legend, settings.include_service_rank_icons,
        settings.include_service_rank_legend, settings.rank_labels_en,
        settings.rank_labels_ru, list(range(1, 13)), settings.parish_name, "",
        settings.custom_header, settings.custom_footer,
    )
    DocxRenderer().render(output, project.resolve_days(), options)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/sample_calendar.rocproject"))
    parser.add_argument("--project", type=Path, default=Path("output/projects/Test_2027_Queensland.rocproject"))
    parser.add_argument("--english-pdf", type=Path, default=Path("output/pdf/Project_Roundtrip_English_2027.pdf"))
    parser.add_argument("--russian-pdf", type=Path, default=Path("output/pdf/Project_Roundtrip_Russian_2027.pdf"))
    parser.add_argument("--english-docx", type=Path, default=Path("output/docx/Project_Roundtrip_English_2027.docx"))
    parser.add_argument("--russian-docx", type=Path, default=Path("output/docx/Project_Roundtrip_Russian_2027.docx"))
    args = parser.parse_args()
    store = ProjectStore(args.project.parent / "recovery")
    project = store.load(args.fixture)
    project.file_path = ""; project.modified = True
    args.project.parent.mkdir(parents=True, exist_ok=True)
    args.english_pdf.parent.mkdir(parents=True, exist_ok=True)
    args.english_docx.parent.mkdir(parents=True, exist_ok=True)
    store.save(project, args.project)
    reopened = store.load(args.project); day = reopened.resolve_days()[6]
    assert [item.id for item in day.saints] == [900002, 900001]
    assert day.saints[0].selected and not day.saints[1].selected
    assert day.notes == ["TEST PARISH DIVINE LITURGY AT 9:00 AM"]
    assert day.is_edited and day.primary_saint_id
    render(reopened, args.english_pdf)
    render_docx(reopened, args.english_docx)
    reopened.settings.language = "Russian"; reopened.mark_modified(); store.save(reopened, args.project)
    russian = store.load(args.project)
    assert russian.settings.language == "Russian"
    render(russian, args.russian_pdf)
    render_docx(russian, args.russian_docx)
    print(args.project.resolve())
    print(args.english_pdf.resolve())
    print(args.russian_pdf.resolve())
    print(args.english_docx.resolve())
    print(args.russian_docx.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
