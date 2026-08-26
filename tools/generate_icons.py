"""Generate bundled, print-friendly transparent calendar icons."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "assets" / "icons"
OUT.mkdir(parents=True, exist_ok=True)
RANK_OUT = OUT / "rank"
RANK_OUT.mkdir(parents=True, exist_ok=True)
SIZE = 96
INK = (40, 40, 40, 255)
RED = (139, 30, 45, 255)


def save(name, draw_fn):
    canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw_fn(ImageDraw.Draw(canvas))
    canvas.save(OUT / name)


def save_rank(name, draw_fn):
    canvas = Image.new("RGBA", (SIZE, SIZE), (255, 255, 255, 0))
    draw_fn(ImageDraw.Draw(canvas))
    canvas.save(RANK_OUT / name)


save("fish.png", lambda d: (d.ellipse((18, 31, 69, 66), outline=INK, width=6), d.polygon(((68, 48), (88, 29), (88, 68)), outline=INK), d.ellipse((29, 43, 35, 49), fill=INK)))
save("wine.png", lambda d: (d.arc((24, 10, 72, 62), 0, 180, fill=INK, width=6), d.line((25, 36, 71, 36), fill=INK, width=5), d.line((48, 60, 48, 82), fill=INK, width=6), d.line((30, 84, 66, 84), fill=INK, width=6)))
save("oil.png", lambda d: (d.rounded_rectangle((25, 28, 71, 84), 8, outline=INK, width=6), d.rectangle((35, 13, 61, 31), outline=INK, width=5), d.polygon(((48, 41), (36, 62), (48, 72), (60, 62)), outline=INK)))
save("strict_fast.png", lambda d: (d.ellipse((14, 14, 82, 82), outline=INK, width=6), d.line((27, 27, 69, 69), fill=INK, width=7), d.line((69, 27, 27, 69), fill=INK, width=7)))
save("feast.png", lambda d: (d.line((48, 12, 48, 83), fill=RED, width=7), d.line((22, 36, 74, 36), fill=RED, width=7), d.line((30, 22, 66, 22), fill=RED, width=5)))
save("vigil.png", lambda d: (d.ellipse((28, 12, 68, 78), outline=RED, width=6), d.line((48, 23, 48, 64), fill=RED, width=5), d.line((35, 38, 61, 38), fill=RED, width=5), d.line((30, 83, 66, 83), fill=INK, width=5)))
save("holiday.png", lambda d: d.polygon(((48, 10), (86, 48), (48, 86), (10, 48)), outline=INK, width=6))


def cross(draw, color=INK, width=6):
    draw.line((48, 21, 48, 76), fill=color, width=width)
    draw.line((27, 40, 69, 40), fill=color, width=width)


def great_feast(draw):
    draw.ellipse((8, 8, 88, 88), outline=RED, width=6); draw.ellipse((17, 17, 79, 79), outline=RED, width=3); cross(draw, RED, 7)


def vigil_rank(draw):
    draw.arc((10, 8, 86, 84), 25, 155, fill=RED, width=7); draw.arc((10, 8, 86, 84), 205, 335, fill=RED, width=7); cross(draw, RED, 6)


def polyeleos(draw):
    draw.ellipse((13, 13, 83, 83), outline=INK, width=6); cross(draw, INK, 6); draw.ellipse((43, 43, 53, 53), fill=RED)


def doxology(draw):
    draw.ellipse((29, 29, 67, 67), outline=INK, width=6)
    for line in ((48, 7, 48, 21), (48, 75, 48, 89), (7, 48, 21, 48), (75, 48, 89, 48), (18, 18, 28, 28), (68, 68, 78, 78), (68, 28, 78, 18), (18, 78, 28, 68)):
        draw.line(line, fill=INK, width=5)


def six_stichera(draw):
    points = ((48, 14), (76, 31), (76, 65), (48, 82), (20, 65), (20, 31))
    draw.ellipse((10, 10, 86, 86), outline=INK, width=4)
    for px, py in points: draw.ellipse((px - 6, py - 6, px + 6, py + 6), fill=INK)


def no_sign(draw):
    draw.ellipse((17, 17, 79, 79), outline=(95, 95, 95, 255), width=4)
    for px in (34, 48, 62): draw.ellipse((px - 4, 44, px + 4, 52), fill=(95, 95, 95, 255))


save_rank("great_feast.png", great_feast)
save_rank("vigil.png", vigil_rank)
save_rank("polyeleos.png", polyeleos)
save_rank("doxology.png", doxology)
save_rank("six_stichera.png", six_stichera)
save_rank("no_sign.png", no_sign)
