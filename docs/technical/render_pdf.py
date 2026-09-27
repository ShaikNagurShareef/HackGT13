"""Rebuild the technical docs' diagrams and combined PDF.

Mermaid sources live in `diagrams/*.mmd`. Each document also embeds its diagrams as fenced
Mermaid blocks (so GitHub renders them), each followed by a figure line that links
`img/<name>.png`; that link names the source file `diagrams/<name>.mmd`.

Usage (from the repository root):
    uv run --with markdown --with pillow python docs/technical/render_pdf.py --sync
        copy every diagrams/<name>.mmd into its fenced block in the documents
    uv run --with markdown --with pillow python docs/technical/render_pdf.py --diagrams all
        render those sources to img/<name>.png with mermaid-cli (--diagrams all: every source)
    uv run --with markdown --with pillow python docs/technical/render_pdf.py
        check the blocks match their sources, then print pathpro_technical_docs.pdf

The PDF is the documents converted to HTML with a print stylesheet, each Mermaid block replaced
by its PNG, printed by headless Chrome (override the binary with the CHROME environment variable).
Images are downscaled and re-encoded as JPEG for print so the PDF
stays under the repository's 5 MB file limit; the files in img/ are untouched.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import markdown
from PIL import Image

HERE = Path(__file__).resolve().parent
DIAGRAMS = HERE / "diagrams"
IMG = HERE / "img"
PDF = HERE / "pathpro_technical_docs.pdf"
MERMAID_CONFIG = DIAGRAMS / "mermaid.json"
DOCS = (
    "README.md",
    "architecture.md",
    "data_and_models.md",
    "api_reference.md",
    "deployment_operations.md",
    "security_privacy.md",
    "testing_quality.md",
)
DEFAULT_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
MERMAID_CLI = ("npx", "-y", "@mermaid-js/mermaid-cli")
CHROME_TIMEOUT_S = 240.0
POLL_S = 0.5
STABLE_S = 3.0
BLOCK_RE = re.compile(r"```mermaid\n(.*?)```", re.S)
FIGURE_IMG_RE = re.compile(r"img/([a-z0-9_]+)\.png")
DOC_LINK_RE = re.compile(r'href="([a-z_]+)\.md(?:#([^"]*))?"')
LOCAL_ANCHOR_RE = re.compile(r'href="#([^"]*)"')
ID_RE = re.compile(r' id="([^"]*)"')
IMG_SRC_RE = re.compile(r'<img([^>]*?) src="([^":]+)"')
PRINT_MAX_WIDTH = {"diagram": 1500, "photo": 900}
PRINT_QUALITY = {"diagram": 76, "photo": 70}

PRINT_CSS = """
@page { size: Letter; margin: 16mm 14mm 16mm 14mm; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; font-size: 9.6pt;
       line-height: 1.42; color: #1b1f24; }
h1 { font-size: 19pt; margin: 0 0 8pt; padding-bottom: 4pt; border-bottom: 2px solid #3b4a8a;
     color: #22306b; }
h2 { font-size: 13.5pt; margin: 16pt 0 6pt; color: #22306b; break-after: avoid; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; break-after: avoid; }
section.doc { break-before: page; }
section.doc:first-of-type { break-before: auto; }
p, li { orphans: 3; widows: 3; }
a { color: #2b4bb3; text-decoration: none; }
code { font-family: Menlo, Consolas, monospace; font-size: 8.4pt; background: #f2f4f7;
       padding: 0 2px; border-radius: 2px; }
pre { background: #f5f7fa; border: 1px solid #dde2ea; padding: 6pt 8pt; font-size: 8pt;
      white-space: pre-wrap; word-break: break-word; break-inside: avoid; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.4pt; }
th, td { border: 1px solid #cfd5df; padding: 3pt 5pt; vertical-align: top; text-align: left; }
th { background: #eef1f7; }
tr { break-inside: avoid; }
td code, th code { word-break: break-word; }
img { max-width: 100%; }
figure.diagram { margin: 8pt 0; text-align: center; break-inside: avoid; }
figure.diagram img { max-height: 225mm; object-fit: contain; }
hr { border: none; border-top: 1px solid #dde2ea; margin: 12pt 0; }
"""


def figure_name(text: str, block_end: int) -> str:
    """The diagram a fenced block belongs to: the first img/<name>.png link after it."""
    match = FIGURE_IMG_RE.search(text, block_end)
    if match is None:
        raise ValueError("a Mermaid block has no img/<name>.png figure line after it")
    return match.group(1)


def sync_blocks(write: bool) -> list[str]:
    """Blocks that differ from their diagrams/<name>.mmd source (rewritten when write=True)."""
    stale: list[str] = []
    for doc in DOCS:
        path = HERE / doc
        text = path.read_text(encoding="utf-8")
        parts: list[str] = []
        last = 0
        for block in BLOCK_RE.finditer(text):
            name = figure_name(text, block.end())
            source = (DIAGRAMS / f"{name}.mmd").read_text(encoding="utf-8")
            if block.group(1) != source:
                stale.append(f"{doc}: {name}")
            parts += [text[last : block.start(1)], source]
            last = block.end(1)
        parts.append(text[last:])
        if write:
            path.write_text("".join(parts), encoding="utf-8")
    return stale


def render_diagrams(names: list[str]) -> None:
    if names == ["all"]:
        names = sorted(p.stem for p in DIAGRAMS.glob("*.mmd"))
    for name in names:
        subprocess.run(  # noqa: S603 (fixed local tool, arguments built here)
            [
                *MERMAID_CLI,
                "-i",
                str(DIAGRAMS / f"{name}.mmd"),
                "-o",
                str(IMG / f"{name}.png"),
                "-c",
                str(MERMAID_CONFIG),
                "--size",
                "2000",
                "-s",
                "2",
                "-b",
                "white",
                "-q",
            ],
            check=True,
        )
        print(f"rendered img/{name}.png")


def _with_figures(text: str) -> str:
    """Swap each Mermaid block for its PNG (the figure line after it stays as the caption)."""

    def figure(block: re.Match[str]) -> str:
        name = figure_name(text, block.end())
        return f'<figure class="diagram"><img src="img/{name}.png" alt="{name}"></figure>\n'

    return BLOCK_RE.sub(figure, text)


def _doc_html(doc: str) -> str:
    stem = Path(doc).stem
    html = markdown.markdown(
        _with_figures((HERE / doc).read_text(encoding="utf-8")),
        extensions=["tables", "fenced_code", "toc", "sane_lists"],
    )
    # One HTML page holds every document: prefix ids per document and point links inside it.
    html = ID_RE.sub(lambda m: f' id="{stem}--{m.group(1)}"', html)
    html = LOCAL_ANCHOR_RE.sub(lambda m: f'href="#{stem}--{m.group(1)}"', html)
    html = DOC_LINK_RE.sub(
        lambda m: f'href="#{m.group(1)}--{m.group(2)}"' if m.group(2) else f'href="#{m.group(1)}"',
        html,
    )
    return f'<section class="doc" id="{stem}">\n{html}\n</section>'


def _print_with_chrome(chrome: str, html_path: Path, profile: Path) -> None:
    """Print to PDF. Headless Chrome can linger after writing the file, so once the PDF has
    stopped growing it is stopped rather than waited on."""
    proc = subprocess.Popen(  # noqa: S603 (local Chrome, arguments built here)
        [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--no-pdf-header-footer",
            "--allow-file-access-from-files",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={PDF}",
            html_path.as_uri(),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + CHROME_TIMEOUT_S
    last_size, stable_since = -1, 0.0
    try:
        while proc.poll() is None and time.monotonic() < deadline:
            time.sleep(POLL_S)
            size = PDF.stat().st_size if PDF.is_file() else -1
            if size <= 0 or size != last_size:
                last_size, stable_since = size, time.monotonic()
            elif time.monotonic() - stable_since >= STABLE_S:
                break
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)


def _print_image(source: Path, out_dir: Path) -> Path:
    """A smaller JPEG copy for print (Chrome embeds JPEGs as they are, but re-encodes PNGs)."""
    kind = "diagram" if source.parent == IMG else "photo"
    with Image.open(source) as image:
        rgb = image.convert("RGB")
    width = PRINT_MAX_WIDTH[kind]
    if rgb.width > width:
        rgb = rgb.resize((width, round(rgb.height * width / rgb.width)), Image.Resampling.LANCZOS)
    target = out_dir / f"{source.stem}.jpg"
    rgb.save(target, quality=PRINT_QUALITY[kind], optimize=True)
    return target


def _with_print_images(html: str, out_dir: Path) -> str:
    def swap(match: re.Match[str]) -> str:
        source = (HERE / match.group(2)).resolve()
        if source.suffix.lower() != ".png" or not source.is_file():
            return match.group(0)
        return f'<img{match.group(1)} src="{_print_image(source, out_dir).as_uri()}"'

    return IMG_SRC_RE.sub(swap, html)


def build_pdf() -> int:
    body = "\n".join(_doc_html(doc) for doc in DOCS)
    page = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<base href="{HERE.as_uri()}/"><title>PathPro technical documentation</title>'
        f"<style>{PRINT_CSS}</style></head><body>{body}</body></html>"
    )
    chrome = os.environ.get("CHROME", DEFAULT_CHROME)
    PDF.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        html_path = Path(tmp) / "pathpro_technical_docs.html"
        html_path.write_text(_with_print_images(page, Path(tmp)), encoding="utf-8")
        _print_with_chrome(chrome, html_path, Path(tmp) / "profile")
    if not PDF.is_file():
        raise RuntimeError("Chrome did not write the PDF")
    pages = len(re.findall(rb"/Type\s*/Page[^s]", PDF.read_bytes()))
    print(f"wrote {PDF.name}: {pages} pages")
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--sync", action="store_true", help="copy .mmd sources into the docs")
    parser.add_argument("--diagrams", nargs="+", metavar="NAME", help="render PNGs, or 'all'")
    args = parser.parse_args()
    if args.sync:
        for item in sync_blocks(write=True):
            print(f"synced {item}")
        return 0
    if args.diagrams:
        render_diagrams(args.diagrams)
        return 0
    stale = sync_blocks(write=False)
    if stale:
        print("Mermaid blocks differ from diagrams/*.mmd (run --sync):", *stale, sep="\n  ")
        return 1
    build_pdf()
    return 0


if __name__ == "__main__":
    sys.exit(main())
