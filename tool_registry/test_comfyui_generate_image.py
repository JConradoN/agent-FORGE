from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from comfyui_generate_image import IMAGE_TOOL_SERVER_URL, comfyui_generate_image


def _mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.text = text
    return resp


def test_raises_on_empty_prompt():
    with pytest.raises(ValueError):
        comfyui_generate_image("")


def test_raises_on_whitespace_prompt():
    with pytest.raises(ValueError):
        comfyui_generate_image("   ")


def test_posts_prompt_and_defaults():
    with patch("comfyui_generate_image.requests.post") as mock_post:
        mock_post.return_value = _mock_response("![gerado](D:/ComfyUI/output/img.png)")

        result = comfyui_generate_image("uma raposa no deserto")

    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == IMAGE_TOOL_SERVER_URL
    assert kwargs["json"] == {
        "prompt": "uma raposa no deserto",
        "engine": "sdxl",
        "full_body": False,
    }
    assert result == "![gerado](D:/ComfyUI/output/img.png)"


def test_includes_face_image_path_when_given():
    with patch("comfyui_generate_image.requests.post") as mock_post:
        mock_post.return_value = _mock_response("![gerado](D:/ComfyUI/output/img.png)")

        comfyui_generate_image("uma sereia", face_image_path="D:/foto.jpg")

    _, kwargs = mock_post.call_args
    assert kwargs["json"]["face_image_path"] == "D:/foto.jpg"


def test_omits_face_image_path_when_not_given():
    with patch("comfyui_generate_image.requests.post") as mock_post:
        mock_post.return_value = _mock_response("ok")

        comfyui_generate_image("uma raposa")

    _, kwargs = mock_post.call_args
    assert "face_image_path" not in kwargs["json"]
