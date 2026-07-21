"""Browser navigation tool via Playwright, ported from real/scripts/real_runner.py.

Runs each navigation in an isolated subprocess (fresh `python3 -c <script>` call)
rather than keeping a persistent browser instance, matching the original REAL
harness behavior — avoids asyncio/sync-API conflicts with the caller's event loop
and keeps browser state fully isolated between tool calls.
"""

import json
import subprocess
import sys
from typing import Optional

BROWSER_TIMEOUT_MS = 15000
SUBPROCESS_TIMEOUT_S = BROWSER_TIMEOUT_MS // 1000 + 10
CHROMIUM_PATH = "/usr/bin/chromium-browser"


def browser_navigate(url: str, wait_selector: Optional[str] = None) -> str:
    """Navigates to a URL with headless Chromium and returns the page text.

    JavaScript on the page runs automatically before the text is extracted.

    Args:
        url: URL to navigate to.
        wait_selector: Optional CSS selector to wait for before reading the page.

    Returns:
        A string with title, final URL, and up to 6000 chars of visible body text.
        Returns a "[ERRO browser] ..." string on timeout or any other failure —
        never raises, so a bad URL doesn't abort the caller's tool loop.
    """
    op = {"action": "navigate", "url": url, "wait_selector": wait_selector}
    script = f"""
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
    if op.get('wait_selector'):
        try:
            page.wait_for_selector(op['wait_selector'], timeout=5000)
        except Exception:
            pass
    text = page.inner_text('body')[:6000]
    title = page.title()
    final_url = page.url
    result = f"[Título: {{title}}]\\n[URL: {{final_url}}]\\n\\n{{text}}"

    browser.close()
    print(result)
"""
    try:
        r = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_S,
        )
        if r.returncode != 0:
            return f"[ERRO browser] {r.stderr[:400]}"
        return r.stdout.strip() or "[sem conteúdo]"
    except subprocess.TimeoutExpired:
        return f"[ERRO browser] timeout após {BROWSER_TIMEOUT_MS // 1000}s"
    except Exception as e:
        return f"[ERRO browser] {e}"
