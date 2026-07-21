"""Browser element-text tool via Playwright, ported from real/scripts/real_runner.py.

See browser_navigate.py for why each call runs in an isolated subprocess.
"""

import json
import subprocess
import sys

BROWSER_TIMEOUT_MS = 15000
SUBPROCESS_TIMEOUT_S = BROWSER_TIMEOUT_MS // 1000 + 10
CHROMIUM_PATH = "/usr/bin/chromium-browser"


def browser_get_element(url: str, selector: str) -> str:
    """Navigates to a URL and returns the text content of one CSS-selected element.

    Args:
        url: URL to navigate to.
        selector: CSS selector of the target element.

    Returns:
        The element's inner text, or "elemento não encontrado" if the selector
        doesn't match within 5s. Returns a "[ERRO browser] ..." string on
        timeout or any other failure — never raises.
    """
    op = {"action": "get_element", "url": url, "selector": selector}
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
    try:
        el = page.wait_for_selector(op['selector'], timeout=5000)
        result = el.inner_text() if el else 'elemento não encontrado'
    except Exception:
        result = 'elemento não encontrado'

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
