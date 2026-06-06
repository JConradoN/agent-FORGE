from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

_HISTORY_FILE = "history.json"
_SUMMARY_ROLE = "system"
_SUMMARY_PREFIX = "Resumo da conversa anterior:"

# Hook for custom (e.g. LLM-based) summarizers.
# Receives (overflow_turns, existing_summary_content_or_None).
# Must return the full new content string for the summary message,
# including the "Resumo da conversa anterior:" prefix line.
SummarizerFn = Callable[[list[dict[str, str]], str | None], str]


def _is_summary_message(msg: dict[str, str]) -> bool:
    return msg.get("role") == _SUMMARY_ROLE and msg.get("content", "").startswith(_SUMMARY_PREFIX)


def _build_summary_content(
    existing_content: str | None,
    overflow_turns: list[dict[str, str]],
) -> str:
    lines: list[str] = [_SUMMARY_PREFIX]
    if existing_content:
        lines.extend(line for line in existing_content.split("\n")[1:] if line.strip())
    for msg in overflow_turns:
        label = "User" if msg["role"] == "user" else "Assistant"
        text = msg["content"].replace("\n", " ").strip()
        lines.append(f"- {label}: {text}")
    return "\n".join(lines)


def apply_limit(history: list[dict[str, str]], max_turns: int) -> list[dict[str, str]]:
    """Truncate oldest turns, keeping only the last max_turns.  0 = unlimited."""
    if max_turns <= 0 or len(history) == 0:
        return history
    max_messages = max_turns * 2
    if len(history) <= max_messages:
        return history
    return history[-max_messages:]


def apply_limit_summarize(
    history: list[dict[str, str]],
    max_turns: int,
    summarizer: SummarizerFn | None = None,
) -> list[dict[str, str]]:
    """Compress overflow turns into a summary message instead of discarding them.

    The returned list is: [summary_message] + [last max_turns verbatim turns].
    If a summary message already exists it is updated, not duplicated.
    max_turns=0 means unlimited — history is returned unchanged.
    """
    if max_turns <= 0 or not history:
        return history

    # Separate an existing summary from the real conversation turns.
    if _is_summary_message(history[0]):
        existing_summary: dict[str, str] | None = history[0]
        real_turns = list(history[1:])
    else:
        existing_summary = None
        real_turns = list(history)

    max_messages = max_turns * 2
    if len(real_turns) <= max_messages:
        return history  # still within window, nothing to compress

    overflow = real_turns[:-max_messages]
    keep = real_turns[-max_messages:]
    existing_content = existing_summary["content"] if existing_summary else None

    new_content = (
        summarizer(overflow, existing_content)
        if summarizer is not None
        else _build_summary_content(existing_content, overflow)
    )

    return [{"role": _SUMMARY_ROLE, "content": new_content}] + keep


def apply_window(
    history: list[dict[str, str]],
    max_turns: int,
    policy: str = "truncate",
    summarizer: SummarizerFn | None = None,
) -> list[dict[str, str]]:
    """Apply the configured limit policy to history."""
    if policy == "summarize":
        return apply_limit_summarize(history, max_turns, summarizer)
    return apply_limit(history, max_turns)


def load_history(
    root_dir: Path,
    memory_type: str,
    enabled: bool,
    max_turns: int = 0,
    policy: str = "truncate",
) -> list[dict[str, str]]:
    if not enabled or memory_type == "none":
        return []
    path = root_dir / _HISTORY_FILE
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return apply_window(data, max_turns, policy)
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_history(root_dir: Path, history: list[dict[str, str]]) -> None:
    path = root_dir / _HISTORY_FILE
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_history(root_dir: Path) -> None:
    path = root_dir / _HISTORY_FILE
    if path.exists():
        path.unlink()

        path.unlink()
