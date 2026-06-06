from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


def _load_credentials() -> tuple[str, str]:
    cfg = Path.home() / ".aurelia/config/app.json"
    try:
        d = json.loads(cfg.read_text())
        token = d.get("telegram_bot_token", "")
        chat_id = str(d.get("telegram_allowed_user_ids", [""])[0])
        return token, chat_id
    except Exception:
        return "", ""


def send_claudio(message: str) -> str:
    """Envia message via bot Telegram do Claudio."""
    if not message or not message.strip():
        return "[ERRO] 'message' é obrigatório."

    token, chat_id = _load_credentials()
    if not token or not chat_id or chat_id == "":
        return "[ERRO] Credenciais Telegram não disponíveis (~/.aurelia/config/app.json)."

    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
            msg_id = resp.get("result", {}).get("message_id", "?")
            return f"Mensagem enviada. message_id={msg_id}"
    except Exception as e:
        return f"[ERRO] {e}"
