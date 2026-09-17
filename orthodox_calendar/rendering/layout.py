from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.units import mm


@dataclass(frozen=True, slots=True)
class ReferenceLayout:
    margin_left: float = 7.0 * mm
    margin_right: float = 7.0 * mm
    margin_top: float = 5.0 * mm
    margin_bottom: float = 5.0 * mm
    weekday_height: float = 4.6 * mm
    title_height: float = 17.37 * mm
    footer_height: float = 4.2 * mm
    cell_padding: float = 2.03 * mm
    border_width: float = 0.5
    rank_icon_size: float = 4.1 * mm
    fasting_icon_size: float = 3.7 * mm


REFERENCE_LAYOUT = ReferenceLayout()
