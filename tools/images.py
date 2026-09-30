"""Готовит обложки: скачивает оригиналы с Tilda, обрезает вшитую рамку, приводит к 4:3
и сохраняет WebP трёх ширин в assets/covers/<slug>-<ширина>.webp.

416  — карточка на обычном экране
832  — карточка на ретине, обложка статьи на телефоне
1440 — обложка статьи (720 px) на ретине

Нужен cwebp (brew install webp). Запуск: python3 tools/images.py
"""
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "tools" / ".cache" / "covers"   # оригиналы PNG, в git не попадают
OUT = ROOT / "assets" / "covers"
WIDTHS = (416, 832, 1440)
FRAME = 96      # рамка 64 px + запас на скруглённые углы фото внутри неё
QUALITY = 78


def posts():
    js = (ROOT / "assets" / "posts.js").read_text().split("window.BLOG_POSTS")[1]
    for chunk in re.findall(r"\{ slug: .*?\},?\n", js, re.S):
        yield (re.search(r'slug: "([^"]+)"', chunk)[1],
               re.search(r'img: "([^"]+)"', chunk)[1],
               "framed: true" in chunk)


def size(path):
    out = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", str(path)],
                         capture_output=True, text=True).stdout
    return int(re.search(r"pixelWidth: (\d+)", out)[1]), int(re.search(r"pixelHeight: (\d+)", out)[1])


def crop_box(w, h, framed):
    """Область 4:3 по центру; у обложек с рамкой — внутри рамки."""
    x0, y0 = (FRAME, FRAME) if framed else (0, 0)
    w, h = w - 2 * x0, h - 2 * y0
    if w * 3 > h * 4:           # шире 4:3 → режем бока
        cw, ch = h * 4 // 3, h
    else:                       # выше 4:3 → режем верх и низ
        cw, ch = w, w * 3 // 4
    return x0 + (w - cw) // 2, y0 + (h - ch) // 2, cw, ch


def main():
    SRC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for slug, img, framed in posts():
        src = SRC / f"{slug}.png"
        if not src.exists():
            subprocess.run(["curl", "-sL", "-o", str(src), f"https://static.tildacdn.com/{img}"], check=True)
            time.sleep(0.5)
        x, y, cw, ch = crop_box(*size(src), framed)
        for w in WIDTHS:
            dst = OUT / f"{slug}-{w}.webp"
            subprocess.run(["cwebp", "-quiet", "-q", str(QUALITY), "-metadata", "none",
                            "-crop", str(x), str(y), str(cw), str(ch), "-resize", str(w), "0",
                            str(src), "-o", str(dst)], check=True)
            total += dst.stat().st_size
        print(f"{slug}: {cw}×{ch}{' (рамка обрезана)' if framed else ''}")
    print(f"\nГотово: {total // 1024} КБ в {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
