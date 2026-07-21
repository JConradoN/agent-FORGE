"""Gera áudio TTS via OmniVoice/ComfyUI no fox-wks (system_tool_server, porta 8091).

Chama o serviço já existente — não sobe nem gerencia o ComfyUI, só consome a
API HTTP já homologada.
"""

from __future__ import annotations

import requests

AUDIO_TOOL_SERVER_URL = "http://192.168.88.202:8091/generate_audio"
TIMEOUT_S = 120


def comfyui_generate_audio(
    text: str,
    voice_profile: str = "raposa",
    server_url: str = AUDIO_TOOL_SERVER_URL,
) -> str:
    """Gera síntese de voz em português via OmniVoice local (fox-wks).

    Args:
        text: Texto a ser sintetizado em áudio.
        voice_profile: "conrado" ou "claudio" (clonagem por referência de voz
            homologada), ou "raposa" (masculino jovem, padrão) / "tartaruga"
            (feminino idoso/lento) — estilo sintético sem clonagem.
        server_url: URL do system_tool_server (default: instância do fox-wks).

    Returns:
        Texto retornado pelo servidor — tag <audio> apontando pro arquivo
        real salvo no ComfyUI.

    Raises:
        ValueError: Se text for vazio.
    """
    if not text or not text.strip():
        raise ValueError("text cannot be empty")

    resp = requests.post(
        server_url, json={"text": text, "voice_profile": voice_profile}, timeout=TIMEOUT_S
    )
    resp.raise_for_status()
    return resp.text
