"""Deterministic Khmer visual news poster (no remote images or unlicensed photos).

Requires Pillow with libraqm + a permitted Noto Sans Khmer font from the system.
The poster is an editorial graphic, not a photograph of any announced gadget.
"""
from __future__ import annotations

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features

SIZE = (1080, 1350)
BG = (11, 17, 39)
CYAN = (38, 192, 245)
LAVENDER = (158, 142, 250)
PALE = (248, 250, 255)
MUTED = (169, 184, 207)
ACCENTS = (CYAN, LAVENDER, (47, 210, 163))
FONT_PATHS = [
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansKhmerUI-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansKhmer-Medium.ttf",
    "/usr/share/fonts/truetype/khmeros/KhmerOS.ttf",
]


def font_path() -> str:
    custom = os.getenv("KHMER_FONT_PATH", "")
    candidates = ([custom] if custom else []) + FONT_PATHS
    for path in candidates:
        if path and Path(path).is_file():
            return path
    raise RuntimeError("Khmer font missing. Install fonts-noto-core or set KHMER_FONT_PATH.")


def font(size: int) -> ImageFont.FreeTypeFont:
    if not features.check("raqm"):
        raise RuntimeError("Pillow must support libraqm for Khmer text shaping")
    return ImageFont.truetype(font_path(), size, layout_engine=ImageFont.Layout.RAQM)


def latin_font(size: int) -> ImageFont.FreeTypeFont:
    for path in ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise RuntimeError("Latin font missing; install fonts-noto-core")


def wrap(draw: ImageDraw.ImageDraw, value: str, face: ImageFont.FreeTypeFont,
         max_width: int, max_lines: int = 2) -> list[str]:
    """Wrap at words; for long unspaced Khmer use safe Unicode clusters."""
    import unicodedata
    value = " ".join(str(value).split())
    words = value.split(" ")
    if len(words) == 1:
        # Retain combining marks and Khmer dependent vowels with base clusters.
        chars = []
        for char in value:
            if chars and (unicodedata.combining(char) or
                          unicodedata.category(char) in ("Mn", "Mc", "Me")):
                chars[-1] += char
            else:
                chars.append(char)
        words = chars
        separator = ""
    else:
        separator = " "
    rows, current = [], ""
    for word in words:
        trial = (current + separator + word) if current else word
        if draw.textlength(trial, font=face) <= max_width:
            current = trial
            continue
        if current:
            rows.append(current)
            current = word
        else:
            rows.append(word)
            current = ""
        if len(rows) == max_lines:
            break
    if current and len(rows) < max_lines:
        rows.append(current)
    if not rows:
        return ["—"]
    # Truncate overflowing last row only when additional text exists.
    remaining = value
    for row in rows:
        remaining = remaining.replace(row, "", 1).strip()
    if remaining:
        last = rows[-1]
        while last and draw.textlength(last + "…", font=face) > max_width:
            last = last[:-1]
        rows[-1] = last + "…"
    return rows[:max_lines]


def draw_rows(draw: ImageDraw.ImageDraw, lines: list[str], x: int, y: int,
              face: ImageFont.FreeTypeFont, color, line_height: int) -> None:
    for row in lines:
        draw.text((x, y), row, font=face, fill=color, stroke_width=0,
                  language="km")
        y += line_height


def render_poster(edition: str, stories: list[dict], stamp: str, destination: Path) -> Path:
    if not 1 <= len(stories) <= 3:
        raise ValueError("A visual poster requires one to three sourced articles")
    if edition not in {"cambodia", "global", "tech", "gadget"}:
        raise ValueError("Unknown visual edition")
    names = {
        "cambodia": ("ព័ត៌មានកម្ពុជា", "CAMBODIA NEWS"),
        "global": ("ព័ត៌មានពិភពលោក", "GLOBAL NEWS"),
        "tech": ("ព័ត៌មានបច្ចេកវិទ្យា", "AI & SOFTWARE"),
        "gadget": ("ទូរស័ព្ទ និងឧបករណ៍", "GADGET FRIDAY"),
    }
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
    draw.text((78, 242), names[edition][0], font=font(70), fill=PALE, language="km")
    draw.text((80, 354), names[edition][1], font=latin_font(35), fill=CYAN)
    draw.text((80, 422), stamp[:40], font=latin_font(24), fill=MUTED)

    title_font = font(37)
    source_font = latin_font(24)
    y0 = 510
    for index, story in enumerate(stories):
        y = y0 + index * 225
        accent = ACCENTS[index]
        draw.rounded_rectangle((78, y, 1002, y + 198), radius=24, fill=(31, 39, 73))
        draw.rounded_rectangle((78, y, 89, y + 198), radius=6, fill=accent)
        draw.text((112, y + 16), f"{index + 1:02d}", font=latin_font(29), fill=accent)
        headline = str(story.get("khmer_title") or story["title"])
        headline_font = title_font if any("\u1780" <= ch <= "\u17ff" for ch in headline) else latin_font(33)
        lines = wrap(draw, headline, headline_font, 790, max_lines=2)
        draw_rows(draw, lines, 181, y + 11, headline_font, PALE, 66)
        publisher = str(story["publisher"])[:48]
        draw.text((181, y + 149), publisher, font=source_font, fill=MUTED)
    draw.line((80, 1230, 1002, 1230), fill=(78, 93, 131), width=2)
    draw.text((80, 1252), "@dailynewsagents", font=latin_font(24), fill=CYAN)
    draw.text((565, 1252), "អានព័ត៌មានតាមប្រភពដើម", font=font(25),
              fill=MUTED, language="km")
    destination.parent.mkdir(parents=True, exist_ok=True)
    poster.save(destination, format="PNG", optimize=True)
    return destination
