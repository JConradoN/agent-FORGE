from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from socket import gethostname
from typing import Any

import psutil


def _get_gpu_info() -> dict | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        line = result.stdout.strip()
        if not line:
            return None

        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            return None

        name = parts[0]
        utilization = int(parts[1])
        temperature = int(parts[2])
        vram_used = int(parts[3])
        vram_total = int(parts[4])

        return {
            "name": name,
            "utilization": utilization,
            "temperature": temperature,
            "vram_used_mb": vram_used,
            "vram_total_mb": vram_total,
        }
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        return None


def _get_top_processes(by: str = "cpu", limit: int = 5) -> list[dict[str, Any]]:
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            if info["cpu_percent"] is None:
                info["cpu_percent"] = 0.0
            if info["memory_percent"] is None:
                info["memory_percent"] = 0.0
            processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu_percent" if by == "cpu" else "memory_percent"
    processes.sort(key=lambda x: x[key] or 0, reverse=True)

    return [
        {
            "pid": p["pid"],
            "name": p["name"],
            "cpu_percent": round(p["cpu_percent"], 1),
            "memory_percent": round(p["memory_percent"], 1),
        }
        for p in processes[:limit]
    ]


def collect_system_health() -> dict[str, Any]:
    cpu_percent = psutil.cpu_percent(interval=0.5)

    load_avg = None
    try:
        load_avg = psutil.getloadavg()
    except AttributeError:
        pass

    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_available_mb = mem.available / (1024 * 1024)

    disk = psutil.disk_usage("/")
    disk_percent = disk.percent
    disk_free_gb = disk.free / (1024 * 1024 * 1024)

    gpu = _get_gpu_info()

    top_cpu = _get_top_processes(by="cpu", limit=5)
    top_mem = _get_top_processes(by="memory", limit=5)

    alerts: list[str] = []
    if cpu_percent > 85:
        alerts.append("cpu_high")
    if mem_percent > 90:
        alerts.append("memory_high")
    if disk_percent > 85:
        alerts.append("disk_high")

    if gpu:
        vram_percent = (gpu["vram_used_mb"] / gpu["vram_total_mb"]) * 100 if gpu["vram_total_mb"] > 0 else 0
        if vram_percent > 85:
            alerts.append("gpu_vram_high")
        if gpu["temperature"] > 82:
            alerts.append("gpu_temp_high")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": gethostname(),
        "cpu": {
            "usage_percent": round(cpu_percent, 1),
            "load_average": load_avg,
        },
        "memory": {
            "usage_percent": round(mem_percent, 1),
            "available_mb": round(mem_available_mb, 1),
        },
        "disk": {
            "root_usage_percent": round(disk_percent, 1),
            "free_gb": round(disk_free_gb, 2),
        },
        "gpu": gpu,
        "top_processes_cpu": top_cpu,
        "top_processes_memory": top_mem,
        "alerts": alerts,
    }


if __name__ == "__main__":
    result = collect_system_health()
    print(json.dumps(result, indent=2, default=str))