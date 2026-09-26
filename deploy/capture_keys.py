"""Capture sponsor API keys from the macOS clipboard into backend/.env.

Click "Copy" on each dashboard; keys are recognized by format and written to the right line.
Only strings matching a key format are kept, values are never printed, and the watcher stops
when every key is captured or after the time limit.

Usage: python3 deploy/capture_keys.py [minutes]
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"
PATTERNS: dict[str, re.Pattern[str]] = {
    "DATABASE_URL": re.compile(r"^postgres(?:ql)?://\S+$"),
    "GROQ_API_KEY": re.compile(r"^gsk_[A-Za-z0-9]{40,}$"),
    "GEMINI_API_KEY": re.compile(r"^(?:AIza[0-9A-Za-z_-]{35}|AQ\.[A-Za-z0-9_.-]{20,})$"),
    "ELEVENLABS_API_KEY": re.compile(r"^sk_[a-f0-9]{40,}$"),
    "VULTR_API_KEY": re.compile(r"^[A-Z0-9]{36}$"),
    "ELEVENLABS_VOICE_ID": re.compile(r"^[A-Za-z0-9]{20}$"),
    "GEOAPIFY_API_KEY": re.compile(r"^[a-f0-9]{32}$"),
}
POLL_S = 0.5


def clipboard() -> str:
    out = subprocess.run(["pbpaste"], capture_output=True, text=True, check=False)
    return out.stdout.strip()


def current_values() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip()
    return values


def write_key(name: str, value: str) -> None:
    lines = ENV.read_text().splitlines()
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == name:
            lines[i] = f"{name}={value}"
            break
    else:
        lines.append(f"{name}={value}")
    ENV.write_text("\n".join(lines) + "\n")
    ENV.chmod(0o600)


ASSIGNMENT = re.compile(r"^(?:export\s+)?([A-Z_]+)\s*[=:]\s*(.+)$")


def unwrap(text: str) -> tuple[str | None, str]:
    """Strip quotes and `export NAME=value` / `NAME: value` wrappers some copy buttons add."""
    hinted: str | None = None
    match = ASSIGNMENT.match(text.strip())
    if match:
        hinted, text = match.group(1), match.group(2)
    return hinted, text.strip().strip("'\"").strip()


def classify(text: str) -> str | None:
    hinted, value = unwrap(text)
    if hinted in PATTERNS and value:
        return hinted
    for name, pattern in PATTERNS.items():
        if pattern.match(value):
            return name
    return None


def shape(text: str) -> str:
    """Describe unrecognized text without revealing it: length and character classes."""
    classes = [label for label, rx in (("A-Z", "[A-Z]"), ("a-z", "[a-z]"), ("0-9", "[0-9]"),
               ("_", "_"), ("-", "-"), ("space", r"\s"), ("other", r"[^A-Za-z0-9_\-\s]"))
               if re.search(rx, text)]
    return f"len={len(text)} chars=[{' '.join(classes)}]"


def main(minutes: float) -> int:
    deadline = time.monotonic() + minutes * 60
    last = clipboard()  # ignore whatever was already on the clipboard
    print(f"watching clipboard for {minutes:.0f} min", flush=True)
    while time.monotonic() < deadline:
        missing = [k for k in PATTERNS if not current_values().get(k)]
        if not missing:
            print("all keys captured", flush=True)
            return 0
        text = clipboard()
        if text and text != last:
            last = text
            name = classify(text)
            if name is None:
                print(f"not a recognized key format (ignored): {shape(text)}", flush=True)
            elif current_values().get(name) == unwrap(text)[1]:
                print(f"already have {name}", flush=True)
            else:
                write_key(name, unwrap(text)[1])
                left = [k for k in PATTERNS if not current_values().get(k)]
                print(f"captured {name} | still needed: {', '.join(left) or 'none'}", flush=True)
        time.sleep(POLL_S)
    print("clipboard watch timed out", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 20.0))
