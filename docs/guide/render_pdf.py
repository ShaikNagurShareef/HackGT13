"""Render docs/guide/user_guide.md to user_guide.pdf (Markdown -> print HTML -> headless Chrome).

Usage (from the repo root):
    uv run --no-project --with markdown --with pillow python docs/guide/render_pdf.py

Screenshots are embedded as downscaled JPEG copies (made in a temp folder) to keep the PDF small;
the PNGs in img/ are left untouched.

Set CHROME to a Chrome/Chromium binary if it is not in the default macOS location.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown
from PIL import Image

GUIDE_DIR = Path(__file__).resolve().parent
SOURCE = GUIDE_DIR / "user_guide.md"
TARGET = GUIDE_DIR / "user_guide.pdf"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TITLE = "PathPro User Guide"
PRINT_MAX_PX = 900  # about 190 dpi at the printed size
JPEG_QUALITY = 82

PRINT_CSS = """
@page { size: Letter; margin: 16mm 16mm 18mm; }
:root { --ink: #14202b; --muted: #55626e; --accent: #0f8f82; --rule: #d8dee4; --tint: #f2f6f8; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: var(--ink);
  background: #fff; margin: 0; }
h1 { font-size: 24pt; margin: 0 0 4pt; color: var(--accent); }
h2 { font-size: 15pt; margin: 20pt 0 6pt; padding-bottom: 3pt;
  border-bottom: 1.5pt solid var(--accent); break-after: avoid; }
h3 { font-size: 12pt; margin: 14pt 0 4pt; break-after: avoid; }
h2 + p, h3 + p { break-before: avoid; }
p, li { orphans: 3; widows: 3; }
a { color: var(--accent); text-decoration: none; }
ul, ol { padding-left: 18pt; }
li { margin: 2pt 0; }
blockquote { margin: 8pt 0; padding: 6pt 10pt; background: var(--tint);
  border-left: 3pt solid var(--accent); }
blockquote p { margin: 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9.5pt;
  break-inside: avoid; }
th, td { border: 0.75pt solid var(--rule); padding: 4pt 6pt; text-align: left;
  vertical-align: top; }
th { background: var(--tint); }
code { font: 9pt Menlo, Consolas, monospace; }
figure { margin: 10pt 0; text-align: center; break-inside: avoid; }
figure img { max-width: 100%; border: 0.75pt solid var(--rule); border-radius: 6pt; }
figure.phone img { max-height: 100mm; max-width: 55%; }
figure.desktop img { max-height: 95mm; }
figcaption { font-size: 9pt; color: var(--muted); margin: 4pt auto 0; max-width: 85%; }
"""

# A paragraph that holds only an image becomes a captioned figure (alt text is the caption).
IMAGE_PARAGRAPH = re.compile(r'<p><img alt="([^"]*)" src="([^"]+)" ?/?></p>')


def print_copy(src: str, out_dir: Path) -> str:
    """A downscaled JPEG of one screenshot, as a file URI for Chrome."""
    target = out_dir / (Path(src).stem + ".jpg")
    with Image.open(GUIDE_DIR / src) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((PRINT_MAX_PX, PRINT_MAX_PX * 3))
        rgb.save(target, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return target.as_uri()


def build_html(md_text: str, image_dir: Path) -> str:
    body = markdown.markdown(md_text, extensions=["tables", "toc", "sane_lists"])

    def figure(match: re.Match[str]) -> str:
        alt, src = match.group(1), match.group(2)
        kind = "phone" if "phone" in Path(src).name else "desktop"
        img = f'<img alt="{alt}" src="{print_copy(src, image_dir)}">'
        return f'<figure class="{kind}">{img}<figcaption>{alt}</figcaption></figure>'

    body = IMAGE_PARAGRAPH.sub(figure, body)
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{TITLE}</title>'
        f"<style>{PRINT_CSS}</style></head><body>{body}</body></html>"
    )


def render(chrome: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        html_path = work / "user_guide.html"
        html_path.write_text(build_html(SOURCE.read_text(encoding="utf-8"), work), encoding="utf-8")
        # Fixed argument list; the only input is the local Chrome path (default or $CHROME).
        subprocess.run(  # noqa: S603
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={TARGET}",
                html_path.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
    print(f"wrote {TARGET.relative_to(GUIDE_DIR.parent.parent)}")


if __name__ == "__main__":
    chrome_bin = os.environ.get("CHROME", DEFAULT_CHROME)
    if not Path(chrome_bin).exists():
        sys.exit(f"Chrome not found at {chrome_bin}; set CHROME to a Chrome/Chromium binary.")
    render(chrome_bin)
