"""HeyGen credit wallet — tracks spend per video and projects monthly usage.

Wallet file: ~/.agentforge/heygen_wallet.json

Each entry is written in two phases:
  Phase 1 (at video creation): records credits_before, video_id, title, test_mode.
  Phase 2 (at video completion): records credits_after and calculates credits_spent.

Call heygen_wallet_report() at any time for a summary with average and projection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

logger = logging.getLogger(__name__)

_WALLET_PATH = Path.home() / ".agentforge" / "heygen_wallet.json"


# ---------------------------------------------------------------------------
# Internal persistence
# ---------------------------------------------------------------------------


def _load() -> dict:
    if not _WALLET_PATH.exists():
        return {"entries": []}
    try:
        return json.loads(_WALLET_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": []}


def _save(data: dict) -> None:
    _WALLET_PATH.parent.mkdir(parents=True, exist_ok=True)
    _WALLET_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 1: record video submission
# ---------------------------------------------------------------------------


def wallet_record_creation(video_id: str, title: str, credits_before: int, test_mode: bool) -> None:
    """Called immediately after heygen_video_creator succeeds."""
    data = _load()
    entry = {
        "ts_created": datetime.now(timezone.utc).isoformat(),
        "ts_completed": None,
        "video_id": video_id,
        "title": title,
        "test_mode": test_mode,
        "credits_before": credits_before,
        "credits_after": None,
        "credits_spent": None,
        "status": "pending",
    }
    data["entries"].append(entry)
    _save(data)
    logger.info("wallet: recorded creation video_id=%s credits_before=%d", video_id, credits_before)


# ---------------------------------------------------------------------------
# Phase 2: record video completion
# ---------------------------------------------------------------------------


def wallet_record_completion(video_id: str, credits_after: int) -> int | None:
    """Called when heygen_get_video returns status=completed. Returns credits_spent."""
    data = _load()
    for entry in data["entries"]:
        if entry["video_id"] == video_id and entry["status"] == "pending":
            entry["ts_completed"] = datetime.now(timezone.utc).isoformat()
            entry["credits_after"] = credits_after
            if entry["credits_before"] is not None:
                spent = entry["credits_before"] - credits_after
                entry["credits_spent"] = spent if spent >= 0 else 0
            else:
                entry["credits_spent"] = None
            entry["status"] = "completed"
            _save(data)
            logger.info(
                "wallet: completed video_id=%s spent=%s credits",
                video_id, entry["credits_spent"],
            )
            return entry["credits_spent"]
    return None


# ---------------------------------------------------------------------------
# Report tool
# ---------------------------------------------------------------------------


def heygen_wallet_report() -> str:
    """Shows HeyGen credit usage: cost per video, average, and monthly projection.

    Returns:
        Human-readable report string.
    """
    from agentforge.tools.heygen_mcp import heygen_credits
    import json as _json

    data = _load()
    entries = data.get("entries", [])

    # Fetch current balance
    try:
        user_data = _json.loads(heygen_credits())
        remaining = (
            user_data.get("subscription", {})
            .get("credits", {})
            .get("premium_credits", {})
            .get("remaining")
        )
        resets_at = (
            user_data.get("subscription", {})
            .get("credits", {})
            .get("premium_credits", {})
            .get("resets_at")
        )
    except Exception:
        remaining = None
        resets_at = None

    # Separate real (non-test) completed entries with known spend
    real_completed = [
        e for e in entries
        if e.get("status") == "completed"
        and not e.get("test_mode")
        and e.get("credits_spent") is not None
    ]
    test_completed = [
        e for e in entries
        if e.get("status") == "completed" and e.get("test_mode")
    ]
    pending = [e for e in entries if e.get("status") == "pending"]

    total_real_videos = len(real_completed)
    total_spent = sum(e["credits_spent"] for e in real_completed)
    avg_cost = round(mean(e["credits_spent"] for e in real_completed), 2) if real_completed else None

    lines = ["=== HeyGen Credit Wallet ===", ""]

    if remaining is not None:
        lines.append(f"Saldo atual:       {remaining} créditos")
        if resets_at:
            lines.append(f"Renova em:         {resets_at[:10]}")
    lines.append("")

    lines.append(f"Vídeos reais:      {total_real_videos} concluídos")
    lines.append(f"Créditos gastos:   {total_spent} total")

    if avg_cost is not None:
        lines.append(f"Custo médio:       {avg_cost} créditos/vídeo")
        if remaining is not None:
            estimated_videos = int(remaining / avg_cost) if avg_cost > 0 else "∞"
            lines.append(f"Vídeos restantes:  ~{estimated_videos} (com saldo atual)")

        # Monthly projection: estimate videos/month if we have timestamps
        if len(real_completed) >= 2:
            try:
                dates = [
                    datetime.fromisoformat(e["ts_completed"])
                    for e in real_completed
                    if e.get("ts_completed")
                ]
                if len(dates) >= 2:
                    span_days = (max(dates) - min(dates)).total_seconds() / 86400
                    if span_days > 0:
                        rate_per_day = total_real_videos / span_days
                        videos_per_month = round(rate_per_day * 30, 1)
                        credits_per_month = round(rate_per_day * 30 * avg_cost, 1)
                        lines.append("")
                        lines.append(f"Ritmo atual:       {videos_per_month} vídeos/mês estimados")
                        lines.append(f"Custo projetado:   {credits_per_month} créditos/mês")
            except Exception:
                pass

    lines.append("")
    lines.append(f"Teste (sem custo): {len(test_completed)} vídeos")
    lines.append(f"Pendentes:         {len(pending)} vídeos")

    if real_completed:
        lines.append("")
        lines.append("--- Últimos 5 vídeos reais ---")
        for e in real_completed[-5:]:
            ts = (e.get("ts_completed") or e.get("ts_created") or "")[:16]
            spent = e.get("credits_spent", "?")
            title = (e.get("title") or e.get("video_id"))[:50]
            lines.append(f"  {ts}  {spent:>3} cr  {title}")

    return "\n".join(lines)
