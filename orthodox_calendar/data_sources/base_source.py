from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class SourceAvailability:
    available: bool
    message: str


class CalendarSource(ABC):
    name: str
    home_url: str

    @abstractmethod
    def check_availability(self) -> SourceAvailability:
        """Perform a conservative availability check; never bypass access controls."""


class ManualFirstWebSource(CalendarSource):
    """Metadata adapter. Annual imports are manual until a stable permitted feed exists."""

    def __init__(self, name: str, home_url: str):
        self.name = name
        self.home_url = home_url

    def check_availability(self) -> SourceAvailability:
        try:
            import requests
            from urllib.parse import urljoin
            robots = requests.get(urljoin(self.home_url, "/robots.txt"), timeout=8, headers={"User-Agent": "RussianOrthodoxCalendar/1.0"})
            if robots.status_code >= 500:
                return SourceAvailability(False, f"Server returned HTTP {robots.status_code}")
            return SourceAvailability(True, "Website reachable; use manual import unless a permitted structured feed is configured")
        except requests.RequestException as exc:
            return SourceAvailability(False, f"Connection unavailable: {exc.__class__.__name__}")

