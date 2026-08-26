from __future__ import annotations

import argparse
import copy
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orthodox_calendar.calendar_engine.orthodox_calendar import OrthodoxCalendarEngine
from orthodox_calendar.models import FastLevel, Fasting, PublicHoliday, ServiceRank, ServiceRankInfo, Source
from orthodox_calendar.rendering.pdf_renderer import PdfOptions, PdfRenderer


RANKS = (
    ServiceRank.GREAT_FEAST,
    ServiceRank.VIGIL,
    ServiceRank.POLYELEOS,
    ServiceRank.DOXOLOGY,
    ServiceRank.SIX_STICHERA,
    ServiceRank.NO_SIGN,
)


def stress_month(year: int, month: int, jurisdiction: str, language: str):
    days = copy.deepcopy(OrthodoxCalendarEngine().generate_year(year, jurisdiction, language))
    selected = [day for day in days if day.civil_date.month == month]
    for day, rank in zip(selected, RANKS, strict=False):
        day.service_rank = ServiceRankInfo(normalized_rank=rank, status="visual_test")
    selected[2].fasting = Fasting(FastLevel.FISH, "Fast", "Fish permitted")
    selected[3].fasting = Fasting(FastLevel.WINE_OIL, "Fast", "Wine and oil permitted")
    selected[4].fasting = Fasting(FastLevel.STRICT, "Strict fast", "No food")
    selected[5].public_holidays = [PublicHoliday("Australian public holiday stress test", jurisdiction, Source("Visual regression fixture"))]
    return days


def render_first_page(pdf: Path, png: Path) -> None:
    executable = shutil.which("pdftoppm")
    if not executable:
        raise SystemExit("pdftoppm is required to create visual comparison images")
    prefix = png.with_suffix("")
    subprocess.run([executable, "-f", "1", "-singlefile", "-png", "-r", "150", str(pdf), str(prefix)], check=True)


def comparison(reference: Path, generated: Path, output: Path) -> None:
    left, right = Image.open(reference).convert("RGB"), Image.open(generated).convert("RGB")
    target_h = max(left.height, right.height)
    if left.height != target_h:
        left = left.resize((round(left.width * target_h / left.height), target_h))
    if right.height != target_h:
        right = right.resize((round(right.width * target_h / right.height), target_h))
    gutter = 24
    canvas = Image.new("RGB", (left.width + right.width + gutter, target_h), "white")
    canvas.paste(left, (0, 0)); canvas.paste(right, (left.width + gutter, 0))
    ImageOps.expand(canvas, border=2, fill="black").save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a reference-format stress calendar and optional side-by-side comparison")
    parser.add_argument("--year", type=int, default=2027)
    parser.add_argument("--month", type=int, default=4)
    parser.add_argument("--jurisdiction", default="Queensland")
    parser.add_argument("--language", choices=("English", "Russian"), default="English")
    parser.add_argument("--reference-page", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output/visual-regression"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pdf = args.output_dir / f"stress-{args.year}-{args.month:02d}-{args.language.lower()}.pdf"
    png = args.output_dir / f"stress-{args.year}-{args.month:02d}-{args.language.lower()}.png"
    PdfRenderer().render(pdf, stress_month(args.year, args.month, args.jurisdiction, args.language), PdfOptions(args.year, args.jurisdiction, language=args.language, months=[args.month]))
    render_first_page(pdf, png)
    if args.reference_page:
        comparison(args.reference_page, png, args.output_dir / "reference-vs-generated.png")
    print(pdf)
    print(png)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
