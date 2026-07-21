"""Browser JS-execution tool via Playwright, ported from real/scripts/real_runner.py.

See browser_navigate.py for why each call runs in an isolated subprocess.
"""

import json
import subprocess
import sys

BROWSER_TIMEOUT_MS = 15000
SUBPROCESS_TIMEOUT_S = BROWSER_TIMEOUT_MS // 1000 + 10
CHROMIUM_PATH = "/usr/bin/chromium-browser"


def browser_execute_js(url: str, script: str) -> str:
    """Navigates to a URL and executes JavaScript on it, returning the result.

    Useful for SPA/dynamic pages where static HTML doesn't contain the content.

    Args:
        url: URL to navigate to before running the script.
        script: JS expression to evaluate. Must evaluate to a value (a leading
            "return " is stripped automatically, since Playwright's evaluate()
            expects an expression, not a statement).

    Returns:
        The JS result as a string (JSON-encoded if it's not already a string).
        Returns a "[ERRO browser] ..." string on timeout or any other failure —
        never raises.
    """
    op = {"action": "execute_js", "url": url, "script": script}
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
        js = op['script'].strip()
        if js.startswith('return '):
            js = js[len('return '):]
        val = page.evaluate(js)
        if isinstance(val, str):
            result = val
        else:
            result = json.dumps(val, ensure_ascii=False, default=str)
    except Exception as e:
        result = f'erro JS: {{e}}'

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
