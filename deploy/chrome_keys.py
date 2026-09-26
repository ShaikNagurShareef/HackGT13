"""Drive dedicated Chrome tabs (user-authorized) to create sponsor keys; never print secrets.

Commands:
  open <url>                      open a new window, print its id
  look <window_id>                   print visible buttons/inputs/text (key-like strings masked)
  click <window_id> <text>           click the first button/link whose text contains <text>
  js <window_id> <code>              run JS, print the result (masked)
  save <window_id> <ENV_NAME> <js>   run JS that returns a secret; write it to backend/.env only
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from capture_keys import PATTERNS, write_key  # noqa: E402

SECRET_LIKE = re.compile(
    r"(gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|AQ\.[A-Za-z0-9_.-]{20,}|sk_[a-f0-9]{30,}|postgres(?:ql)?://\S+|"
    r"\b[A-Z0-9]{36}\b|\b[a-f0-9]{32}\b|\b[A-Za-z0-9_-]{40,}\b)"
)


def mask(text: str) -> str:
    return SECRET_LIKE.sub("[MASKED]", text)


def osa(script: str) -> str:
    out = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=60)  # noqa: S603, S607
    if out.returncode != 0:
        raise RuntimeError(mask(out.stderr.strip()))
    return out.stdout.strip()


def run_js(window_id: str, code: str) -> str:
    # AppleScript string literals accept JSON's \" \\ \n escapes, but not \uXXXX.
    escaped = json.dumps(code, ensure_ascii=False)[1:-1]
    # Chrome ids exceed AppleScript's integer range and become reals, so `window id N` and
    # `whose id is N` lookups are unreliable; compare numerically with a tolerance instead.
    return osa(
        'tell application "Google Chrome"\n'
        f"repeat with w in windows\nset d to (id of w) - {int(window_id)}\n"
        f'if d < 1 and d > -1 then return (execute active tab of w javascript "{escaped}")\n'
        'end repeat\nerror "window not found"\nend tell'
    )


def open_tab(url: str) -> str:
    # A separate window keeps the user's own tabs untouched.
    window_id = osa(
        'tell application "Google Chrome"\nset w to make new window\n'
        f'set URL of active tab of w to "{url}"\nreturn id of w\nend tell'
    )
    time.sleep(4)
    return window_id


LOOK = """(() => {
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const btns = [...document.querySelectorAll('button,a[role=button],[role=menuitem],a')]
    .filter(vis).map(e => (e.innerText||e.getAttribute('aria-label')||'').trim()).filter(Boolean);
  const inputs = [...document.querySelectorAll('input,textarea')].filter(vis)
    .map(e => `${e.type}|${e.name||e.id||e.placeholder||''}|len=${(e.value||'').length}`);
  return JSON.stringify({url: location.href, title: document.title,
    buttons: [...new Set(btns)].slice(0, 60), inputs,
    text: document.body.innerText.slice(0, 1500)});
})()"""

CLICK = """(() => {
  const want = %s.toLowerCase();
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
  const el = [...document.querySelectorAll('button,a,[role=button],[role=menuitem],[role=option],label')]
    .filter(vis).find(e => (e.innerText||e.getAttribute('aria-label')||'').trim().toLowerCase().includes(want));
  if (!el) return 'NOT FOUND';
  el.click(); return 'clicked: ' + (el.innerText||el.getAttribute('aria-label')).trim().slice(0, 60);
})()"""


def main(argv: list[str]) -> int:
    cmd = argv[0]
    if cmd == "open":
        print(open_tab(argv[1]))
    elif cmd == "look":
        print(mask(run_js(argv[1], LOOK)))
    elif cmd == "click":
        print(mask(run_js(argv[1], CLICK % json.dumps(argv[2]))))
    elif cmd == "js":
        print(mask(run_js(argv[1], argv[2])))
    elif cmd == "save":
        tab_id, name, code = argv[1], argv[2], argv[3]
        value = run_js(tab_id, code).strip().strip('"')
        pattern = PATTERNS.get(name)
        if not value or (pattern and not pattern.match(value)):
            print(f"not saved: value for {name} does not match the expected format (len={len(value)})")
            return 1
        write_key(name, value)
        print(f"saved {name} (len={len(value)})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
