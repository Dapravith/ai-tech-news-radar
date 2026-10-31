"""Source-attributed Khmer news graphics with mixed-script shaping and glyph checks.

Requires Pillow with libraqm, fonttools, and Noto Sans + Noto Sans Khmer.
Never upload unreviewed posters automatically to the public channel.
"""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import unicodedata

from PIL import Image, ImageDraw, ImageFont, features
from fontTools.ttLib import TTFont
from visual_quality import normalize_visual_text

SIZE = (1080, 1350)
BG = (11, 17, 39)
CYAN = (38, 192, 245)
LAVENDER = (158, 142, 250)
PALE = (248, 250, 255)
MUTED = (169, 184, 207)
ACCENTS = (CYAN, LAVENDER, (47, 210, 163))
FONT_PATHS = (
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansKhmerUI-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Medium.ttf",
    "/usr/share/fonts/truetype/khmeros/KhmerOS.ttf",
)
LATIN_FONT_PATHS = (
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def first_existing(paths: tuple[str, ...]) -> str:
    for path in paths:
        if path and Path(path).is_file():
            return path
    raise RuntimeError("Required Khmer/Latin font not installed; install fonts-noto-core")


def font_path() -> str:
    custom = os.getenv("KHMER_FONT_PATH", "")
    return first_existing(((custom,) if custom else ()) + FONT_PATHS)


def latin_path() -> str:
    return first_existing(LATIN_FONT_PATHS)


@lru_cache(maxsize=12)
def face(path: str, size: int) -> ImageFont.FreeTypeFont:
    if not features.check("raqm"):
        raise RuntimeError("Pillow needs libraqm to shape Khmer consonants and dependent vowels")
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)


def font(size: int) -> ImageFont.FreeTypeFont:
    return face(font_path(), size)


def latin_font(size: int) -> ImageFont.FreeTypeFont:
    return face(latin_path(), size)


@lru_cache(maxsize=6)
def glyphs(path: str) -> frozenset[int]:
    ft = TTFont(path, lazy=True)
    try:
        return frozenset(ft.getBestCmap().keys())
    finally:
        ft.close()


def is_khmer(char: str) -> bool:
    return 0x1780 <= ord(char) <= 0x17FF


def runs(value: str):
    """Group only adjacent characters of the same script for proper shaping."""
    current, script = "", None
    for char in value:
        group = "khmer" if is_khmer(char) else "latin"
        if current and group != script:
            yield script, current
            current = ""
        script, current = group, current + char
    if current:
        yield script, current


def verify_glyph_coverage(value: str) -> None:
    value = normalize_visual_text(value, max_length=280)
    faces = {"khmer": glyphs(font_path()), "latin": glyphs(latin_path())}
    for script, text in runs(value):
        unsupported = [ch for ch in text if ord(ch) not in faces[script]]
        if unsupported:
            raise ValueError(
                f"Poster glyph not supported by {script} font: U+{ord(unsupported[0]):04X}. "
                "Do not render a missing-glyph square."
            )


def measure(draw: ImageDraw.ImageDraw, value: str, size: int) -> float:
    return sum(draw.textlength(part, font=font(size) if script == "khmer"
                               else latin_font(size))
               for script, part in runs(value))


def mixed_text(draw: ImageDraw.ImageDraw, value: str, x: float, y: float,
               size: int, fill) -> None:
    verify_glyph_coverage(value)
    for script, part in runs(value):
        selected = font(size) if script == "khmer" else latin_font(size)
        draw.text((x, y), part, font=selected, fill=fill,
                  language="km" if script == "khmer" else "en")
        x += draw.textlength(part, font=selected)


def graphemes(value: str) -> list[str]:
    """Keep Khmer coeng + subscript consonants and combining vowels together."""
    output = []
    for char in value:
        combine = (unicodedata.category(char) in {"Mn", "Mc", "Me"} or
                   char == "\u17D2" or (output and output[-1].endswith("\u17D2")))
        if output and combine:
            output[-1] += char
        else:
            output.append(char)
    return output


def wrap(draw: ImageDraw.ImageDraw, value: str, size: int,
         max_width: int, max_lines: int = 2) -> list[str]:
    """Wrap on spaces first; split oversized tokens at safe grapheme boundaries."""
    value = normalize_visual_text(value, max_length=180)
    verify_glyph_coverage(value)
    output, line = [], ""
    tokens = value.split(" ")
    for token in tokens:
        candidate = (line + " " + token) if line else token
        if measure(draw, candidate, size) <= max_width:
            line = candidate
            continue
        if line:
            output.append(line)
            line = ""
            if len(output) >= max_lines:
                break
        if measure(draw, token, size) <= max_width:
            line = token
            continue
        for cluster in graphemes(token):
            if measure(draw, line + cluster, size) <= max_width:
                line += cluster
            else:
                if line:
                    output.append(line)
                line = cluster
                if len(output) >= max_lines:
                    break
        if len(output) >= max_lines:
            break
    if line and len(output) < max_lines:
        output.append(line)
    if not output:
        raise ValueError("Poster headline cannot fit")
    if " ".join(output) != value:
        last = output[-1]
        while last and measure(draw, last + "…", size) > max_width:
            last = "".join(graphemes(last)[:-1])
        if not last:
            raise ValueError("Poster headline has no place for an ellipsis")
        output[-1] = last + "…"
    if any(measure(draw, line, size) > max_width for line in output):
        raise ValueError("Poster headline exceeds card width")
    return output


def render_poster(edition: str, stories: list[dict], stamp: str, destination: Path) -> Path:
    if not 1 <= len(stories) <= 3:
        raise ValueError("A visual poster needs 1–3 articles")
    names = {
        "cambodia": ("ព័ត៌មានកម្ពុជា", "CAMBODIA NEWS"),
        "global": ("ព័ត៌មានពិភពលោក", "GLOBAL NEWS"),
        "tech": ("ព័ត៌មានបច្ចេកវិទ្យា", "AI & SOFTWARE"),
        "gadget": ("ទូរស័ព្ទ និងឧបករណ៍", "GADGET FRIDAY"),
    }
    if edition not in names:
        raise ValueError("Unrecognized news edition")
    stamp = normalize_visual_text(stamp, max_length=70)
    for item in stories:
        verify_glyph_coverage(item.get("khmer_title") or item["title"])
        verify_glyph_coverage(item["publisher"])
    verify_glyph_coverage(names[edition][0])
    verify_glyph_coverage("អានព័ត៌មានតាមប្រភពដើម")

    poster = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(poster)
    for x in range(0, SIZE[0], 60):
        draw.line((x, 0, x, SIZE[1]), fill=(19, 27, 53), width=1)
    for y in range(0, SIZE[1], 60):
        draw.line((0, y, SIZE[0], y), fill=(19, 27, 53), width=1)

    draw.rounded_rectangle((70, 74, 156, 158), radius=22, fill=(38, 123, 214))
    draw.text((92, 91), "N", font=latin_font(45), fill=PALE)
    draw.text((180, 82), "AI TECH RADAR", font=latin_font(40), fill=PALE)
    draw.text((180, 143), "KHMER NEWS EDITION", font=latin_font(21), fill=MUTED)
    mixed_text(draw, names[edition][0], 78, 242, 70, PALE)
    draw.text((80, 354), names[edition][1], font=latin_font(35), fill=CYAN)
    draw.text((80, 422), stamp[:48], font=latin_font(24), fill=MUTED)

    for index, item in enumerate(stories):
        y = 510 + index * 225
        draw.rounded_rectangle((78, y, 1002, y + 198), radius=24, fill=(31, 39, 73))
        draw.rounded_rectangle((78, y, 89, y + 198), radius=6, fill=ACCENTS[index])
        draw.text((112, y + 16), f"{index + 1:02d}", font=latin_font(29), fill=ACCENTS[index])

        headline = normalize_visual_text(item.get("khmer_title") or item["title"])
        size = 36
        # Prefer full headline with smaller type; never draw outside the card.
        while size > 28 and measure(draw, headline, size) > 2 * 790:
            size -= 2
        lines = wrap(draw, headline, size, 790, max_lines=2)
        for offset, line in enumerate(lines):
            mixed_text(draw, line, 181, y + 10 + offset * 68, size, PALE)
        mixed_text(draw, str(item["publisher"])[:60], 181, y + 148, 23, MUTED)

    draw.line((80, 1230, 1002, 1230), fill=(78, 93, 131), width=2)
    draw.text((80, 1252), "@dailynewsagents", font=latin_font(24), fill=CYAN)
    mixed_text(draw, "អានព័ត៌មានតាមប្រភពដើម", 565, 1252, 25, MUTED)
    destination.parent.mkdir(parents=True, exist_ok=True)
    poster.save(destination, format="PNG", optimize=True)
    return destination
