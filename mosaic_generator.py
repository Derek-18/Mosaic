#!/usr/bin/env python3
"""Deterministic manufacturable mosaic generator (MVP).

Supports input images in JPEG/PNG/BMP (via Pillow) and PPM (P3/P6).
Outputs:
- mosaic_preview.ppm
- mosaic_preview.png
- assembly.csv
- assembly.svg
- bom.csv
- report.html (simple UI dashboard)
"""

from __future__ import annotations

import argparse
import csv
import html
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from PIL import Image

RGB8 = Tuple[int, int, int]
RGBF = Tuple[float, float, float]


@dataclass(frozen=True)
class RasterImage:
    width: int
    height: int
    pixels: List[RGB8]


def _tokenize_ppm(data: bytes) -> List[bytes]:
    tokens: List[bytes] = []
    i = 0
    while i < len(data):
        if data[i] in b" \t\r\n":
            i += 1
            continue
        if data[i] == ord("#"):
            while i < len(data) and data[i] not in b"\r\n":
                i += 1
            continue
        j = i
        while j < len(data) and data[j] not in b" \t\r\n":
            j += 1
        tokens.append(data[i:j])
        i = j
    return tokens


def read_ppm(path: Path) -> RasterImage:
    data = path.read_bytes()
    if data.startswith(b"P3"):
        toks = _tokenize_ppm(data)
        _, w_b, h_b, max_b, *vals_b = toks
        width, height, maxv = int(w_b), int(h_b), int(max_b)
        if maxv != 255:
            raise ValueError("PPM max value must be 255")
        vals = [int(v) for v in vals_b]
        if len(vals) != width * height * 3:
            raise ValueError("P3 data length mismatch")
        px = [(vals[i], vals[i + 1], vals[i + 2]) for i in range(0, len(vals), 3)]
        return RasterImage(width, height, px)

    if not data.startswith(b"P6"):
        raise ValueError("Not a PPM file")

    header_tokens: List[bytes] = []
    i = 0
    while len(header_tokens) < 4:
        while i < len(data) and data[i] in b" \t\r\n":
            i += 1
        if data[i] == ord("#"):
            while i < len(data) and data[i] not in b"\r\n":
                i += 1
            continue
        j = i
        while j < len(data) and data[j] not in b" \t\r\n":
            j += 1
        header_tokens.append(data[i:j])
        i = j

    _, w_b, h_b, max_b = header_tokens
    width, height, maxv = int(w_b), int(h_b), int(max_b)
    if maxv != 255:
        raise ValueError("PPM max value must be 255")

    while i < len(data) and data[i] in b" \t\r\n":
        i += 1
    payload = data[i:]
    if len(payload) != width * height * 3:
        raise ValueError("P6 data length mismatch")
    px = [(payload[k], payload[k + 1], payload[k + 2]) for k in range(0, len(payload), 3)]
    return RasterImage(width, height, px)


def write_ppm(path: Path, image: RasterImage) -> None:
    header = f"P6\n{image.width} {image.height}\n255\n".encode("ascii")
    buf = bytearray()
    for r, g, b in image.pixels:
        buf.extend((r, g, b))
    path.write_bytes(header + bytes(buf))


def read_image(path: Path) -> RasterImage:
    if path.suffix.lower() == ".ppm":
        return read_ppm(path)
    img = Image.open(path).convert("RGB")
    w, h = img.size
    raw = img.tobytes()
    pixels = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
    return RasterImage(w, h, pixels)


def write_png(path: Path, image: RasterImage) -> None:
    img = Image.new("RGB", (image.width, image.height))
    img.putdata(image.pixels)
    img.save(path)


def srgb_to_linear(v: int) -> float:
    c = v / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(v: float) -> int:
    v = max(0.0, min(1.0, v))
    if v <= 0.0031308:
        c = 12.92 * v
    else:
        c = 1.055 * (v ** (1.0 / 2.4)) - 0.055
    return int(round(c * 255.0))


def to_linear_pixels(pixels: Sequence[RGB8]) -> List[RGBF]:
    return [(srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)) for r, g, b in pixels]


def from_linear_pixels(pixels: Sequence[RGBF]) -> List[RGB8]:
    return [(linear_to_srgb(r), linear_to_srgb(g), linear_to_srgb(b)) for r, g, b in pixels]


def _dist2(a: RGBF, b: RGBF) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def kmeans_palette(pixels: Sequence[RGBF], k: int, seed: int = 0, iterations: int = 20) -> List[RGBF]:
    if k <= 0:
        raise ValueError("colors must be greater than zero")

    rnd = random.Random(seed)
    centers = [pixels[i] for i in rnd.sample(range(len(pixels)), min(k, len(pixels)))]
    while len(centers) < k:
        centers.append(centers[-1])

    for _ in range(iterations):
        buckets = [[] for _ in range(k)]
        for p in pixels:
            idx = min(range(k), key=lambda i: _dist2(p, centers[i]))
            buckets[idx].append(p)
        next_centers = []
        for i, b in enumerate(buckets):
            if not b:
                next_centers.append(centers[i])
            else:
                inv = 1.0 / len(b)
                next_centers.append((sum(x[0] for x in b) * inv, sum(x[1] for x in b) * inv, sum(x[2] for x in b) * inv))
        centers = next_centers
    return centers


def nearest_palette_color(c: RGBF, palette: Sequence[RGBF]) -> RGBF:
    return min(palette, key=lambda p: _dist2(c, p))


def floyd_steinberg_dither(
    pixels: Sequence[RGBF], width: int, height: int, palette: Sequence[RGBF], serpentine: bool = True
) -> List[RGBF]:
    work = [list(p) for p in pixels]
    out: List[RGBF] = [(0.0, 0.0, 0.0)] * (width * height)

    def add_err(x: int, y: int, err: RGBF, factor: float) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = y * width + x
            work[idx][0] += err[0] * factor
            work[idx][1] += err[1] * factor
            work[idx][2] += err[2] * factor

    for y in range(height):
        ltr = not (serpentine and y % 2 == 1)
        xr = range(width) if ltr else range(width - 1, -1, -1)
        for x in xr:
            idx = y * width + x
            old = (work[idx][0], work[idx][1], work[idx][2])
            new = nearest_palette_color(old, palette)
            out[idx] = new
            err = (old[0] - new[0], old[1] - new[1], old[2] - new[2])
            if ltr:
                add_err(x + 1, y, err, 7 / 16)
                add_err(x - 1, y + 1, err, 3 / 16)
                add_err(x, y + 1, err, 5 / 16)
                add_err(x + 1, y + 1, err, 1 / 16)
            else:
                add_err(x - 1, y, err, 7 / 16)
                add_err(x + 1, y + 1, err, 3 / 16)
                add_err(x, y + 1, err, 5 / 16)
                add_err(x - 1, y + 1, err, 1 / 16)
    return out


def generate_assembly_csv(path: Path, width: int, height: int, tile_mm: float, grout_mm: float, px: Sequence[RGB8]) -> None:
    pitch = tile_mm + grout_mm
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tile_id", "grid_x", "grid_y", "x_mm", "y_mm", "tile_mm", "grout_mm", "r", "g", "b"])
        tid = 1
        for y in range(height):
            for x in range(width):
                r, g, b = px[y * width + x]
                w.writerow([tid, x, y, round(x * pitch, 3), round(y * pitch, 3), tile_mm, grout_mm, r, g, b])
                tid += 1


def generate_svg(path: Path, width: int, height: int, tile_mm: float, grout_mm: float, px: Sequence[RGB8]) -> None:
    pitch = tile_mm + grout_mm
    w_mm = width * pitch
    h_mm = height * pitch
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm}mm" height="{h_mm}mm" viewBox="0 0 {w_mm} {h_mm}">',
        f'  <rect x="0" y="0" width="{w_mm}" height="{h_mm}" fill="rgb(220,220,220)"/>',
    ]
    for y in range(height):
        for x in range(width):
            r, g, b = px[y * width + x]
            lines.append(
                f'  <rect x="{x * pitch:.3f}" y="{y * pitch:.3f}" width="{tile_mm:.3f}" height="{tile_mm:.3f}" fill="rgb({r},{g},{b})"/>'
            )
    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def generate_html_report(
    path: Path,
    source_name: str,
    width: int,
    height: int,
    tile_mm: float,
    grout_mm: float,
    colors: int,
    bom_counts: Dict[RGB8, int],
) -> None:
    total_tiles = width * height
    bom_rows = []
    for (r, g, b), count in sorted(bom_counts.items(), key=lambda kv: kv[1], reverse=True)[:20]:
        swatch = f"<span class='swatch' style='background: rgb({r},{g},{b})'></span>"
        bom_rows.append(
            f"<tr><td>{swatch} rgb({r},{g},{b})</td><td>{count}</td><td>{(count/total_tiles)*100:.2f}%</td></tr>"
        )

    html_doc = f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'/>
<title>Mosaic Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #222; background: #f5f7fa; }}
.card {{ background: white; border-radius: 12px; padding: 16px 20px; box-shadow: 0 2px 10px rgba(0,0,0,.08); margin-bottom: 18px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 8px; }}
small {{ color: #666; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 8px 6px; border-bottom: 1px solid #eee; }}
.swatch {{ display: inline-block; width: 14px; height: 14px; border: 1px solid #3334; vertical-align: -2px; margin-right: 8px; border-radius: 3px; }}
code {{ background: #eef; padding: 1px 5px; border-radius: 4px; }}
</style>
</head>
<body>
<div class='card'>
  <h1>Mosaic Output Report</h1>
  <p><strong>Source:</strong> {html.escape(source_name)}</p>
  <p><strong>Grid:</strong> {width} × {height} ({total_tiles} tiles) &nbsp; <strong>Palette:</strong> {colors} colors</p>
  <p><strong>Tile:</strong> {tile_mm} mm &nbsp; <strong>Grout:</strong> {grout_mm} mm &nbsp; <strong>Pitch:</strong> {tile_mm + grout_mm} mm</p>
  <small>Generated artifacts: <code>mosaic_preview.png</code>, <code>mosaic_preview.ppm</code>, <code>assembly.csv</code>, <code>assembly.svg</code>, <code>bom.csv</code>.</small>
</div>
<div class='grid'>
  <div class='card'>
    <h2>Preview</h2>
    <img src='mosaic_preview.png' alt='Mosaic preview'/>
  </div>
  <div class='card'>
    <h2>Top BOM Colors</h2>
    <table>
      <thead><tr><th>Color</th><th>Count</th><th>Share</th></tr></thead>
      <tbody>
      {''.join(bom_rows)}
      </tbody>
    </table>
  </div>
</div>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    image = read_image(Path(args.input))
    linear = to_linear_pixels(image.pixels)
    palette = kmeans_palette(linear, args.colors, seed=args.seed)
    if args.no_dither:
        mapped = [nearest_palette_color(p, palette) for p in linear]
    else:
        mapped = floyd_steinberg_dither(linear, image.width, image.height, palette, serpentine=not args.no_serpentine)
    mapped8 = from_linear_pixels(mapped)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mapped_image = RasterImage(image.width, image.height, mapped8)
    write_ppm(out_dir / "mosaic_preview.ppm", mapped_image)
    write_png(out_dir / "mosaic_preview.png", mapped_image)
    generate_assembly_csv(out_dir / "assembly.csv", image.width, image.height, args.tile_mm, args.grout_mm, mapped8)
    generate_svg(out_dir / "assembly.svg", image.width, image.height, args.tile_mm, args.grout_mm, mapped8)

    counts: Dict[RGB8, int] = {}
    for rgb in mapped8:
        counts[rgb] = counts.get(rgb, 0) + 1

    with (out_dir / "bom.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["r", "g", "b", "count"])
        for (r, g, b), c in sorted(counts.items(), key=lambda kv: kv[1], reverse=True):
            w.writerow([r, g, b, c])

    generate_html_report(
        out_dir / "report.html",
        source_name=Path(args.input).name,
        width=image.width,
        height=image.height,
        tile_mm=args.tile_mm,
        grout_mm=args.grout_mm,
        colors=args.colors,
        bom_counts=counts,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generate a manufacturable grid mosaic plan.")
    p.add_argument("--input", required=True, help="Input image (ppm/png/jpg/jpeg/bmp)")
    p.add_argument("--output-dir", default="out")
    p.add_argument("--colors", type=int, default=16)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--tile-mm", type=float, default=20.0)
    p.add_argument("--grout-mm", type=float, default=2.0)
    p.add_argument("--no-dither", action="store_true")
    p.add_argument("--no-serpentine", action="store_true")
    return p


def main() -> None:
    run(build_parser().parse_args())


if __name__ == "__main__":
    main()
