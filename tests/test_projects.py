import json
from datetime import date
from pathlib import Path

import pytest
from pypdf import PdfReader

from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.models import FastLevel, Fasting, Saint, ServiceRank, ServiceRankInfo, Source
from orthodox_calendar.projects import CalendarProject, ProjectSettings, ProjectStore, ProjectValidationError
from orthodox_calendar.projects.model import saint_key
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer


def make_project(year=2027, language="English"):
    days = OrthodoxCalendarEngine().generate_year(year, "Queensland", language)
    target = days[6]
    target.saints = [
        Saint(101, "Saint Alpha", "Saint Alpha", target.civil_date, source=Source("TEST DATA — NOT FOR LITURGICAL USE"), display_order=0),
        Saint(102, "Saint Beta", "Saint Beta", target.civil_date, source=Source("TEST DATA — NOT FOR LITURGICAL USE"), display_order=1),
        Saint(103, "Saint Gamma", "Saint Gamma", target.civil_date, source=Source("TEST DATA — NOT FOR LITURGICAL USE"), display_order=2),
    ]
    settings = ProjectSettings(year, "Queensland", language)
    return CalendarProject.create(f"TEST {year} Queensland", settings, days, f"{year}.test", "2026-08-26T00:00:00+00:00")


def test_create_edit_save_close_reopen_restores_complete_state(tmp_path):
    project = make_project(); days = project.resolve_days(); day = days[6]
    day.saints[0].selected = False; day.saints[0].display_order = 2
    day.saints[1].selected = True; day.saints[1].display_order = 1
    day.saints[2].selected = True; day.saints[2].display_order = 0
    day.saints.sort(key=lambda item: item.display_order)
    day.notes = ["Parish Divine Liturgy at 9:00 AM"]
    day.fasting = Fasting(FastLevel.FISH, "Parish fast", "Fish permitted")
    day.service_rank = ServiceRankInfo(normalized_rank=ServiceRank.POLYELEOS, status="user_override", user_override=True)
    project.update_day(day, saint_key(day.saints[0]))
    path = ProjectStore(tmp_path / "recovery").save(project, tmp_path / "Test_2027_Queensland.rocproject")
    reopened = ProjectStore(tmp_path / "recovery").load(path); restored = reopened.resolve_days()[6]
    assert reopened.settings.year == 2027 and reopened.settings.jurisdiction == "Queensland" and reopened.settings.language == "English"
    assert [item.id for item in restored.saints] == [103, 102, 101]
    assert restored.saints[0].selected and not restored.saints[2].selected
    assert restored.notes == ["Parish Divine Liturgy at 9:00 AM"]
    assert restored.fasting.level == FastLevel.FISH
    assert restored.service_rank.normalized_rank == ServiceRank.POLYELEOS


def test_save_as_backup_and_atomic_recovery(tmp_path):
    store = ProjectStore(tmp_path / "recovery"); project = make_project()
    first = store.save(project, tmp_path / "draft.rocproject")
    project.project_name = "Final variant"; project.mark_modified(); store.write_recovery(project)
    assert store.has_newer_recovery(first)
    recovered = store.load_recovery(first); assert recovered.project_name == "Final variant" and recovered.modified
    store.save(recovered, first); assert not first.with_suffix(".rocproject.recovery").exists()
    recovered.project_name = "Another"; recovered.mark_modified(); store.save(recovered, first)
    assert first.with_suffix(".rocproject.bak").exists()
    second = store.save(recovered, tmp_path / "final-copy")
    assert second.suffix == ".rocproject" and first.exists()


def test_save_as_removes_old_recovery_and_discard_removes_untitled_recovery(tmp_path):
    store = ProjectStore(tmp_path / "recovery"); project = make_project()
    untitled = store.write_recovery(project); assert untitled.exists()
    store.save(project, tmp_path / "named.rocproject"); assert not untitled.exists()
    project.mark_modified(); saved_recovery = store.write_recovery(project); assert saved_recovery.exists()
    store.discard_project_recovery(project); assert not saved_recovery.exists()


def test_corrupt_future_schema_and_oversized_projects_are_rejected(tmp_path):
    store = ProjectStore(tmp_path)
    corrupt = tmp_path / "bad.rocproject"; corrupt.write_text("not json", encoding="utf-8")
    with pytest.raises(ProjectValidationError): store.load(corrupt)
    future = tmp_path / "future.rocproject"; future.write_text(json.dumps({"project_schema_version": 999}), encoding="utf-8")
    with pytest.raises(ProjectValidationError, match="newer application"): store.load(future)


def test_shipped_project_fixture_is_real_portable_and_marked_as_test_data():
    project = ProjectStore().load(Path(__file__).parent / "fixtures" / "sample_calendar.rocproject")
    restored = project.resolve_days()[6]
    assert len(project.source_snapshot) == 365
    assert "NOT FOR LITURGICAL USE" in project.project_name
    assert [item.id for item in restored.saints] == [900002, 900001]
    assert restored.saints[0].selected and not restored.saints[1].selected
    assert restored.notes == ["TEST PARISH DIVINE LITURGY AT 9:00 AM"]


def test_project_embeds_logo_and_materializes_it_portably(tmp_path):
    project = make_project(); source = Path("assets/icons/feast.png").resolve()
    project.settings.parish_logo = str(source)
    saved = ProjectStore(tmp_path / "recovery").save(project, tmp_path / "portable")
    raw = saved.read_text(encoding="utf-8")
    assert str(source) not in raw and "embedded://parish_logo" in raw
    reopened = ProjectStore().load(saved)
    materialized = Path(reopened.materialize_parish_logo(tmp_path / "assets"))
    assert materialized.read_bytes() == source.read_bytes()


def test_source_update_preserves_missing_saved_saint_and_flags_warning():
    project = make_project(); day = project.resolve_days()[6]; day.saints[0].selected = False; project.update_day(day)
    current = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    updated = project.update_source_data(current, "2027.new")
    saved = next(item for item in updated[6].saints if item.id == 101)
    assert not saved.selected
    assert project.missing_references and "Saint Alpha" in project.missing_references[0]


def test_source_compare_reports_changes_without_mutating_project():
    project = make_project(); project.modified = False; current = OrthodoxCalendarEngine().generate_year(2027, "Queensland")
    before = project.to_dict(); result = project.compare_source_data(current)
    assert result["changed_dates"] >= 1 and result["removed_records"] >= 3
    assert project.to_dict() == before and not project.modified


def test_project_pdf_uses_reopened_edits_without_saving_again(tmp_path):
    store = ProjectStore(tmp_path); project = make_project(); day = project.resolve_days()[6]
    day.saints[0].selected = False; day.saints[1].display_name = "PRIMARY TEST SAINT"; day.saints[1].display_order = 0; day.notes = ["TEST PROJECT NOTE"]
    project.update_day(day, saint_key(day.saints[1])); path = store.save(project, tmp_path / "calendar.rocproject")
    reopened = store.load(path); output = tmp_path / "project.pdf"
    PdfRenderer().render(output, reopened.resolve_days(), PdfOptions(2027, "Queensland", months=[1]))
    text = PdfReader(output).pages[0].extract_text() or ""
    assert "PRIMARY TEST SAINT" in text and "TEST PROJECT NOTE" in text and "Saint Alpha" not in text


def test_language_and_state_are_project_specific(tmp_path):
    project = make_project(language="Russian"); project.settings.jurisdiction = "Victoria"
    path = ProjectStore(tmp_path).save(project, tmp_path / "russian.rocproject")
    reopened = ProjectStore(tmp_path).load(path)
    assert reopened.settings.language == "Russian" and reopened.settings.jurisdiction == "Victoria" and reopened.settings.year == 2027
