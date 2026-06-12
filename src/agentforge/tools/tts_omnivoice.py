from __future__ import annotations

import os
from pathlib import Path

import requests


_OMNIVOICE_URL = os.environ.get("OMNIVOICE_URL", "http://localhost:8880")
_CONRADO_SAMPLE = "conrado"
_CLAUDIO_INSTRUCT = "male, young adult, portuguese accent"


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def tts_omnivoice(text: str, speaker: str, output_path: str) -> str:
    """Synthesizes speech via OmniVoice API and saves to output_path.

    Args:
        text: Text to synthesize (already normalized for TTS).
        speaker: 'conrado' (voice clone) or 'claudio' (instruct mode).
        output_path: Relative path under AGENT_WORKDIR, e.g. 'output/audio/conrado_1.wav'.

    Returns:
        Absolute path of saved file, or error message starting with [ERROR].
    """
    if not text or not text.strip():
        return "[ERROR] 'text' is required."
    if speaker not in ("conrado", "claudio"):
        return "[ERROR] 'speaker' must be 'conrado' or 'claudio'."
    if not output_path or not output_path.strip():
        return "[ERROR] 'output_path' is required."

    dest = Path(output_path)
    if not dest.is_absolute():
        dest = (_workdir() / output_path).resolve()

    dest.parent.mkdir(parents=True, exist_ok=True)

    payload: dict = {
        "text": text,
        "language_id": "pt",
        "output_format": "wav",
    }
    if speaker == "conrado":
        payload["sample"] = _CONRADO_SAMPLE
    else:
        payload["instruct"] = _CLAUDIO_INSTRUCT

    try:
        resp = requests.post(f"{_OMNIVOICE_URL}/tts", json=payload, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"[ERROR] OmniVoice API call failed: {exc}"

    dest.write_bytes(resp.content)
    return str(dest)
