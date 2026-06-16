"""AgentForge tools for the HeyGen MCP server.

HeyGen MCP endpoint: https://mcp.heygen.com/mcp/v1/ (OAuth 2.0, no API key needed).
Tokens are persisted to ~/.agentforge/mcp_tokens/heygen.json.

Available tools:
  heygen_upload_audio        — upload a local WAV/MP3 to HeyGen assets, returns asset_id
  heygen_upload_image        — upload a local PNG/JPG to HeyGen assets, returns asset_id
  heygen_create_photo_avatar — upload image + create HeyGen photo avatar, returns group_id + look_id
  heygen_poll_avatar_ready   — poll avatar training until ready (up to timeout_s), returns look_id
  heygen_video_creator       — create a video from an avatar + local audio path or text script
  heygen_list_avatars        — list available avatar groups
  heygen_get_video           — poll video status/URL by video_id
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


def _sandbox_active() -> bool:
    """True when AGENTFORGE_HEYGEN_SANDBOX is set to a truthy value.

    Code-level kill switch for paid HeyGen calls — independent of any agent's
    tools.yaml or guardrails, so a misconfigured agent (or a must_compliance
    correction cycle picking the wrong tool) cannot incur a real charge while
    this is set. Removing a tool from tools.yaml stops the model from calling it
    on purpose; this stops the *function* from ever billing, even if called.
    """
    return os.environ.get("AGENTFORGE_HEYGEN_SANDBOX", "").lower() in ("1", "true", "yes")


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


def heygen_upload_image(image_path: str) -> str:
    """Uploads a local PNG/JPG image to HeyGen assets.

    Args:
        image_path: Local path to PNG or JPG file (absolute or relative to AGENT_WORKDIR).

    Returns:
        HeyGen asset_id string, or [ERROR] on failure.
    """
    path = Path(image_path)
    if not path.is_absolute():
        path = (_workdir() / image_path).resolve()

    if not path.exists():
        return f"[ERROR] Image file not found: {image_path}"

    img_bytes = path.read_bytes()
    size = len(img_bytes)
    suffix = path.suffix.lower()
    content_type = "image/png" if suffix == ".png" else "image/jpeg"

    create_result = _mcp("create_asset_upload", {
        "filename": path.name,
        "contentType": content_type,
        "sizeBytes": size,
    })
    if isinstance(create_result, str) and create_result.startswith("[ERROR]"):
        return create_result

    try:
        data = json.loads(create_result) if isinstance(create_result, str) else create_result
    except json.JSONDecodeError:
        return f"[ERROR] create_asset_upload unexpected response: {create_result[:200]}"

    upload_url = data.get("uploadUrl") or data.get("upload_url")
    asset_id = data.get("assetId") or data.get("asset_id") or data.get("id")

    if not upload_url:
        return f"[ERROR] No uploadUrl in response: {data}"
    if not asset_id:
        return f"[ERROR] No assetId in response: {data}"

    try:
        resp = requests.put(
            upload_url,
            data=img_bytes,
            headers={
                "Content-Type": content_type,
                "Content-Length": str(size),
                "x-amz-server-side-encryption": "AES256",
            },
            timeout=120,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"[ERROR] Image upload PUT failed: {exc}"

    complete_result = _mcp("complete_asset_upload", {"assetId": asset_id})
    if isinstance(complete_result, str) and complete_result.startswith("[ERROR]"):
        return complete_result

    logger.info("heygen_upload_image: uploaded %s → asset_id=%s", path.name, asset_id)
    return asset_id


def heygen_create_photo_avatar(image_path: str, avatar_name: str) -> str:
    """Uploads an image and creates a HeyGen photo avatar. Training is async.

    Args:
        image_path: Local path to PNG/JPG (absolute or relative to AGENT_WORKDIR).
        avatar_name: Display name for the avatar in HeyGen dashboard.

    Returns:
        JSON string with group_id and look_id, or [ERROR] on failure.
    """
    asset_id = heygen_upload_image(image_path)
    if asset_id.startswith("[ERROR]"):
        return asset_id

    result = _mcp("create_photo_avatar", {
        "name": avatar_name,
        "file": {"type": "asset_id", "asset_id": asset_id},
    })

    if isinstance(result, str) and result.startswith("[ERROR]"):
        return result

    try:
        data = json.loads(result) if isinstance(result, str) else result
    except json.JSONDecodeError:
        return f"[ERROR] create_photo_avatar unexpected response: {result[:200]}"

    # Response structure: {"avatar_item": {"id": look_id, "group_id": ...}, "avatar_group": {"id": group_id}}
    avatar_item = data.get("avatar_item") or {}
    avatar_group = data.get("avatar_group") or {}

    group_id = (
        avatar_group.get("id")
        or avatar_item.get("group_id")
        or data.get("group_id")
        or data.get("id")
        or ""
    )
    look_id = (
        avatar_item.get("id")
        or data.get("avatar_id")
        or data.get("id")
        or ""
    )

    logger.info("heygen_create_photo_avatar: group=%s look=%s status=%s",
                group_id, look_id, avatar_item.get("status", "unknown"))
    return json.dumps({"group_id": group_id, "look_id": look_id, "status": avatar_item.get("status", "unknown")})


def heygen_poll_avatar_ready(group_id: str, look_id: str = "", timeout_s: int = 600) -> str:
    """Polls HeyGen until a photo avatar finishes training.

    Args:
        group_id: Avatar group ID returned by heygen_create_photo_avatar.
        look_id: Avatar look ID (optional — will be fetched from group if absent).
        timeout_s: Max seconds to wait (default 600 = 10 min).

    Returns:
        Confirmed look_id string when ready, or [ERROR]/[TIMEOUT] on failure.
    """
    import time

    deadline = time.time() + timeout_s

    for attempt in range(200):
        if time.time() > deadline:
            return f"[TIMEOUT] Avatar not ready after {timeout_s}s"

        if group_id:
            resp = _mcp("get_avatar_group", {"groupId": group_id})
            try:
                data = json.loads(resp) if isinstance(resp, str) else resp
                looks = data.get("looks", []) if isinstance(data, dict) else []
                if looks:
                    first = looks[0]
                    look_id = first.get("avatar_look_id") or first.get("id") or look_id
                    status = first.get("status", "unknown")
                    logger.info("avatar poll [%d] group=%s status=%s look=%s", attempt, group_id, status, look_id)
                    if status in ("completed", "ready", "active"):
                        return look_id
                    if status in ("failed", "error"):
                        return f"[ERROR] Avatar training failed: {first}"
            except Exception as exc:
                logger.warning("avatar poll parse error: %s", exc)

        if look_id:
            resp = _mcp("get_avatar_look", {"lookId": look_id})
            try:
                data = json.loads(resp) if isinstance(resp, str) else resp
                status = data.get("status") or data.get("processing_status") if isinstance(data, dict) else "unknown"
                logger.info("avatar poll [%d] look=%s status=%s", attempt, look_id, status)
                if status in ("completed", "ready", "active"):
                    return look_id
                if status in ("failed", "error"):
                    return f"[ERROR] Avatar training failed: {data}"
            except Exception as exc:
                logger.warning("avatar look poll parse error: %s", exc)

        time.sleep(15)

    return f"[TIMEOUT] Avatar not ready after {timeout_s}s"


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
    width: int = 720,
    height: int = 1280,
) -> str:
    """Creates a HeyGen video with the specified avatar.

    Provide either audio_path (local WAV — will be uploaded automatically) or
    script (text for HeyGen built-in TTS).

    Args:
        avatar_id: HeyGen avatar look ID.
        title: Video title shown in HeyGen dashboard.
        audio_path: Local path to WAV/MP3 (relative to AGENT_WORKDIR or absolute). Uploaded automatically.
        script: Text script for HeyGen built-in TTS. Used when audio_path is None.
        voice_id: HeyGen voice ID for TTS. Required when using script without a default avatar voice.
        test_mode: If True, renders in test mode (watermark, no credit cost).
        width: Output video width in pixels (e.g. 720 for 9:16 portrait). Paired with height.
        height: Output video height in pixels (e.g. 1280 for 9:16 portrait). Paired with width.

    Returns:
        JSON string with video_id and status, or [ERROR] on failure.
    """
    if not avatar_id:
        return "[ERROR] 'avatar_id' is required."
    if not audio_path and not script:
        return "[ERROR] Either 'audio_path' or 'script' must be provided."

    if _sandbox_active() and not test_mode:
        logger.warning(
            "heygen_video_creator: AGENTFORGE_HEYGEN_SANDBOX active — forcing test_mode=True "
            "(caller passed test_mode=False)"
        )
        test_mode = True

    args: dict = {"avatarId": avatar_id}
    if title:
        args["title"] = title
    if test_mode:
        args["test"] = True
    if width and height:
        args["dimension"] = {"width": width, "height": height}

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

    # Snapshot credits before creation for wallet tracking.
    # Always fetch even in test_mode — test videos are NOT free (they consume credits).
    credits_before: int | None = None
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


def heygen_video_agent(
    prompt: str,
    mode: str = "generate",
    orientation: str = "portrait",
    avatar_id: str | None = None,
    style_id: str | None = None,
) -> str:
    """Creates a full HeyGen video from a prompt using the Video Agent pipeline.

    The Video Agent handles scripting, scene composition, avatar selection, b-roll
    generation, and rendering automatically. Much cheaper than create_video_from_avatar
    for complete videos — draws on web plan credits, not per-second billing.

    Use mode="generate" for automation (fire-and-forget). Returns a session_id immediately;
    poll heygen_get_agent_session until video_id is set, then poll heygen_get_video.

    Args:
        prompt: Full video description — include script, tone, b-roll cues, and style.
                Example: "Diálogo tech entre Conrado e Cláudio cyborg sobre agentes IA.
                Intercalar com telas de terminal e infográficos. Estilo anime, portrait."
        mode: "generate" (automated, no review) or "chat" (interactive, asks for decisions).
        orientation: "portrait" for 9:16 (TikTok/Reels), "landscape" for 16:9.
        avatar_id: Optional look_id to use as main avatar. If omitted, HeyGen auto-selects.
        style_id: Optional style template ID from list_video_agent_styles.

    Returns:
        JSON string with session_id and session_url, or [ERROR] on failure.
    """
    if not prompt:
        return "[ERROR] 'prompt' is required."

    if _sandbox_active():
        logger.warning("heygen_video_agent: blocked — AGENTFORGE_HEYGEN_SANDBOX active, no free mode exists for this tool")
        return (
            "[ERROR] heygen_video_agent is disabled while AGENTFORGE_HEYGEN_SANDBOX is active. "
            "This tool has no free/test mode and always bills real credits. "
            "Use heygen_video_creator with test_mode=True instead."
        )

    args: dict = {"prompt": prompt, "mode": mode}
    if orientation == "portrait":
        args["orientation"] = "portrait"
    if avatar_id:
        args["avatar_id"] = avatar_id
    if style_id:
        args["style_id"] = style_id

    # Snapshot credits before
    credits_before: int | None = None
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

    result = _mcp("create_video_agent", args)
    logger.info("heygen_video_agent: mode=%s orientation=%s avatar=%s", mode, orientation, avatar_id)

    # Register in wallet using session_id as key
    if not isinstance(result, str) or not result.startswith("[ERROR]"):
        try:
            data = json.loads(result) if isinstance(result, str) else result
            session_id = data.get("session_id") or data.get("id", "")
            if session_id and credits_before is not None:
                from agentforge.tools.heygen_wallet import wallet_record_creation
                wallet_record_creation(session_id, prompt[:60], credits_before, False)
        except Exception:
            pass

    return result if isinstance(result, str) else json.dumps(result)


def heygen_get_agent_session(session_id: str) -> str:
    """Polls a Video Agent session for status and video_id.

    Call in a loop after heygen_video_agent until status is "completed" and
    video_id is set. Then call heygen_get_video(video_id) to get the final URL.

    Args:
        session_id: Session ID returned by heygen_video_agent.

    Returns:
        JSON string with status, video_id (when ready), and recent messages.
    """
    if not session_id:
        return "[ERROR] 'session_id' is required."
    return _mcp("get_video_agent_session", {"session_id": session_id})


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
