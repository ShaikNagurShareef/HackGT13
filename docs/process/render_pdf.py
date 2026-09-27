"""Render docs/process/process_notes.md to process_notes.pdf.

Markdown -> HTML (python-markdown, with a print stylesheet) -> PDF (headless Chrome).

Usage (from the repo root):
    uv run --with markdown python docs/process/render_pdf.py
    # or: python3 docs/process/render_pdf.py   (with `markdown` installed)

Set CHROME to the browser binary if it isn't at the default macOS path.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "process_notes.md"
TARGET = HERE / "process_notes.pdf"
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TIMEOUT_S = 120

PRINT_CSS = """
@page { size: Letter; margin: 16mm 15mm 18mm 15mm; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body {
  font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 10.5pt; line-height: 1.45; color: #1b1f24; background: #fff;
}
h1 { font-size: 20pt; margin: 0 0 6pt; color: #0b4f4a; }
h2 { font-size: 14pt; margin: 16pt 0 6pt; padding-bottom: 3pt;
     border-bottom: 1px solid #cfd8dc; color: #0b4f4a; break-after: avoid; }
h3 { font-size: 12pt; margin: 12pt 0 4pt; color: #12324a; break-after: avoid; }
p, li { orphans: 3; widows: 3; }
ul, ol { padding-left: 18pt; }
code { font-family: Menlo, Consolas, monospace; font-size: 9pt;
       background: #f1f4f6; padding: 0 2pt; border-radius: 2pt; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; }
th, td { border: 1px solid #cfd8dc; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #e8f1f0; }
tr { break-inside: avoid; }
img { max-width: 100%; max-height: 90mm; display: block; margin: 6pt auto; break-inside: avoid; }
a { color: #0b6b63; text-decoration: none; }
"""


def build_html(text: str) -> str:
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    base = HERE.as_uri() + "/"  # relative image paths resolve against docs/process/
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        f"<base href='{base}'><title>PathPro process notes</title>"
        f"<style>{PRINT_CSS}</style></head><body>{body}</body></html>"
    )


def render(chrome: str) -> None:
    html = build_html(SOURCE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "process_notes.html"
        page.write_text(html, encoding="utf-8")
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--allow-file-access-from-files",
                f"--print-to-pdf={TARGET}",
                page.as_uri(),
            ],
            check=True,
            timeout=TIMEOUT_S,
            capture_output=True,
        )


def main() -> int:
    chrome = os.environ.get("CHROME", DEFAULT_CHROME)
    if not Path(chrome).exists():
        print(f"Chrome not found at {chrome}; set CHROME to the browser binary.", file=sys.stderr)
        return 1
    try:
        render(chrome)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(f"PDF render failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    print(f"Wrote {TARGET.relative_to(HERE.parents[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
