from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path


@dataclass
class Settings:
    config_version: int = 3
    default_year: int = 0
    jurisdiction: str = "Queensland"
    language: str = "English"
    template: str = "Traditional"
    paper: str = "A4"
    orientation: str = "Landscape"
    include_julian: bool = True
    include_holidays: bool = True
    include_sources: bool = True
    include_fasting_icons: bool = True
    include_fasting_legend: bool = True
    include_service_rank_icons: bool = True
    include_service_rank_legend: bool = True
    rank_labels_en: dict[str, str] = field(default_factory=dict)
    rank_labels_ru: dict[str, str] = field(default_factory=dict)
    output_directory: str = ""
    parish_name: str = ""
    parish_logo: str = ""
    address: str = ""
    website: str = ""
    phone: str = ""
    custom_header: str = ""
    custom_footer: str = ""

    @property
    def effective_year(self) -> int:
        return self.default_year or date.today().year


class SettingsStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if int(data.get("config_version", 1)) < 2:
                data.update({"config_version": 2, "orientation": "Landscape", "paper": "A4", "include_fasting_icons": True, "include_fasting_legend": True})
            if int(data.get("config_version", 1)) < 3:
                data.update({"config_version": 3, "include_service_rank_icons": True, "include_service_rank_legend": True, "rank_labels_en": {}, "rank_labels_ru": {}})
            if str(data.get("language", "")).startswith("Russian"):
                data["language"] = "Russian"
            return Settings(**{k: v for k, v in data.items() if k in Settings.__dataclass_fields__})
        except (OSError, ValueError, TypeError):
            return Settings()

    def save(self, settings: Settings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)
