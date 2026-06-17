#!/usr/bin/env python3
"""
Geração sintética do dataset de fine-tuning do Cláudio.

Usa qwen3.5:27b para gerar novos exemplos JSONL a partir de meta-prompts.

Uso:
    python3 synth_generate.py --count 500 --category all
    python3 synth_generate.py --count 200 --category read_link
    python3 synth_generate.py --count 100 --category run_bash
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_URL = "http://localhost:11434/v1/chat/completions"
GEN_MODEL  = "qwen3.5:27b"
OUT_DIR    = Path(__file__).parent.parent / "dataset"
GOLD_FILE  = OUT_DIR / "gold_seed.jsonl"
OUT_FILE   = OUT_DIR / "synth.jsonl"
LOG_FILE   = OUT_DIR / "synth_progress.log"

SYSTEM_PROMPT = (Path(__file__).parent.parent / "system_prompt.txt").read_text().strip()

# ---------------------------------------------------------------------------
# Tópicos / cenários por categoria
# ---------------------------------------------------------------------------

READ_LINK_TOPICS = [
    "fine-tuning de LLMs com LoRA/QLoRA",
    "RAG (Retrieval-Augmented Generation)",
    "agentes de IA e orquestração de ferramentas",
    "quantização de modelos (GGUF, AWQ, GPTQ)",
    "vector databases (Qdrant, Chroma)",
    "modelos open-source (Llama, Qwen, Gemma, Mistral)",
    "benchmark de LLMs locais",
    "MCP (Model Context Protocol)",
    "inferência local com Ollama",
    "arquitetura de sistemas multi-agente",
    "function calling em LLMs",
    "memória episódica para agentes (mem0, Zep)",
    "grafos de conhecimento (Kuzu, Neo4j)",
    "otimização de throughput em GPUs consumer",
    "DPO e RLHF para alinhamento",
    "Playwright e scraping de páginas dinâmicas",
    "FastAPI para servir modelos locais",
    "n8n e automação de workflows com IA",
    "Unsloth e treino eficiente de LLMs",
    "avaliação de qualidade de LLMs",
    "SFT com TRL/HuggingFace",
    "structured output e JSON mode em LLMs",
    "chain-of-thought e reasoning",
    "modelos multimodais locais (LLaVA, Qwen-VL)",
    "Proxmox e GPU passthrough para VMs",
    "Tailscale e redes privadas para servidores locais",
    "Docker Compose para stacks de ML",
    "embedding models e busca semântica",
    "LLM distillation (destilação de modelos)",
    "ORPO como alternativa ao DPO",
]

RUN_BASH_SCENARIOS = [
    "verificar uso de VRAM das GPUs",
    "listar modelos carregados no Ollama",
    "verificar logs de um serviço systemd",
    "checar espaço em disco no vault",
    "listar containers Docker e status",
    "verificar temperatura CPU/GPU",
    "checar uso de RAM e swap",
    "verificar latência de rede via ping",
    "ver processos mais pesados de CPU",
    "verificar uptime do servidor",
    "checar se Qdrant está respondendo",
    "ver últimas linhas de log do n8n",
    "verificar status do Tailscale",
    "checar se um serviço específico está rodando",
    "listar modelos disponíveis no Ollama",
    "verificar uso de CPU por core",
    "checar conexões de rede ativas",
    "ver erros recentes no journal",
    "verificar se o vault está montado",
    "ver load average do sistema",
    "verificar versão do CUDA no servidor",
    "checar se VMs KVM estão rodando",
    "verificar uso de inode no filesystem",
    "listar processos em swap",
    "checar logs do container ollama",
]

CHAT_SCENARIOS = [
    "usuário pede explicação de um conceito de ML/IA (fine-tuning, RAG, quantização, LoRA, DPO)",
    "usuário pede comparação entre duas abordagens técnicas de IA",
    "usuário faz pergunta de configuração sobre o fox-server",
    "usuário pede recomendação de modelo local para uma tarefa específica",
    "usuário pergunta sobre estratégia do projeto de fine-tuning do 9b",
    "usuário pergunta sobre capacidades do Cláudio",
    "usuário faz uma saudação ou mensagem casual curta",
    "usuário pede ajuda para entender um erro conceitual",
    "usuário pergunta sobre modelos disponíveis localmente no Ollama",
    "usuário pede análise de trade-offs entre duas ferramentas",
    "usuário pergunta sobre custo de infra do fox-server vs cloud",
    "usuário faz pergunta sobre Tailscale ou acesso remoto",
    "usuário pede para explicar o agent-mesh",
    "usuário pergunta sobre o pipeline de geração de vídeo/avatar",
    "usuário pergunta diferença entre SFT e RLHF",
    "usuário quer saber qual modelo usar para uma tarefa específica",
    "usuário pede conselho sobre arquitetura de um novo agente",
    "usuário pergunta sobre o Qdrant e busca vetorial",
    "usuário pede para explicar como o mem0 funciona",
    "usuário quer entender o fluxo completo de fine-tuning planejado",
]

REFUSAL_SCENARIOS = [
    "usuário pede para fazer git commit ou push",
    "usuário pede para enviar email",
    "usuário pede para postar algo no LinkedIn",
    "usuário pede para salvar algo no Kuzu sem ter essa tool",
    "usuário pede para deletar um arquivo sem confirmação",
    "usuário pede para parar todos os containers sem confirmação",
    "usuário pede para reiniciar o servidor sem confirmar",
    "usuário pede para buscar no Google (sem URL específica)",
    "usuário pede para inventar dados ou métricas",
    "usuário pede para comprar algo ou fazer transação",
    "usuário pede para acessar API externa sem URL",
    "usuário pede para desligar o servidor fox-server",
    "usuário pede para apagar todos os logs",
    "usuário pede para criar usuário no sistema sem confirmar",
]

DIFFICULTY_WEIGHTS = {"easy": 0.40, "medium": 0.40, "hard": 0.20}


# ---------------------------------------------------------------------------
# Meta-prompts
# ---------------------------------------------------------------------------

def _json_schema_read_link() -> str:
    """Retorna o schema JSON esperado como string literal (sem f-string)."""
    return (
        '{\n'
        '  "messages": [\n'
        '    {"role": "system", "content": "<system_prompt>"},\n'
        '    {"role": "user", "content": "<mensagem do usuário com URL ou pedido>"},\n'
        '    {"role": "assistant", "content": null, '
        '"tool_calls": [{"type": "function", "function": '
        '{"name": "read_link", "arguments": "{\\"url\\": \\"<URL completa>\\"}"}}]},\n'
        '    {"role": "tool", "name": "read_link", "content": "<conteúdo realista da página, 2-4 frases>"},\n'
        '    {"role": "assistant", "content": "<resposta final substantiva, texto puro, sem markdown>"}\n'
        '  ]\n'
        '}'
    )


def _json_schema_run_bash() -> str:
    return (
        '{\n'
        '  "messages": [\n'
        '    {"role": "system", "content": "<system_prompt>"},\n'
        '    {"role": "user", "content": "<pedido do usuário>"},\n'
        '    {"role": "assistant", "content": null, '
        '"tool_calls": [{"type": "function", "function": '
        '{"name": "run_bash", "arguments": "{\\"command\\": \\"<comando bash real>\\"}"}}]},\n'
        '    {"role": "tool", "name": "run_bash", "content": "<output realista de terminal>"},\n'
        '    {"role": "assistant", "content": "<interpretação e resposta, texto puro>"}\n'
        '  ]\n'
        '}'
    )


def _json_schema_chat() -> str:
    return (
        '{\n'
        '  "messages": [\n'
        '    {"role": "system", "content": "<system_prompt>"},\n'
        '    {"role": "user", "content": "<mensagem do usuário>"},\n'
        '    {"role": "assistant", "content": "<resposta do Cláudio, texto puro>"}\n'
        '  ]\n'
        '}'
    )


def build_meta_prompt(category: str, subcategory: str, difficulty: str) -> str:
    sys_note = (
        "IMPORTANTE: O campo 'content' do role 'system' deve conter EXATAMENTE este texto "
        "(copie literalmente, não resuma):\n\n"
        + SYSTEM_PROMPT
    )

    diff_desc = {
        "easy":   "Simples e direto. Pergunta clara, resposta concisa.",
        "medium": "Mais contexto. Análise que conecta com o projeto do usuário.",
        "hard":   "Complexo. Trade-offs, implicações, múltiplos ângulos.",
    }[difficulty]

    if subcategory == "read_link":
        topic = random.choice(READ_LINK_TOPICS)
        schema = _json_schema_read_link()
        return "\n".join([
            "Você é um gerador de exemplos de fine-tuning para o assistente Cláudio.",
            "",
            f"Gere UM exemplo de conversa onde o usuário envia uma URL ou pede para ler um link sobre: {topic}.",
            f"Dificuldade: {difficulty} — {diff_desc}",
            "",
            "Regras OBRIGATÓRIAS:",
            "1. O assistente DEVE chamar read_link antes de responder",
            "2. O tool_result simula conteúdo realista de uma página real (2-4 frases informativas)",
            "3. A resposta final: texto puro sem markdown (* # \\ etc), listas com hífen (-)",
            "4. URL deve ser plausível (LinkedIn, arXiv, GitHub, huggingface.co, docs.*)",
            "5. A análise conecta o conteúdo ao contexto do usuário (fox-server, fine-tuning do 9b, agentes)",
            "",
            sys_note,
            "",
            "Retorne SOMENTE o JSON válido no formato abaixo (substitua <system_prompt> pelo texto copiado):",
            "",
            schema,
        ])

    elif subcategory == "run_bash":
        scenario = random.choice(RUN_BASH_SCENARIOS)
        schema = _json_schema_run_bash()
        return "\n".join([
            "Você é um gerador de exemplos de fine-tuning para o assistente Cláudio.",
            "",
            f"Gere UM exemplo onde o usuário pede: {scenario}.",
            f"Dificuldade: {difficulty} — {diff_desc}",
            "",
            "Regras OBRIGATÓRIAS:",
            "1. O assistente DEVE chamar run_bash antes de responder",
            "2. O command é um comando bash real e válido para Ubuntu",
            "3. O tool_result simula output realista de terminal (números plausíveis para o fox-server)",
            "4. Para comandos destrutivos: pedir confirmação ANTES de executar (sem tool_call ainda)",
            "5. Resposta: texto puro sem markdown, crases só para código",
            "",
            "Contexto da máquina:",
            "Xeon E5-2696 v3 (36 threads), 128GB RAM, 2xRTX 3060 12GB",
            "Containers: n8n:5678, ollama:11434, qdrant:6333, open-webui:3000, portainer:9443",
            "",
            sys_note,
            "",
            "Retorne SOMENTE o JSON válido no formato abaixo:",
            "",
            schema,
        ])

    elif category == "chat":
        scenario = random.choice(CHAT_SCENARIOS)
        schema = _json_schema_chat()
        return "\n".join([
            "Você é um gerador de exemplos de fine-tuning para o assistente Cláudio.",
            "",
            f"Gere UM exemplo de chat: {scenario}.",
            f"Dificuldade: {difficulty} — {diff_desc}",
            "",
            "Regras OBRIGATÓRIAS:",
            "1. NÃO usar ferramentas — conversa pura",
            "2. Resposta em PT-BR, texto puro sem markdown (* # \\ etc)",
            "3. Cláudio é expert técnico: direto, sem condescendência, sem emojis",
            "4. O usuário é desenvolvedor avançado de IA/infra — não explicar conceitos óbvios",
            "5. Se pedir algo fora das capacidades (git, email): recusar claramente em 1-2 frases",
            "",
            sys_note,
            "",
            "Retorne SOMENTE o JSON válido no formato abaixo:",
            "",
            schema,
        ])

    else:  # refusal
        scenario = random.choice(REFUSAL_SCENARIOS)
        schema = _json_schema_chat()
        return "\n".join([
            "Você é um gerador de exemplos de fine-tuning para o assistente Cláudio.",
            "",
            f"Gere UM exemplo onde o usuário pede algo e Cláudio recusa: {scenario}.",
            "",
            "Regras OBRIGATÓRIAS:",
            "1. NÃO usar ferramentas",
            "2. Recusa direta, sem drama, sem desculpas excessivas (1-3 frases)",
            "3. Explica brevemente POR QUE não pode e, quando aplicável, como o usuário pode fazer",
            "4. Texto puro sem markdown",
            "5. NÃO inventar outputs — se não executou, não confirma",
            "",
            sys_note,
            "",
            "Retorne SOMENTE o JSON válido no formato abaixo:",
            "",
            schema,
        ])


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def wait_for_ollama_idle(timeout_s: int = 60) -> bool:
    """Aguarda até o slot do Ollama estar livre antes de enviar request."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            req = urllib.request.Request(
                "http://localhost:11434/api/ps",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                models = data.get("models", [])
                # Se nenhum modelo está em "processing", o slot está livre
                busy = any(m.get("processing_count", 0) > 0 for m in models)
                if not busy:
                    return True
        except Exception:
            pass
        time.sleep(10)
    return False  # nunca ficou livre dentro do timeout


def call_llm(prompt: str, temperature: float = 0.85) -> str | None:
    payload = json.dumps({
        "model": GEN_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                OLLAMA_URL, data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=300) as r:
                result = json.loads(r.read())
                return result["choices"][0]["message"]["content"].strip()
        except Exception:
            # Backoff exponencial: 30s, 60s, 120s
            wait = 30 * (2 ** attempt)
            print(f"  [retry {attempt+1}/3] aguardando {wait}s...", flush=True)
            time.sleep(wait)
    return None


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

def validate(obj: dict, category: str, subcategory: str) -> tuple[bool, str]:
    msgs = obj.get("messages", [])
    if not msgs:
        return False, "sem mensagens"
    if msgs[0].get("role") != "system":
        return False, "primeiro role não é system"
    if len(msgs) < 3:
        return False, "menos de 3 mensagens"

    if category == "tool_calling":
        has_tool_call   = any("tool_calls" in m and m["tool_calls"] for m in msgs)
        has_tool_result = any(m.get("role") == "tool" for m in msgs)
        if not has_tool_call:
            return False, "sem tool_call"
        if not has_tool_result:
            return False, "sem tool result"
        for m in msgs:
            if "tool_calls" in m and m["tool_calls"]:
                name = m["tool_calls"][0]["function"]["name"]
                if name != subcategory:
                    return False, f"tool errada: {name} != {subcategory}"
                # Valida que arguments é JSON string válida
                try:
                    args_str = m["tool_calls"][0]["function"]["arguments"]
                    json.loads(args_str)
                except Exception:
                    return False, "arguments não é JSON válido"

    last = msgs[-1]
    if last.get("role") != "assistant":
        return False, "última mensagem não é assistant"
    content = last.get("content") or ""
    if not content.strip():
        return False, "resposta final vazia"

    return True, "ok"


# ---------------------------------------------------------------------------
# Load existing IDs
# ---------------------------------------------------------------------------

def load_existing_ids() -> set[str]:
    ids = set()
    for f in [GOLD_FILE, OUT_FILE]:
        if f.exists():
            for line in f.read_text().splitlines():
                try:
                    obj = json.loads(line)
                    if "id" in obj:
                        ids.add(obj["id"])
                except Exception:
                    pass
    return ids


# ---------------------------------------------------------------------------
# Category map
# ---------------------------------------------------------------------------

CATEGORY_MAP = {
    "all": [
        ("tool_calling", "read_link", 0.35),
        ("tool_calling", "run_bash",  0.20),
        ("chat",         "persona",   0.30),
        ("refusal",      "mixed",     0.15),
    ],
    "tool_calling": [
        ("tool_calling", "read_link", 0.55),
        ("tool_calling", "run_bash",  0.45),
    ],
    "read_link": [("tool_calling", "read_link", 1.0)],
    "run_bash":  [("tool_calling", "run_bash",  1.0)],
    "chat":      [("chat",         "persona",   1.0)],
    "refusal":   [("refusal",      "mixed",     1.0)],
}


def pick_cat(category: str) -> tuple[str, str]:
    options = CATEGORY_MAP.get(category, CATEGORY_MAP["all"])
    cats  = [o[0] for o in options]
    subs  = [o[1] for o in options]
    weights = [o[2] for o in options]
    idx = random.choices(range(len(cats)), weights=weights)[0]
    return cats[idx], subs[idx]


def pick_difficulty() -> str:
    opts = list(DIFFICULTY_WEIGHTS.keys())
    weights = list(DIFFICULTY_WEIGHTS.values())
    return random.choices(opts, weights=weights)[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",       type=int,   default=100)
    parser.add_argument("--category",    default="all",
                        choices=["all", "tool_calling", "read_link", "run_bash", "chat", "refusal"])
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--retries",     type=int,   default=3)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    existing_ids = load_existing_ids()
    nums = [int(i.split("-")[-1]) for i in existing_ids
            if i.startswith("claudio-") and i.split("-")[-1].isdigit()]
    next_id = (max(nums) if nums else 50) + 1

    log = LOG_FILE.open("a")
    out = OUT_FILE.open("a")

    generated = 0
    failed    = 0
    start     = time.time()

    print(f"Gerando {args.count} exemplos com {GEN_MODEL} | categoria={args.category}")
    print(f"Output: {OUT_FILE}")
    print(f"IDs existentes: {len(existing_ids)} | próximo id: claudio-{next_id:04d}")
    print()

    while generated < args.count:
        category, subcategory = pick_cat(args.category)
        difficulty = pick_difficulty()
        prompt = build_meta_prompt(category, subcategory, difficulty)

        ok = False
        for attempt in range(1, args.retries + 1):
            raw = call_llm(prompt, temperature=args.temperature)
            if raw is None:
                log.write(f"[TIMEOUT] {category}/{subcategory} tentativa {attempt}\n")
                log.flush()
                time.sleep(5)
                continue

            # Extrai JSON (modelo pode embrulhar em ```json```)
            json_str = raw
            m = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
            if m:
                json_str = m.group(1).strip()
            # Garante que começa com {
            brace = json_str.find("{")
            if brace > 0:
                json_str = json_str[brace:]

            try:
                obj = json.loads(json_str)
            except json.JSONDecodeError as e:
                msg = f"[JSON_ERROR] {category}/{subcategory} tentativa {attempt}: {e}"
                print(msg, flush=True)
                log.write(msg + "\n")
                log.flush()
                failed += 1
                if attempt < args.retries:
                    continue
                break

            valid, reason = validate(obj, category, subcategory)
            if not valid:
                msg = f"[INVALID] {category}/{subcategory} tentativa {attempt}: {reason}"
                print(msg, flush=True)
                log.write(msg + "\n")
                log.flush()
                failed += 1
                if attempt < args.retries:
                    continue
                break

            example_id = f"claudio-{next_id:04d}"
            next_id += 1
            record = {
                "id":          example_id,
                "category":    category,
                "subcategory": subcategory,
                "difficulty":  difficulty,
                "source":      "synthetic_27b",
                "validated":   False,
                "validator":   None,
                "messages":    obj["messages"],
            }

            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()
            generated += 1
            elapsed = time.time() - start
            rate = generated / elapsed * 60
            msg = (f"[{generated:4d}/{args.count}] {example_id} "
                   f"{category}/{subcategory}/{difficulty} ({rate:.1f}/min)")
            print(msg, flush=True)
            log.write(f"[OK] {example_id} {category}/{subcategory}/{difficulty}\n")
            log.flush()
            ok = True
            break

        if not ok:
            # Conta falha total mas continua
            pass

        time.sleep(0.3)

    elapsed = time.time() - start
    print(f"\nConcluido: {generated} exemplos em {elapsed/60:.1f} min ({failed} falhas)")
    print(f"Taxa: {generated / elapsed * 60:.1f} exemplos/min")
    out.close()
    log.close()


if __name__ == "__main__":
    main()
