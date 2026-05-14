"""Gera BMPs do assistente Inno (modern) a partir de assets/easyacq.ico.

Dimensoes oficiais Inno Setup 6 (WizardStyle=modern):
  WizardImageFile      164 x 314
  WizardSmallImageFile 55 x 55

Executar antes de compilar EasyAcq.iss (build_release.ps1 -Installer e CI).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Instale Pillow: pip install -r requirements-build.txt"
    ) from exc

ROOT = Path(__file__).resolve().parents[1]
ICO_PATH = ROOT / "assets" / "easyacq.ico"
OUT_LARGE = ROOT / "assets" / "setup_wizard_large.bmp"
OUT_SMALL = ROOT / "assets" / "setup_wizard_small.bmp"

# Fundo alinhado a estetica «bancada / instrumento»
_BG = (13, 71, 117)
_TITLE = (255, 255, 255)
_SUB = (200, 230, 255)


def _load_icon_rgba() -> Image.Image:
    if not ICO_PATH.is_file():
        raise SystemExit(f"Icon em falta: {ICO_PATH}")
    im = Image.open(ICO_PATH)
    return im.convert("RGBA")


def _fit(im: Image.Image, max_w: int, max_h: int) -> Image.Image:
    w, h = im.size
    scale = min(max_w / w, max_h / h, 1.0)
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return im.resize((nw, nh), Image.Resampling.LANCZOS)


def _try_font(size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    candidates = [
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for p in candidates:
        if p.is_file():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _paste_alpha(dst: Image.Image, src: Image.Image, pos: tuple[int, int]) -> None:
    if src.mode == "RGBA":
        dst.paste(src, pos, src)
    else:
        dst.paste(src, pos)


def render_large(icon: Image.Image) -> Image.Image:
    w, h = 164, 314
    img = Image.new("RGB", (w, h), _BG)
    fitted = _fit(icon, 120, 120)
    ix = (w - fitted.width) // 2
    iy = 36
    _paste_alpha(img, fitted, (ix, iy))
    draw = ImageDraw.Draw(img)
    title = _try_font(17)
    sub = _try_font(12)
    draw.text((10, 198), "EasyAcq", fill=_TITLE, font=title)
    draw.text((10, 222), "Instalacao", fill=_SUB, font=sub)
    return img


def render_small(icon: Image.Image) -> Image.Image:
    size = 55
    img = Image.new("RGB", (size, size), _BG)
    fitted = _fit(icon, 48, 48)
    sx = (size - fitted.width) // 2
    sy = (size - fitted.height) // 2
    _paste_alpha(img, fitted, (sx, sy))
    return img


def main() -> int:
    icon = _load_icon_rgba()
    OUT_LARGE.parent.mkdir(parents=True, exist_ok=True)
    render_large(icon).save(OUT_LARGE, "BMP")
    render_small(icon).save(OUT_SMALL, "BMP")
    print("OK:", OUT_LARGE.name, OUT_SMALL.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
