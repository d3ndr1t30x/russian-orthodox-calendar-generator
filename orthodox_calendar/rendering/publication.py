from __future__ import annotations

from orthodox_calendar.models import CalendarDay, Saint
from orthodox_calendar.projects.model import primary_saint, saint_key


def ordered_selected_saints(day: CalendarDay) -> list[Saint]:
    """Return the single publication order shared by GUI, PDF and DOCX."""
    selected = sorted((item for item in day.saints if item.selected), key=lambda item: (item.display_order, saint_key(item)))
    primary = primary_saint(day)
    if primary is None:
        return selected
    return [primary] + [item for item in selected if saint_key(item) != saint_key(primary)]


def is_primary_saint(day: CalendarDay, saint: Saint) -> bool:
    primary = primary_saint(day)
    return primary is not None and saint_key(primary) == saint_key(saint)
