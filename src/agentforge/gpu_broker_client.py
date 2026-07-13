"""Cliente síncrono do fox-gpu-broker — coordena acesso ao TurboQuant/GPU
compartilhado entre AgentForge, Cláudio v2 e scripts de batch.

Fail-open por design: se o broker estiver fora do ar, segue sem coordenar
em vez de travar quem já funcionava sem ele. Perde o benefício de fila com
prioridade nesse cenário, mas não vira ponto único de falha.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager

import requests

log = logging.getLogger("agentforge.gpu_broker_client")

BROKER_URL = os.environ.get("FOX_GPU_BROKER_URL", "http://127.0.0.1:8199")


@contextmanager
def acquire_gpu(
    client: str,
    priority: str = "batch",
    resource: str = "turboquant",
    max_wait_s: float = 300.0,
    broker_url: str = BROKER_URL,
):
    """Bloqueia até conseguir o slot do `resource`; libera automaticamente ao sair do bloco.

    priority: "interactive" (furos a fila de "batch") ou "batch".
    """
    ticket_id = None
    try:
        r = requests.post(
            f"{broker_url}/acquire",
            json={"client": client, "priority": priority, "resource": resource, "max_wait_s": max_wait_s},
            timeout=max_wait_s + 10,
        )
        if r.status_code == 200:
            ticket_id = r.json()["ticket_id"]
        elif r.status_code == 408:
            log.warning("gpu_broker: timeout na fila (%s, %s) — seguindo sem ticket", client, priority)
        else:
            log.warning("gpu_broker: resposta inesperada %s — seguindo sem ticket", r.status_code)
    except requests.exceptions.RequestException as exc:
        log.warning("gpu_broker indisponível (%s) — seguindo sem coordenação", exc)

    try:
        yield
    finally:
        if ticket_id:
            try:
                requests.post(f"{broker_url}/release", json={"ticket_id": ticket_id}, timeout=10)
            except requests.exceptions.RequestException as exc:
                log.warning("gpu_broker: falha ao liberar ticket %s (%s)", ticket_id, exc)
