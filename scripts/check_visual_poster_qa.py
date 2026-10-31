#!/usr/bin/env python3
"""Offline visual QA: glyph coverage, Khmer syllables, mixed-script PNG.

This checks mechanical rendering. A human must still review Khmer grammar and
source claims before publication.
"""
from pathlib import Path

from PIL import Image, ImageDraw
from visual_poster import (graphemes, measure, mixed_text, render_poster,
                           verify_glyph_coverage, wrap)
from visual_quality import normalize_visual_text


def main() -> int:
    mixed = "Apple MacBook Pro OLED និង Samsung W27"
    verify_glyph_coverage(mixed)
    assert normalize_visual_text(mixed, require_khmer=True) == mixed
    assert graphemes("ក្ខ") == ["ក្ខ"], "Khmer coeng/subscript must stay together"

    for invalid in ("បច្ចេកវិទ្យា □□□□", "ព័ត៌មាន 世界", "សេចក្ដីជូនដំណឹង �"):
        try:
            verify_glyph_coverage(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Failed to reject unsupported poster text: {invalid!r}")

    image = Image.new("RGB", (880, 210), (12, 17, 38))
    canvas = ImageDraw.Draw(image)
    lines = wrap(canvas, mixed, 34, 720)
    assert all(measure(canvas, line, 34) <= 720 for line in lines)
    for index, line in enumerate(lines):
        mixed_text(canvas, line, 24, 18 + index * 65, 34, (250, 250, 250))

    cases = [
        {"title": mixed, "khmer_title": mixed, "publisher": "MacRumors"},
        {"title": "ក្រសួងប្រកាសព័ត៌មានថ្មីអំពីបច្ចេកវិទ្យា",
         "khmer_title": "ក្រសួងប្រកាសព័ត៌មានថ្មីអំពីបច្ចេកវិទ្យា",
         "publisher": "Khmer Times"},
        {"title": "ព័ត៌មានថ្មីអំពីសុវត្ថិភាពតាមអ៊ីនធឺណិត",
         "khmer_title": "ព័ត៌មានថ្មីអំពីសុវត្ថិភាពតាមអ៊ីនធឺណិត",
         "publisher": "BBC News"},
    ]
    out = Path("out/visual/qa-mixed-script.png")
    render_poster("tech", cases, "QA ONLY · TEST", out)
    with Image.open(out) as png:
        png.verify()
    with Image.open(out) as png:
        assert png.size == (1080, 1350)
    print("PASS: mixed Khmer/English glyphs, Khmer coeng clusters, line widths, invalid symbols and PNG rendering")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
