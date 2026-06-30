#!/usr/bin/env python3
"""
Fox WKS Image Tool Server — porta 8090
Tool Server compatível com Open WebUI 0.10.x (formato OpenAPI).

Expõe generate_image e save_face_reference para uso direto pelo OWU
sem depender do mecanismo frágil de tool_ids embutido.

Deploy: NSSM ou Task Scheduler
  C:\venv-owu\Scripts\python.exe image_tool_server.py
"""
import os
import json
import time
import random
import shutil
import urllib.request
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

COMFY_URL = os.environ.get("COMFY_URL", "http://localhost:8188")
FACE_REF = os.environ.get("FACE_REF", "C:/ComfyUI_windows_portable/ComfyUI/input/face_swap_ref.jpg")
OWU_API_KEY = os.environ.get("OWU_API_KEY", "sk-foxwks-bd6dc62fd0caca045e5fa615680866d4")
OWU_BASE = os.environ.get("OWU_BASE", "http://localhost:8080")

app = FastAPI(
    title="Fox WKS Image Tools",
    description="Geração de imagens via ComfyUI + JuggernautXL + ReActor Face Swap.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SaveFaceRequest(BaseModel):
    image_source: str


class GenerateImageRequest(BaseModel):
    prompt: str
    face_image_path: Optional[str] = None
    full_body: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _comfy_post(payload: dict, timeout: int = 10) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{COMFY_URL}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _comfy_wait(prompt_id: str, timeout: int = 180) -> Optional[dict]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5) as resp:
                hist = json.loads(resp.read())
            if prompt_id in hist and hist[prompt_id].get("status", {}).get("completed"):
                return hist[prompt_id]["outputs"]
        except Exception:
            pass
        time.sleep(3)
    return None


def _build_sdxl_workflow(prompt: str, w: int, h: int, face_path: Optional[str]) -> dict:
    neg = (
        "adult, teenager, breasts, cleavage, makeup, eyeliner, eyeshadow, "
        "ugly, deformed, blurry, extra limbs, bad anatomy, nsfw, mature, "
        "bad face, watermark, signature, text"
    )
    wf = {
        "1": {"inputs": {"ckpt_name": "JuggernautXL_v9.safetensors"}, "class_type": "CheckpointLoaderSimple"},
        "2": {"inputs": {"text": prompt + ", masterpiece, best quality, highly detailed, sharp focus, photorealistic", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "3": {"inputs": {"text": neg, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "4": {"inputs": {"width": w, "height": h, "batch_size": 1}, "class_type": "EmptyLatentImage"},
        "5": {
            "inputs": {
                "seed": random.randint(1, 10**15),
                "steps": 30,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
            "class_type": "KSampler",
        },
        "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
        "9": {"inputs": {"filename_prefix": "ComfyUI", "images": ["6", 0]}, "class_type": "SaveImage"},
    }

    if face_path and os.path.exists(face_path):
        dest = FACE_REF
        if os.path.normcase(face_path) != os.path.normcase(dest):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy(face_path, dest)
        wf["30"] = {"inputs": {"image": "face_swap_ref.jpg"}, "class_type": "LoadImage"}
        wf["31"] = {
            "inputs": {
                "enabled": True,
                "input_image": ["6", 0],
                "source_image": ["30", 0],
                "swap_model": "inswapper_128.onnx",
                "facedetection": "retinaface_resnet50",
                "face_restore_model": "GFPGANv1.4.pth",
                "face_restore_visibility": 0.85,
                "codeformer_weight": 0.5,
                "detect_gender_input": "no",
                "detect_gender_source": "no",
                "input_faces_index": "0",
                "source_faces_index": "0",
                "console_log_level": 1,
            },
            "class_type": "ReActorFaceSwap",
        }
        wf["9"]["inputs"]["images"] = ["31", 0]

    return wf


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "server": "fox-wks-image-tools"}


@app.post("/save_face_reference", response_class=PlainTextResponse, operation_id="save_face_reference")
def save_face_reference(req: SaveFaceRequest) -> str:
    """
    Salva uma imagem de referência de rosto para uso no face swap.
    Aceita caminho Windows (D:\\foto.jpg) ou URL HTTP do OWU.
    """
    os.makedirs(os.path.dirname(FACE_REF), exist_ok=True)
    try:
        src = req.image_source
        if src.startswith("http://") or src.startswith("https://"):
            opener = urllib.request.Request(src)
            opener.add_header("Authorization", f"Bearer {OWU_API_KEY}")
            with urllib.request.urlopen(opener, timeout=15) as resp:
                with open(FACE_REF, "wb") as f:
                    f.write(resp.read())
        elif os.path.exists(src):
            shutil.copy(src, FACE_REF)
        else:
            raise HTTPException(status_code=400, detail=f"Imagem não encontrada: {src}")
        return f"Referência salva: {FACE_REF}"
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/generate_image", response_class=PlainTextResponse, operation_id="generate_image")
def generate_image(req: GenerateImageRequest) -> str:
    """
    Gera uma imagem usando JuggernautXL (SDXL) via ComfyUI.
    Face swap aplicado automaticamente se face_swap_ref.jpg foi atualizado há menos de 1h.
    """
    face = req.face_image_path

    # Auto-detectar referência recente (< 1h)
    if face is None and os.path.exists(FACE_REF):
        if time.time() - os.path.getmtime(FACE_REF) < 3600:
            face = FACE_REF

    if face:
        face = face.strip().strip("'\"")
        if not any(face.upper().startswith(d) for d in ("C:", "D:", "V:")):
            face = os.path.join("D:\\", face)

    w, h = (768, 1344) if req.full_body else (832, 1216)

    try:
        wf = _build_sdxl_workflow(req.prompt, w, h, face)
        res = _comfy_post({"prompt": wf})
        prompt_id = res["prompt_id"]

        outputs = _comfy_wait(prompt_id)
        if outputs is None:
            raise HTTPException(status_code=504, detail="Timeout na geração ComfyUI.")

        for nid, out in outputs.items():
            for img in out.get("images", []):
                url = (
                    f"http://192.168.88.202:8188/view"
                    f"?filename={img['filename']}&subfolder={img['subfolder']}&type={img['type']}"
                )
                return f"![imagem]({url})"

        raise HTTPException(status_code=500, detail="Nenhuma imagem encontrada nos outputs.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8090, log_level="info")
