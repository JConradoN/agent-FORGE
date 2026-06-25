from __future__ import annotations

import subprocess
import json
import requests


_WKS_HOST = "192.168.88.202"
_WKS_USER = "morph"
_LLAMA_URL = f"http://{_WKS_HOST}:8082"


def _ssh(cmd: str, timeout: int = 10) -> str:
    r = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=8",
         f"{_WKS_USER}@{_WKS_HOST}", cmd],
        capture_output=True, text=True, timeout=timeout
    )
    return r.stdout.strip() or r.stderr.strip()


def collect_wks_health() -> str:
    """Coleta métricas de saúde do fox-wks via SSH e HTTP."""
    results: dict = {"host": "fox-wks", "ip": _WKS_HOST}

    # CPU e RAM via PowerShell remoto
    try:
        ps = (
            "$os=Get-CimInstance Win32_OperatingSystem; "
            "$cpu=(Get-CimInstance Win32_Processor).LoadPercentage; "
            "Write-Output ($cpu.ToString()+' '+$os.TotalVisibleMemorySize.ToString()+' '+$os.FreePhysicalMemory.ToString())"
        )
        raw = _ssh(f'powershell -NoProfile -NonInteractive -Command "{ps}"')
        parts = raw.split()
        if len(parts) >= 3:
            cpu_pct = int(parts[0])
            total_mb = int(parts[1]) // 1024
            free_mb  = int(parts[2]) // 1024
            used_mb  = total_mb - free_mb
            results["cpu_pct"] = cpu_pct
            results["ram_used_mb"] = used_mb
            results["ram_total_mb"] = total_mb
    except Exception as e:
        results["cpu_ram_error"] = str(e)

    # GPU via nvidia-smi
    try:
        gpu_raw = _ssh(
            "nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw "
            "--format=csv,noheader,nounits"
        )
        if gpu_raw:
            p = [x.strip() for x in gpu_raw.split(",")]
            if len(p) >= 6:
                results["gpu"] = {
                    "name": p[0], "temp_c": p[1], "util_pct": p[2],
                    "vram_used_mb": p[3], "vram_total_mb": p[4], "power_w": p[5]
                }
    except Exception as e:
        results["gpu_error"] = str(e)

    # Disco D:\
    try:
        disk_raw = _ssh(
            'powershell -NoProfile -NonInteractive -Command '
            '"$d=Get-PSDrive D; Write-Output (($d.Used/1GB).ToString(\'F1\')+\' \'+($d.Free/1GB).ToString(\'F1\'))"'
        )
        parts = disk_raw.split()
        if len(parts) >= 2:
            results["disk_D"] = {"used_gb": float(parts[0]), "free_gb": float(parts[1])}
    except Exception as e:
        results["disk_error"] = str(e)

    # llama-server status
    try:
        resp = requests.get(f"{_LLAMA_URL}/health", timeout=5)
        results["llama_server"] = resp.json().get("status", resp.text[:100])
    except Exception as e:
        results["llama_server"] = f"unreachable: {e}"

    # Formatar saída
    lines = [f"=== fox-wks ({_WKS_HOST}) ==="]
    if "cpu_pct" in results:
        lines.append(f"CPU: {results['cpu_pct']}%")
        lines.append(f"RAM: {results['ram_used_mb']}/{results['ram_total_mb']} MB")
    elif "cpu_ram_error" in results:
        lines.append(f"CPU/RAM: erro — {results['cpu_ram_error']}")

    if "gpu" in results:
        g = results["gpu"]
        lines.append(f"GPU: {g['name']} | {g['temp_c']}°C | {g['util_pct']}% | {g['vram_used_mb']}/{g['vram_total_mb']} MB VRAM | {g['power_w']}W")
    elif "gpu_error" in results:
        lines.append(f"GPU: erro — {results['gpu_error']}")

    if "disk_D" in results:
        d = results["disk_D"]
        lines.append(f"Disco D: {d['used_gb']} GB usados, {d['free_gb']} GB livres")

    lines.append(f"llama-server :8082 → {results.get('llama_server', 'N/A')}")

    return "\n".join(lines)
