from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from orthodox_calendar.calendar_engine.australian_holidays import JURISDICTIONS
from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.config import SettingsStore
from orthodox_calendar.data_sources.importer import CalendarImporter
from orthodox_calendar.database.database import Database
from orthodox_calendar.paths import ensure_user_dirs
from orthodox_calendar.projects import ProjectStore
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Russian Orthodox printable calendar generator")
    parser.add_argument("project_file", nargs="?", type=Path, help="Open a .rocproject file")
    parser.add_argument("--project", type=Path, help="Render or open a saved .rocproject file")
    parser.add_argument("--year", type=int)
    parser.add_argument("--state", choices=[code for code in JURISDICTIONS.values() if code] + list(JURISDICTIONS.keys()))
    parser.add_argument("--generate-pdf", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--months", help="Comma-separated month numbers (default: all)")
    parser.add_argument("--orientation", choices=["Portrait", "Landscape"])
    parser.add_argument("--language", choices=["English", "Russian"])
    parser.add_argument("--template", choices=["Traditional", "Minimal", "Parish"], default="Traditional")
    parser.add_argument("--import-file", type=Path)
    parser.add_argument("--source-name", default="Manual authoritative import")
    parser.add_argument("--sync-holy-trinity", action="store_true", help="Synchronize the legacy Holy Trinity English/Russian source")
    parser.add_argument("--cache-only", action="store_true", help="During synchronization, do not make network requests")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gui-smoke-test", action="store_true", help=argparse.SUPPRESS)
    return parser


def initialize():
    paths = ensure_user_dirs()
    logging.basicConfig(filename=paths["logs"] / "application.log", level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    database = Database(paths["database"] / "calendar.sqlite3"); database.initialize()
    store = SettingsStore(paths["config"] / "settings.json"); settings = store.load()
    return paths, database, store, settings


def _jurisdiction(value: str | None, default: str) -> str:
    if not value: return default
    if value in JURISDICTIONS: return value
    return next((name for name, code in JURISDICTIONS.items() if code == value), default)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths, database, store, settings = initialize()
    year = args.year or settings.effective_year
    jurisdiction = _jurisdiction(args.state, settings.jurisdiction)
    if args.import_file:
        result = CalendarImporter(database).import_file(args.import_file, year, args.source_name)
        print(f"Imported {result.count} records for {result.year}")
        return 0
    if args.sync_holy_trinity:
        from orthodox_calendar.services.synchronization import SynchronizationService
        result, counts = SynchronizationService(database).sync_holy_trinity(year, cache_only=args.cache_only)
        print(f"Holy Trinity {year}: {counts}; downloaded={result.downloaded}; cache={result.cache_hits}; legacy-cache={result.legacy_cache_hits}; failures={len(result.failures)}")
        return 0 if not result.failures else 2
    if args.generate_pdf or args.smoke_test:
        project_path = args.project or args.project_file
        project = ProjectStore(paths["cache"] / "recovery").load(project_path) if project_path else None
        if project:
            year, jurisdiction = project.settings.year, project.settings.jurisdiction
            language, orientation, template = project.settings.language, project.settings.orientation, project.settings.template
            days = project.resolve_days()
        else:
            language = args.language or settings.language; orientation = args.orientation or settings.orientation; template = args.template
            days = OrthodoxCalendarEngine(database).generate_year(year, jurisdiction, language)
        months = [int(item) for item in args.months.split(",")] if args.months else list(range(1, 13))
        if any(not 1 <= month <= 12 for month in months): raise ValueError("Months must be from 1 to 12")
        safe_state = jurisdiction.replace(" ", "_").replace("/", "_")
        output = args.output or paths["output"] / f"Russian_Orthodox_Calendar_{year}_{safe_state}_{language}.pdf"
        options = PdfOptions(
            year=year, jurisdiction=jurisdiction, template=template, orientation=orientation,
            language=language, include_julian=project.settings.include_julian if project else settings.include_julian,
            include_holidays=project.settings.include_holidays if project else settings.include_holidays, include_sources=project.settings.include_sources if project else settings.include_sources,
            include_fasting_icons=project.settings.include_fasting_icons if project else settings.include_fasting_icons,
            include_fasting_legend=project.settings.include_fasting_legend if project else settings.include_fasting_legend,
            include_service_rank_icons=project.settings.include_service_rank_icons if project else settings.include_service_rank_icons,
            include_service_rank_legend=project.settings.include_service_rank_legend if project else settings.include_service_rank_legend,
            rank_labels_en=project.settings.rank_labels_en if project else settings.rank_labels_en, rank_labels_ru=project.settings.rank_labels_ru if project else settings.rank_labels_ru,
            months=months,
            parish_name=project.settings.parish_name if project else settings.parish_name,
            parish_logo=project.materialize_parish_logo(paths["cache"] / "project-assets" / project.project_id) if project else settings.parish_logo,
            custom_header=project.settings.custom_header if project else settings.custom_header,
            custom_footer=project.settings.custom_footer if project else settings.custom_footer,
        )
        PdfRenderer().render(output, days, options)
        print(output)
        return 0
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from orthodox_calendar.ui.main_window import MainWindow
    from orthodox_calendar.ui.styles import APP_STYLESHEET
    app = QApplication(sys.argv); app.setApplicationName("Russian Orthodox Calendar Generator"); app.setOrganizationName("Russian Orthodox Calendar Generator"); app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow(database, settings, store, args.project or args.project_file, check_data_updates=not args.gui_smoke_test); window.show()
    if args.gui_smoke_test:
        QTimer.singleShot(2500, window.close)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
