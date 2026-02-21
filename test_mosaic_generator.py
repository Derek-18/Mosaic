import tempfile
import unittest
from pathlib import Path

from PIL import Image

from mosaic_generator import (
    RasterImage,
    floyd_steinberg_dither,
    generate_assembly_csv,
    generate_html_report,
    generate_svg,
    kmeans_palette,
    nearest_palette_color,
    read_image,
    read_ppm,
    run,
    to_linear_pixels,
    write_ppm,
)


class MosaicGeneratorTests(unittest.TestCase):
    def test_ppm_roundtrip(self):
        img = RasterImage(2, 2, [(255, 0, 0), (0, 255, 0), (0, 0, 255), (10, 20, 30)])
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.ppm"
            write_ppm(p, img)
            b = read_ppm(p)
            self.assertEqual(img, b)

    def test_read_image_jpeg(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.jpg"
            Image.new("RGB", (2, 1), color=(12, 34, 56)).save(p)
            img = read_image(p)
            self.assertEqual((2, 1), (img.width, img.height))

    def test_kmeans_deterministic(self):
        px = to_linear_pixels([(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0)])
        self.assertEqual(kmeans_palette(px, 2, seed=42), kmeans_palette(px, 2, seed=42))

    def test_dither_palette_membership(self):
        src = to_linear_pixels([(i, i, i) for i in (0, 64, 128, 192, 255, 127)])
        palette = to_linear_pixels([(0, 0, 0), (255, 255, 255)])
        out = floyd_steinberg_dither(src, width=3, height=2, palette=palette, serpentine=True)
        for c in out:
            self.assertIn(nearest_palette_color(c, palette), palette)

    def test_csv_svg_and_html_generation(self):
        pixels = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        with tempfile.TemporaryDirectory() as td:
            csv_p = Path(td) / "assembly.csv"
            svg_p = Path(td) / "assembly.svg"
            html_p = Path(td) / "report.html"
            generate_assembly_csv(csv_p, 2, 2, 20.0, 2.0, pixels)
            generate_svg(svg_p, 2, 2, 20.0, 2.0, pixels)
            generate_html_report(
                html_p,
                source_name="example.jpg",
                width=2,
                height=2,
                tile_mm=20.0,
                grout_mm=2.0,
                colors=4,
                bom_counts={(255, 0, 0): 1, (0, 255, 0): 1, (0, 0, 255): 1, (255, 255, 0): 1},
            )
            self.assertTrue(csv_p.exists())
            self.assertTrue(svg_p.exists())
            self.assertTrue(html_p.exists())
            self.assertIn("rgb(255,0,0)", svg_p.read_text(encoding="utf-8"))
            self.assertIn("Mosaic Output Report", html_p.read_text(encoding="utf-8"))

    def test_end_to_end_creates_ui_report(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            input_path = base / "input.jpg"
            Image.new("RGB", (3, 2), color=(100, 120, 140)).save(input_path)

            class Args:
                input = str(input_path)
                output_dir = str(base / "out")
                colors = 4
                seed = 1
                tile_mm = 20.0
                grout_mm = 2.0
                no_dither = False
                no_serpentine = False

            run(Args)
            out = base / "out"
            self.assertTrue((out / "mosaic_preview.png").exists())
            self.assertTrue((out / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
