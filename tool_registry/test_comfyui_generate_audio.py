from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comfyui_generate_audio import AUDIO_TOOL_SERVER_URL, comfyui_generate_audio


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.text = text
    return resp


def test_raises_on_empty_text():
    with pytest.raises(ValueError):
        comfyui_generate_audio("")


def test_raises_on_whitespace_text():
    with pytest.raises(ValueError):
        comfyui_generate_audio("   ")


def test_posts_text_and_default_voice_profile():
    with patch("comfyui_generate_audio.requests.post") as mock_post:
        mock_post.return_value = _mock_response('<audio src="D:/ComfyUI/output/audio.wav">')

        result = comfyui_generate_audio("olá mundo")

    mock_post.assert_called_once_with(
        AUDIO_TOOL_SERVER_URL,
        json={"text": "olá mundo", "voice_profile": "raposa"},
        timeout=120,
    )
    assert result == '<audio src="D:/ComfyUI/output/audio.wav">'


def test_uses_given_voice_profile():
    with patch("comfyui_generate_audio.requests.post") as mock_post:
        mock_post.return_value = _mock_response("ok")

        comfyui_generate_audio("teste", voice_profile="tartaruga")

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["voice_profile"] == "tartaruga"
