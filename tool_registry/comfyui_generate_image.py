"""Gera uma imagem via ComfyUI no fox-wks (image_tool_server, porta 8090).

Chama o serviço já existente (JuggernautXL/SDXL por padrão, ou Flux Schnell)
rodando na estação de mídia — não sobe nem gerencia o ComfyUI, só consome a
API HTTP já homologada.
"""

from __future__ import annotations

import requests

IMAGE_TOOL_SERVER_URL = "http://192.168.88.202:8090/generate_image"
TIMEOUT_S = 120


def comfyui_generate_image(
    prompt: str,
    engine: str = "sdxl",
    full_body: bool = False,
    face_image_path: str | None = None,
    server_url: str = IMAGE_TOOL_SERVER_URL,
) -> str:
    """Gera uma imagem local via ComfyUI (fox-wks) a partir de um prompt.

    Args:
        prompt: Descrição da imagem a gerar.
        engine: "sdxl" (JuggernautXL, padrão) ou "flux" (Flux Schnell).
        full_body: Se True, pede enquadramento de corpo inteiro.
        face_image_path: Caminho Windows ou URL da referência de rosto para
            face swap via ReActor — opcional, omitir para gerar sem swap.
        server_url: URL do image_tool_server (default: instância do fox-wks).

    Returns:
        Texto retornado pelo servidor — tag markdown de imagem apontando pro
        arquivo real salvo no ComfyUI.

    Raises:
        ValueError: Se prompt for vazio.
    """
    if not prompt or not prompt.strip():
        raise ValueError("prompt cannot be empty")

    body: dict = {"prompt": prompt, "engine": engine, "full_body": full_body}
    if face_image_path:
        body["face_image_path"] = face_image_path

    resp = requests.post(server_url, json=body, timeout=TIMEOUT_S)
    resp.raise_for_status()
    return resp.text
