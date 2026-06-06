from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser

HTTP_MAX_CHARS = 4000


class _HTMLTextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "nav", "footer", "head", "meta", "link", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


def _html_to_text(raw: str) -> str:
    if "<html" not in raw.lower() and "<body" not in raw.lower():
        return raw
    try:
        extractor = _HTMLTextExtractor()
        extractor.feed(raw)
        text = extractor.get_text()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text if text.strip() else raw
    except Exception:
        return raw


def http_get(url: str, headers: dict | None = None) -> str:
    """Faz GET em url e retorna texto limpo (HTML→texto). Limitado a 4000 chars."""
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"[ERRO] {e}"

    text = _html_to_text(raw)
    if len(text) > HTTP_MAX_CHARS:
        text = text[:HTTP_MAX_CHARS] + f"\n... [truncado — {len(text)} chars total]"
    return text
