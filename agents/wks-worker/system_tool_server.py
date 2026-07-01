#!/usr/bin/env python3
"""
Fox WKS System Tool Server — porta 8091
Tool Server compatível com Open WebUI 0.10.x (formato OpenAPI).

Expõe ferramentas de sistema do fox-wks: saúde, arquivos, PowerShell,
SSH para fox-server e agent-mesh. Roda em fox-wks, consomido pelo OWU
que fica no fox-server.

Deploy: Task Scheduler "SystemToolServer" (ONSTART, user morph)
  C:\open-webui-venv\Scripts\python.exe C:\repos\wks-tools\system_tool_server.py
"""
import os
import json
import platform
import shutil
import subprocess
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

OWU_API_KEY = os.environ.get("OWU_API_KEY", "sk-foxwks-bd6dc62fd0caca045e5fa615680866d4")
COMFY_URL   = os.environ.get("COMFY_URL", "http://localhost:8188")
FOX_SERVER_IP   = os.environ.get("FOX_SERVER_IP", "192.168.88.200")
FOX_SERVER_USER = os.environ.get("FOX_SERVER_USER", "conrado")
SSH_KEY     = os.environ.get("SSH_KEY", "C:/ProgramData/open-webui-ssh/id_rsa")
TURBOQUANT_URL   = os.environ.get("TURBOQUANT_URL", "http://192.168.88.200:8082/v1/chat/completions")
TURBOQUANT_MODEL = os.environ.get("TURBOQUANT_MODEL", "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf")
WORKSPACE = "D:\\"

app = FastAPI(
    title="Fox WKS System Tools",
    description="Ferramentas de sistema do fox-wks: saúde, arquivos, PowerShell, SSH para fox-server.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _check_path(path: str):
    resolved = os.path.normpath(os.path.abspath(path))
    if not resolved.upper().startswith("D:\\"):
        raise HTTPException(status_code=400, detail=f"Acesso negado: workspace é D:\\ (tentativa: {resolved})")
    return resolved


def _ps(cmd: str, timeout: int = 15) -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return (r.stdout.strip() or r.stderr.strip())[:4000]


def _ssh(command: str, timeout: int = 20) -> str:
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            FOX_SERVER_IP,
            username=FOX_SERVER_USER,
            key_filename=SSH_KEY,
            timeout=10,
        )
        _, stdout, stderr = client.exec_command(command, timeout=timeout)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        return (out or err or "(sem output)")[:4000]
    finally:
        client.close()


def _win_os_name() -> str:
    ver = platform.version()
    try:
        build = int(ver.split(".")[2])
        if build >= 22000:
            return f"Windows 11 (build {build})"
    except Exception:
        pass
    return f"Windows {platform.release()} ({ver})"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PathRequest(BaseModel):
    path: str

class WriteRequest(BaseModel):
    path: str
    content: str

class ShellRequest(BaseModel):
    command: str

class AgentMemoryWriteRequest(BaseModel):
    key: str
    value: str

class MemoryLimitRequest(BaseModel):
    limit: int = 10

class AnalyzeImageRequest(BaseModel):
    image_source: str
    question: str = "Descreva detalhadamente o que você vê nesta imagem."

class AudioRequest(BaseModel):
    text: str
    voice_profile: str = "raposa"


# ---------------------------------------------------------------------------
# Saúde
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "server": "fox-wks-system-tools"}


@app.get("/get_system_info", response_class=PlainTextResponse, operation_id="get_system_info")
def get_system_info() -> str:
    """Retorna OS, CPU e RAM do fox-wks."""
    try:
        ram_out = _ps(
            "$os = Get-CimInstance Win32_OperatingSystem; "
            "Write-Output ($os.TotalVisibleMemorySize.ToString() + ' ' + $os.FreePhysicalMemory.ToString())"
        )
        parts = ram_out.split()
        total = int(parts[0]) // 1024 if parts else 0
        free  = int(parts[1]) // 1024 if len(parts) > 1 else 0
        return (
            f"OS: {_win_os_name()}\nMaquina: {platform.node()}\nCPU: {platform.processor()}\n"
            f"RAM: {total - free}/{total} MB usados ({free} MB livres)"
        )
    except Exception as e:
        return f"Erro: {e}"


@app.get("/get_gpu_info", response_class=PlainTextResponse, operation_id="get_gpu_info")
def get_gpu_info() -> str:
    """Retorna temperatura, uso e VRAM da GPU NVIDIA do fox-wks."""
    try:
        r = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            return "nvidia-smi nao disponivel."
        lines = []
        for i, line in enumerate(r.stdout.strip().splitlines()):
            p = [x.strip() for x in line.split(",")]
            if len(p) >= 6:
                lines.append(f"GPU {i}: {p[0]} | {p[1]}C | {p[2]}% | {p[3]}/{p[4]} MB VRAM | {p[5]}W")
        return "\n".join(lines) or "Nenhuma GPU."
    except Exception as e:
        return f"Erro: {e}"


@app.get("/get_full_health", response_class=PlainTextResponse, operation_id="get_full_health")
def get_full_health() -> str:
    """Retorna saúde completa do fox-wks: OS, CPU, RAM, GPU e disco D em uma só chamada."""
    lines = [f"=== fox-wks ({platform.node()}) ==="]
    lines.append(get_system_info())
    lines.append(get_gpu_info())
    disk = _ps("$d=Get-PSDrive D; Write-Output (($d.Used/1GB).ToString('F1')+' GB usados, '+($d.Free/1GB).ToString('F1')+' GB livres')")
    lines.append(f"Disco D: {disk}")
    return "\n".join(lines)


@app.get("/fox_server_health", response_class=PlainTextResponse, operation_id="fox_server_health")
def fox_server_health() -> str:
    """Retorna saúde do fox-server: CPU, RAM, disco, GPU e containers Docker."""
    try:
        cpu    = _ssh("top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4\"%\"}'")
        mem    = _ssh("free -h | awk '/^Mem:/{print $3\"/\"$2}'")
        disk   = _ssh("df -h / /mnt/vault 2>/dev/null | awk 'NR>1{print $6\": \"$3\"/\"$2\" (\"$5\")\"}'")
        gpu    = _ssh("docker exec ollama nvidia-smi --query-gpu=name,temperature.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null || echo 'GPU indisponivel'")
        docker = _ssh("docker ps --format '{{.Names}} ({{.Status}})' | head -10")
        return (
            f"=== fox-server ===\nCPU: {cpu}\nRAM: {mem}\nDisco:\n{disk}\n"
            f"GPU: {gpu}\nContainers:\n{docker}"
        )
    except Exception as e:
        return f"Erro SSH fox-server: {e}"


# ---------------------------------------------------------------------------
# Arquivos em D:\
# ---------------------------------------------------------------------------

@app.post("/list_directory", response_class=PlainTextResponse, operation_id="list_directory")
def list_directory(req: PathRequest) -> str:
    """Lista arquivos e pastas em D:\\ ou subdiretório."""
    resolved = _check_path(req.path)
    if not os.path.exists(resolved):
        return f"Diretorio nao existe: {resolved}"
    items = []
    for name in sorted(os.listdir(resolved)):
        full = os.path.join(resolved, name)
        if os.path.isdir(full):
            items.append(f"[DIR]  {name}/")
        else:
            items.append(f"[FILE] {name} ({os.path.getsize(full)} bytes)")
    return f"{resolved}\n" + ("\n".join(items) if items else "(vazio)")


@app.post("/create_directory", response_class=PlainTextResponse, operation_id="create_directory")
def create_directory(req: PathRequest) -> str:
    """Cria um diretório (e subdiretórios) em D:\\."""
    resolved = _check_path(req.path)
    os.makedirs(resolved, exist_ok=True)
    return f"Diretorio criado: {resolved}"


@app.post("/write_file", response_class=PlainTextResponse, operation_id="write_file")
def write_file(req: WriteRequest) -> str:
    """Grava qualquer arquivo de texto em D:\\ (html, txt, md, json, py, js, css...)."""
    resolved = _check_path(req.path)
    os.makedirs(os.path.dirname(resolved), exist_ok=True)
    with open(resolved, "w", encoding="utf-8") as f:
        f.write(req.content)
    return f"Arquivo gravado: {resolved} ({len(req.content)} chars)"


@app.post("/read_file", response_class=PlainTextResponse, operation_id="read_file")
def read_file(req: PathRequest) -> str:
    """Lê o conteúdo de um arquivo em D:\\."""
    resolved = _check_path(req.path)
    if not os.path.exists(resolved):
        return f"Nao encontrado: {resolved}"
    with open(resolved, "r", encoding="utf-8", errors="replace") as f:
        return f.read(8000)


@app.post("/delete_file", response_class=PlainTextResponse, operation_id="delete_file")
def delete_file(req: PathRequest) -> str:
    """Deleta um arquivo em D:\\."""
    resolved = _check_path(req.path)
    if not os.path.exists(resolved):
        return f"Nao encontrado: {resolved}"
    if os.path.isdir(resolved):
        return "E um diretorio, use delete_directory."
    os.remove(resolved)
    return f"Deletado: {resolved}"


@app.post("/delete_directory", response_class=PlainTextResponse, operation_id="delete_directory")
def delete_directory(req: PathRequest) -> str:
    """Deleta um diretório e todo seu conteúdo em D:\\. Irreversível."""
    resolved = _check_path(req.path)
    if resolved.upper().rstrip("\\") == "D:":
        return "Nao e permitido deletar a raiz D:\\."
    if not os.path.exists(resolved):
        return f"Nao encontrado: {resolved}"
    shutil.rmtree(resolved)
    return f"Diretorio removido: {resolved}"


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------

@app.post("/run_powershell", response_class=PlainTextResponse, operation_id="run_powershell")
def run_powershell(req: ShellRequest) -> str:
    """Executa PowerShell no fox-wks. Comandos destrutivos (shutdown, format, iex) são bloqueados."""
    blocked = ["shutdown", "restart", "format-", "invoke-expression", "iex "]
    for b in blocked:
        if b in req.command.lower():
            return "Bloqueado: comando nao permitido."
    return (_ps(req.command, timeout=20) or "(sem output)")


# ---------------------------------------------------------------------------
# Agent-mesh (via SSH para fox-server)
# ---------------------------------------------------------------------------

@app.post("/read_agent_memory", response_class=PlainTextResponse, operation_id="read_agent_memory")
def read_agent_memory(req: MemoryLimitRequest) -> str:
    """Lê as memórias mais recentes do agent-mesh do fox-server."""
    limit = max(1, min(int(req.limit), 50))
    sql = (
        "SELECT key, agent, substr(value,1,120), updated_at "
        f"FROM shared_memory ORDER BY updated_at DESC LIMIT {limit};"
    )
    cmd = f'sqlite3 ~/.agent-mesh/state.db "{sql}"'
    return _ssh(cmd)


@app.post("/write_agent_memory", response_class=PlainTextResponse, operation_id="write_agent_memory")
def write_agent_memory(req: AgentMemoryWriteRequest) -> str:
    """Grava uma memória no agent-mesh do fox-server (fonte: fox-wks)."""
    safe = req.value.replace("'", "''")
    cmd = f"python3 ~/.agent-mesh/write-memory.py '{req.key}' '{safe}' fox-wks"
    return _ssh(cmd)


# ---------------------------------------------------------------------------
# Visão (via TurboQuant no fox-server)
# ---------------------------------------------------------------------------

@app.post("/analyze_image", response_class=PlainTextResponse, operation_id="analyze_image")
def analyze_image(req: AnalyzeImageRequest) -> str:
    """
    Analisa uma imagem usando visão computacional (Qwen3.6 multimodal via fox-server).
    Aceita caminho em D:\\ ou URL HTTP do OWU.
    """
    import base64
    import urllib.request

    try:
        if req.image_source.startswith("http://") or req.image_source.startswith("https://"):
            opener = urllib.request.Request(req.image_source)
            opener.add_header("Authorization", f"Bearer {OWU_API_KEY}")
            with urllib.request.urlopen(opener, timeout=15) as resp:
                img_bytes = resp.read()
        else:
            path = req.image_source
            if not path.upper().startswith("D:\\"):
                raise HTTPException(status_code=400, detail="Caminho deve ser D:\\ ou URL HTTP.")
            with open(path, "rb") as f:
                img_bytes = f.read()

        img_b64 = base64.b64encode(img_bytes).decode()
        ext = req.image_source.rsplit(".", 1)[-1].lower() if "." in req.image_source else "jpeg"
        mime = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif", "webp": "image/webp",
        }.get(ext, "image/jpeg")

        payload = json.dumps({
            "model": TURBOQUANT_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
                    {"type": "text", "text": req.question},
                ],
            }],
            "max_tokens": 2048,
            "temperature": 0.1,
        }).encode()

        req2 = urllib.request.Request(
            TURBOQUANT_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req2, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except Exception as e:
        return f"Erro na análise de imagem: {e}"


# ---------------------------------------------------------------------------
# Áudio (OmniVoice via ComfyUI)
# ---------------------------------------------------------------------------

@app.post("/generate_audio", response_class=PlainTextResponse, operation_id="generate_audio")
def generate_audio(req: AudioRequest) -> str:
    """
    Gera síntese de voz (TTS) em português via OmniVoice local (ComfyUI).
    voice_profile: 'raposa' (masculino jovem) ou 'tartaruga' (feminino idoso/lento).
    Retorna tag HTML audio para reprodução direta no chat.
    """
    import random
    import urllib.request

    profiles = {
        "raposa":    {"gender": "male",   "age": "young adult", "pitch": "none", "accent": "portuguese accent", "speed": 1.0},
        "tartaruga": {"gender": "female", "age": "elderly",     "pitch": "none", "accent": "portuguese accent", "speed": 0.8},
    }
    p = profiles.get(req.voice_profile.lower(), {"gender": "male", "age": "adult", "pitch": "none", "accent": "portuguese accent", "speed": 1.0})

    prompt_data = {
        "1": {
            "class_type": "OmniVoiceLoadModel",
            "inputs": {
                "device": "auto", "dtype": "auto",
                "offload_after_generate": False,
                "asr_model_name": "openai/whisper-large-v3-turbo",
            },
        },
        "2": {
            "class_type": "OmniVoiceGenerate",
            "inputs": {
                "pipe": ["1", 0],
                "text": req.text,
                "language": "auto",
                "style_gender": p["gender"],
                "style_age": p["age"],
                "style_pitch": p["pitch"],
                "style_accent": p["accent"],
                "num_step": 32,
                "guidance_scale": 2.0,
                "t_shift": 0.1,
                "layer_penalty_factor": 5.0,
                "position_temperature": 5.0,
                "class_temperature": 0.0,
                "speed": p["speed"],
                "seed": random.randint(1, 2147483647),
                "use_duration": False,
                "duration": 10.0,
                "postprocess_output": True,
            },
        },
        "3": {
            "class_type": "SaveAudio",
            "inputs": {"audio": ["2", 0], "filename_prefix": "audio/OmniVoice_Test"},
        },
    }

    data = json.dumps({"prompt": prompt_data}).encode("utf-8")
    req2 = urllib.request.Request(
        f"{COMFY_URL}/prompt", data=data, headers={"Content-Type": "application/json"}
    )
    res = json.loads(urllib.request.urlopen(req2, timeout=10).read())
    prompt_id = res["prompt_id"]

    deadline = time.time() + 180
    while time.time() < deadline:
        try:
            hist = json.loads(urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=5).read())
            if prompt_id in hist:
                status = hist[prompt_id].get("status", {})
                if not status.get("completed"):
                    raise HTTPException(status_code=500, detail=f"ComfyUI erro: {status}")
                for out in hist[prompt_id]["outputs"].values():
                    for a in out.get("audio", []):
                        url = f"http://192.168.88.202:8188/view?filename={a['filename']}&subfolder={a['subfolder']}&type={a['type']}"
                        return f'<audio controls src="{url}"></audio>'
        except HTTPException:
            raise
        except Exception:
            pass
        time.sleep(2)

    raise HTTPException(status_code=504, detail="Timeout na geração de áudio.")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8091, log_level="info")
