"""AgentForge tools for the HeyGen MCP server.

HeyGen MCP endpoint: https://mcp.heygen.com/mcp/v1/ (OAuth 2.0, no API key needed).
Tokens are persisted to ~/.agentforge/mcp_tokens/heygen.json.

Available tools:
  heygen_upload_audio   — upload a local WAV/MP3 to HeyGen assets, returns asset_id
  heygen_video_creator  — create a video from an avatar + local audio path or text script
  heygen_list_avatars   — list available avatar groups
  heygen_get_video      — poll video status/URL by video_id
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

_HEYGEN_MCP_URL = "https://mcp.heygen.com/mcp/v1/"
_TOKEN_PATH = Path.home() / ".agentforge" / "mcp_tokens" / "heygen.json"


def _workdir() -> Path:
    return Path(os.environ.get("AGENT_WORKDIR", ".")).resolve()


def _mcp(tool_name: str, args: dict) -> str:
    from agentforge.channels.mcp_client import call_mcp_tool
    try:
        result = call_mcp_tool(_HEYGEN_MCP_URL, tool_name, args, _TOKEN_PATH)
        if result is None:
            return "[ERROR] MCP tool returned no content."
        return str(result)
    except Exception as exc:
        return f"[ERROR] HeyGen MCP call failed: {exc}"


def heygen_upload_audio(audio_path: str) -> str:
    """Uploads a local audio file to HeyGen assets.

    Resolves path relative to AGENT_WORKDIR. Uses a two-step flow:
    create_asset_upload → PUT to pre-signed URL → complete_asset_upload.

    Args:
        audio_path: Local path to WAV or MP3 file (relative to AGENT_WORKDIR or absolute).

    Returns:
        HeyGen asset_id string, or [ERROR] on failure.
    """
    path = Path(audio_path)
    if not path.is_absolute():
        path = (_workdir() / audio_path).resolve()

    if not path.exists():
        return f"[ERROR] Audio file not found: {audio_path}"

    audio_bytes = path.read_bytes()
    size = len(audio_bytes)
    sha256 = hashlib.sha256(audio_bytes).hexdigest()
    content_type = "audio/wav" if path.suffix.lower() == ".wav" else "audio/mpeg"

    # Step 1: request pre-signed upload URL (no checksum — keeps signed headers minimal)
    create_result = _mcp("create_asset_upload", {
        "filename": path.name,
        "contentType": content_type,
        "sizeBytes": size,
    })
    if create_result.startswith("[ERROR]"):
        return create_result

    try:
        data = json.loads(create_result)
    except json.JSONDecodeError:
        return f"[ERROR] create_asset_upload returned unexpected response: {create_result[:200]}"

    upload_url = data.get("uploadUrl") or data.get("upload_url")
    asset_id = data.get("assetId") or data.get("asset_id") or data.get("id")

    if not upload_url:
        return f"[ERROR] No uploadUrl in create_asset_upload response: {create_result[:200]}"
    if not asset_id:
        return f"[ERROR] No assetId in create_asset_upload response: {create_result[:200]}"

    # Step 2: PUT bytes directly to the pre-signed S3 URL
    # x-amz-server-side-encryption is in the signed headers — required.
    try:
        put_headers = {
            "Content-Type": content_type,
            "Content-Length": str(size),
            "x-amz-server-side-encryption": "AES256",
        }
        resp = requests.put(upload_url, data=audio_bytes, headers=put_headers, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"[ERROR] Upload PUT failed: {exc}"

    # Step 3: confirm upload
    complete_result = _mcp("complete_asset_upload", {"assetId": asset_id})
    if complete_result.startswith("[ERROR]"):
        return complete_result

    logger.info("heygen_upload_audio: uploaded %s → asset_id=%s", path.name, asset_id)
    return asset_id


def heygen_video_creator(
    avatar_id: str,
    title: str,
    audio_path: str | None = None,
    script: str | None = None,
    voice_id: str | None = None,
    test_mode: bool = False,
) -> str:
    """Creates a HeyGen video with the Conrado Virtual avatar.

    Provide either audio_path (local WAV — will be uploaded automatically) or
    script (text for HeyGen built-in TTS).

    Args:
        avatar_id: HeyGen avatar look ID (use '58e972a6a66f4f9eae1376fe28fd2291' for Conrado Virtual).
        title: Video title shown in HeyGen dashboard.
        audio_path: Local path to WAV/MP3 (relative to AGENT_WORKDIR or absolute). Uploaded automatically.
        script: Text script for HeyGen built-in TTS. Used when audio_path is None.
        voice_id: HeyGen voice ID for TTS. Required when using script without a default avatar voice.
        test_mode: If True, renders in test mode (watermark, no credit cost).

    Returns:
        JSON string with video_id and status, or [ERROR] on failure.
    """
    if not avatar_id:
        return "[ERROR] 'avatar_id' is required."
    if not audio_path and not script:
        return "[ERROR] Either 'audio_path' or 'script' must be provided."

    args: dict = {"avatarId": avatar_id}
    if title:
        args["title"] = title
    if test_mode:
        args["test"] = True

    if audio_path:
        asset_id = heygen_upload_audio(audio_path)
        if asset_id.startswith("[ERROR]"):
            return asset_id
        args["audioAssetId"] = asset_id
        logger.info("heygen_video_creator: avatar=%s audio_asset=%s", avatar_id, asset_id)
    else:
        args["script"] = script
        if voice_id:
            args["voiceId"] = voice_id
        logger.info("heygen_video_creator: avatar=%s mode=tts", avatar_id)

    # Snapshot credits before creation for wallet tracking
    credits_before: int | None = None
    if not test_mode:
        try:
            user_data = json.loads(heygen_credits())
            credits_before = (
                user_data.get("subscription", {})
                .get("credits", {})
                .get("premium_credits", {})
                .get("remaining")
            )
        except Exception:
            pass

    result = _mcp("create_video_from_avatar", args)

    # Register creation in wallet
    if not result.startswith("[ERROR]"):
        try:
            video_id = json.loads(result).get("video_id")
            if video_id:
                from agentforge.tools.heygen_wallet import wallet_record_creation
                wallet_record_creation(video_id, title or video_id, credits_before or 0, test_mode)
        except Exception:
            pass

    return result


def heygen_credits() -> str:
    """Returns remaining HeyGen credits and billing details for the authenticated account.

    Returns:
        JSON string with credit balance and plan info, or [ERROR] on failure.
    """
    return _mcp("get_current_user", {})


def heygen_list_avatars(include_public: bool = True) -> str:
    """Lists available HeyGen avatar groups.

    Returns:
        JSON string with avatar groups, or [ERROR] on failure.
    """
    return _mcp("list_avatar_groups", {"include_public": include_public})


def heygen_get_video(video_id: str) -> str:
    """Gets video status and download URL by video_id.

    Args:
        video_id: HeyGen video ID returned by heygen_video_creator.

    Returns:
        JSON string with status and video_url when complete, or [ERROR] on failure.
    """
    if not video_id:
        return "[ERROR] 'video_id' is required."
    result = _mcp("get_video", {"video_id": video_id})

    # When video completes, record final credit balance in wallet
    if not result.startswith("[ERROR]"):
        try:
            data = json.loads(result)
            if data.get("status") == "completed":
                user_data = json.loads(heygen_credits())
                credits_after = (
                    user_data.get("subscription", {})
                    .get("credits", {})
                    .get("premium_credits", {})
                    .get("remaining")
                )
                if credits_after is not None:
                    from agentforge.tools.heygen_wallet import wallet_record_completion
                    spent = wallet_record_completion(video_id, credits_after)
                    if spent is not None:
                        logger.info("wallet: video %s spent %d credits", video_id, spent)
        except Exception:
            pass

    return result
