from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from uuid import uuid4

from .model import CalendarProject, ProjectValidationError, utc_now


LOG = logging.getLogger(__name__)
MAX_PROJECT_BYTES = 25 * 1024 * 1024


class ProjectStore:
    def __init__(self, recovery_directory: Path | None = None):
        self.recovery_directory = Path(recovery_directory) if recovery_directory else None

    @staticmethod
    def normalize_path(path: Path) -> Path:
        path = Path(path)
        return path if path.suffix.lower() == ".rocproject" else path.with_suffix(".rocproject")

    def save(self, project: CalendarProject, path: Path, create_backup: bool = True) -> Path:
        target = self.normalize_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            previous_recovery = self.recovery_path(project)
        except ProjectValidationError:
            previous_recovery = None
        project.capture_parish_logo()
        project.modified_at = utc_now()
        payload = project.to_dict()
        temp = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            with temp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
            self.load(temp)
            if create_backup and target.exists():
                shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
            os.replace(temp, target)
        except Exception:
            if temp.exists():
                temp.unlink()
            LOG.exception("Project save failed")
            raise
        project.file_path = str(target)
        project.modified = False
        recovery = self.recovery_path(project, target)
        for candidate in {previous_recovery, recovery}:
            if candidate is not None and candidate.exists():
                candidate.unlink()
        LOG.info("Project saved: %s", project.project_id)
        return target

    def load(self, path: Path) -> CalendarProject:
        source = Path(path)
        try:
            size = source.stat().st_size
            if size <= 0 or size > MAX_PROJECT_BYTES:
                raise ProjectValidationError("Project file is empty or exceeds the 25 MB safety limit")
            raw = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ProjectValidationError("Project root must be a JSON object")
            project = CalendarProject.from_dict(raw)
            project.file_path = str(source)
            project.modified = False
            LOG.info("Project opened: %s", project.project_id)
            return project
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            LOG.warning("Project validation failed: %s", type(exc).__name__)
            if isinstance(exc, ProjectValidationError):
                raise
            raise ProjectValidationError("Unable to open this project because it is corrupted or invalid") from exc

    def recovery_path(self, project: CalendarProject, project_path: Path | None = None) -> Path:
        if project_path or project.file_path:
            target = Path(project_path or project.file_path)
            return target.with_suffix(target.suffix + ".recovery")
        if self.recovery_directory is None:
            raise ProjectValidationError("No recovery directory is configured")
        self.recovery_directory.mkdir(parents=True, exist_ok=True)
        return self.recovery_directory / f"untitled-{project.project_id}.rocproject.recovery"

    def write_recovery(self, project: CalendarProject) -> Path:
        recovery = self.recovery_path(project)
        recovery.parent.mkdir(parents=True, exist_ok=True)
        temp = recovery.with_name(f".{recovery.name}.{uuid4().hex}.tmp")
        with temp.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(project.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n"); handle.flush(); os.fsync(handle.fileno())
        self.load(temp)
        os.replace(temp, recovery)
        LOG.info("Project recovery written: %s", project.project_id)
        return recovery

    def has_newer_recovery(self, path: Path) -> bool:
        source = Path(path); recovery = source.with_suffix(source.suffix + ".recovery")
        return recovery.exists() and (not source.exists() or recovery.stat().st_mtime > source.stat().st_mtime)

    def load_recovery(self, path: Path) -> CalendarProject:
        source = Path(path); recovery = source if source.name.endswith(".recovery") else source.with_suffix(source.suffix + ".recovery")
        project = self.load(recovery)
        project.file_path = str(source if not source.name.endswith(".recovery") else Path(str(source)[:-9]))
        project.modified = True
        LOG.info("Project recovered: %s", project.project_id)
        return project

    @staticmethod
    def discard_recovery(path: Path) -> None:
        recovery = Path(path).with_suffix(Path(path).suffix + ".recovery")
        if recovery.exists():
            recovery.unlink()

    def discard_project_recovery(self, project: CalendarProject) -> None:
        recovery = self.recovery_path(project)
        if recovery.exists():
            recovery.unlink()
