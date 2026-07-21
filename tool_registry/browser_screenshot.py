"""Browser screenshot tool via Playwright, ported from real/scripts/real_runner.py.

See browser_navigate.py for why each call runs in an isolated subprocess.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

BROWSER_TIMEOUT_MS = 15000
SUBPROCESS_TIMEOUT_S = BROWSER_TIMEOUT_MS // 1000 + 10
CHROMIUM_PATH = "/usr/bin/chromium-browser"


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def browser_screenshot(url: str, filename: str) -> str:
    """Navigates to a URL and saves a screenshot to a file in AGENT_WORKDIR.

    Args:
        url: URL to navigate to before capturing.
        filename: Name of the .png file to write, relative to AGENT_WORKDIR.

    Returns:
        A confirmation string with the saved path, or a "[ERRO browser] ..."
        string on timeout or any other failure — never raises.
    """
    path = str((_workdir() / filename).resolve())
    op = {"action": "screenshot", "url": url, "path": path}
    script_body = f"""
import sys, json
from playwright.sync_api import sync_playwright

op = json.loads({json.dumps(json.dumps(op))})

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        executable_path='{CHROMIUM_PATH}',
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    )
    ctx = browser.new_context(viewport={{'width': 1280, 'height': 900}})
    page = ctx.new_page()
    page.set_default_timeout({BROWSER_TIMEOUT_MS})

    page.goto(op['url'], wait_until='domcontentloaded')
    page.screenshot(path=op['path'], full_page=False)
    result = f"Screenshot salvo: {{op['path']}}"

    browser.close()
    print(result)
"""
    try:
        r = subprocess.run(
            [sys.executable, "-c", script_body],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S,
        )
        if r.returncode != 0:
            return f"[ERRO browser] {r.stderr[:400]}"
        return r.stdout.strip() or "[sem conteúdo]"
    except subprocess.TimeoutExpired:
        return f"[ERRO browser] timeout após {BROWSER_TIMEOUT_MS // 1000}s"
    except Exception as e:
        return f"[ERRO browser] {e}"
