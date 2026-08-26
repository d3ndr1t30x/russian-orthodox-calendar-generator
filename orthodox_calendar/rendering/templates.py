from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.colors import Color, HexColor


@dataclass(frozen=True)
class TemplateStyle:
    name: str
    ink: Color
    accent: Color
    pale: Color
    border_width: float
    normal_background: Color
    strict_fast_background: Color
    vigil_background: Color
    great_feast_background: Color
    feast_text: Color
    vigil_text: Color
    secondary_text: Color
    holiday_indicator: Color


STYLES = {
    "Traditional": TemplateStyle("Traditional", HexColor("#211D1B"), HexColor("#8B1E2D"), HexColor("#F5EFE7"), 0.9, HexColor("#FFFDFC"), HexColor("#E2E2E2"), HexColor("#F9E8E8"), HexColor("#F6DEDE"), HexColor("#981F2F"), HexColor("#8B1E2D"), HexColor("#5C5753"), HexColor("#273C55")),
    "Minimal": TemplateStyle("Minimal", HexColor("#20242A"), HexColor("#3F5D73"), HexColor("#F2F4F5"), 0.6, HexColor("#FFFFFF"), HexColor("#E5E7E9"), HexColor("#F7EAEA"), HexColor("#F4E1E1"), HexColor("#8F2331"), HexColor("#8F2331"), HexColor("#596168"), HexColor("#314C60")),
    "Parish": TemplateStyle("Parish", HexColor("#252018"), HexColor("#785B23"), HexColor("#F6F1E2"), 1.1, HexColor("#FFFDF8"), HexColor("#E4E2DD"), HexColor("#F8E8E4"), HexColor("#F5DED8"), HexColor("#8A2832"), HexColor("#8A2832"), HexColor("#625B50"), HexColor("#3C4B55")),
}
