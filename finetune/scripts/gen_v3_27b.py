#!/usr/bin/env python3
"""
Geração de exemplos V3 via qwen3.5:27b local (Ollama REST API).

Foco: create_then_use + tool_discovery + general_reasoning
- 1 exemplo por chamada → qualidade máxima
- Validação imediata antes de salvar
- Retry automático com variação de prompt
- Target: 300-500 exemplos em ~7 horas

Uso:
    python3 gen_v3_27b.py [--target 400] [--output synth_v3_27b.jsonl]
"""

import argparse
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OLLAMA_URL   = "http://localhost:11434/api/chat"
MODEL        = "qwen3.5:27b"
DATASET_DIR  = Path(__file__).parent.parent / "dataset"
LOG_DIR      = Path(__file__).parent.parent / "logs"
DEFAULT_OUT  = "synth_v3_27b.jsonl"
DEFAULT_TARGET = 400
TIMEOUT      = 180   # segundos por chamada
PAUSE_OK     = 5     # pausa após sucesso
PAUSE_ERR    = 15    # pausa após erro/retry

# ---------------------------------------------------------------------------
# Schema de exemplo canônico (referência para o modelo)
# ---------------------------------------------------------------------------
CANONICAL_SCHEMA = {
    "id": "v3-27b-NNN",
    "messages": [
        {"role": "system",  "content": "Você é Cláudio, agente AgentForge..."},
        {"role": "user",    "content": "<tarefa do usuário>"},
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "call_1", "type": "function",
                         "function": {"name": "tool_name",
                                      "arguments": {"param": "value"}}}]},
        {"role": "tool",    "content": "<resultado da tool>", "name": "tool_name"},
        {"role": "assistant", "content": "<resposta final ao usuário>"}
    ]
}

# ---------------------------------------------------------------------------
# Categorias e prompts por categoria
# ---------------------------------------------------------------------------
CATEGORIES = {
    "create_then_use": {
        "weight": 35,
        "scenarios": [
            ("text_summarizer", "sumarizar múltiplos arquivos de log em relatório"),
            ("csv_merger", "mesclar 3 arquivos CSV com colunas diferentes"),
            ("port_scanner_lite", "verificar quais portas estão abertas em host"),
            ("json_flattener", "achatar JSON aninhado para planilha"),
            ("markdown_to_html", "converter docs Markdown para HTML com estilos"),
            ("token_counter", "contar tokens em múltiplos arquivos de texto"),
            ("diff_checker", "comparar dois diretórios e listar arquivos divergentes"),
            ("config_auditor", "auditar arquivo .env e detectar chaves faltando"),
            ("dependency_graph", "gerar grafo de dependências de um projeto Python"),
            ("api_load_tester", "testar endpoint com N requisições paralelas"),
            ("log_parser", "parsear logs com regex e agregar por nível de erro"),
            ("schema_validator", "validar JSON contra schema e reportar erros"),
        ]
    },
    "tool_discovery": {
        "weight": 30,
        "scenarios": [
            "análise de sentimento em comentários de código",
            "geração de thumbnail para vídeo",
            "busca semântica em documentos locais",
            "sincronização de estado entre agentes",
            "monitoramento de uso de GPU em tempo real",
            "extração de entidades de texto livre",
            "agendamento de tarefa com cron local",
            "backup incremental de diretório",
            "relatório de cobertura de testes",
            "notificação condicional por threshold",
            "compilação de changelog a partir de git log",
            "verificação de saúde de serviços Docker",
        ]
    },
    "general_reasoning": {
        "weight": 20,
        "scenarios": [
            "explicar trade-offs entre PostgreSQL e MongoDB para dados de séries temporais",
            "como implementar circuit breaker em sistema de microserviços Python",
            "diferença entre fine-tuning e RAG para LLMs corporativos",
            "estratégia de migração de monolito para microserviços sem downtime",
            "como debugar vazamento de memória em processo Python de longa duração",
            "quando usar mutex vs canal em Go para comunicação entre goroutines",
            "diferença entre eventual consistency e strong consistency em sistemas distribuídos",
            "como estruturar permissões RBAC em API REST com múltiplos tenants",
            "trade-offs entre SSE e WebSockets para streaming de dados ao frontend",
            "como modelar um sistema de filas de prioridade com Redis",
        ]
    },
    "schema_driven_use": {
        "weight": 15,
        "scenarios": [
            ("score_document", {"text": "string", "rubric": "string"}, "avaliar qualidade de documentação"),
            ("ingest_event", {"source": "string", "payload": "dict", "ts": "string"}, "registrar evento no pipeline"),
            ("hydrate_template", {"template_id": "string", "vars": "dict"}, "renderizar template com variáveis"),
            ("pin_context", {"key": "string", "data": "dict", "ttl_s": "int"}, "salvar contexto efêmero"),
            ("resolve_conflict", {"doc_a": "string", "doc_b": "string"}, "mesclar dois documentos divergentes"),
            ("emit_trace", {"span_id": "string", "tags": "dict", "duration_ms": "float"}, "registrar span de trace"),
            ("quantize_model", {"model_path": "string", "bits": "int", "method": "string"}, "quantizar modelo local"),
            ("replay_events", {"queue": "string", "from_ts": "string", "dry_run": "bool"}, "reprocessar eventos históricos"),
        ]
    }
}


def log(msg: str, logfile):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    logfile.write(line + "\n")
    logfile.flush()


def pick_category():
    cats = list(CATEGORIES.keys())
    weights = [CATEGORIES[c]["weight"] for c in cats]
    return random.choices(cats, weights=weights, k=1)[0]


def build_prompt(cat: str, example_id: str) -> str:
    """Constrói prompt específico por categoria."""

    base_rules = f"""Você vai gerar UM exemplo de dataset de fine-tuning para um LLM agêntico chamado Cláudio.

ID DO EXEMPLO: {example_id}

FORMATO OBRIGATÓRIO (JSON puro, sem markdown, sem bloco ```):
{{
  "id": "{example_id}",
  "messages": [
    {{"role": "system", "content": "Você é Cláudio, agente AgentForge. Responda sempre em PT-BR. Use as ferramentas disponíveis para completar tarefas. Seja direto e técnico."}},
    {{"role": "user", "content": "<pedido do usuário>"}},
    ... (tool_calls e respostas conforme a tarefa) ...
    {{"role": "assistant", "content": "<resposta final ao usuário>"}}
  ]
}}

REGRAS CRÍTICAS:
- tool_calls[].function.arguments = dict Python (nunca string JSON)
- role "tool" sempre tem campo "name" com nome da ferramenta
- Sem quebra de linha literal dentro de strings (use \\n)
- Última mensagem SEMPRE role=assistant com texto de conclusão
- Retorne APENAS o JSON, sem explicação, sem markdown
"""

    if cat == "create_then_use":
        scen = random.choice(CATEGORIES[cat]["scenarios"])
        tool_name, use_case = scen
        return base_rules + f"""CATEGORIA: create_then_use
TAREFA: usuário pede para {use_case}.

Gere o JSON diretamente. Sequência de mensagens:
1. system: instrução do agente
2. user: pedido de {use_case}
3. assistant com tool_call write_file → cria tools/{tool_name}.py com classe ToolSpec Python
4. tool (name=write_file): "Arquivo criado com sucesso"
5. assistant com tool_call {tool_name} → usa a tool recém criada com args reais
6. tool (name={tool_name}): resultado simulado da execução
7. assistant: resposta final em PT-BR

O código Python dentro do write_file deve ter: imports reais, class {tool_name.title().replace('_','')}Tool com name="{tool_name}", description, input_schema dict, método execute(**kwargs)->str.

IMPORTANTE: retorne APENAS o JSON, sem texto antes ou depois.
"""

    elif cat == "tool_discovery":
        scen = random.choice(CATEGORIES[cat]["scenarios"])
        return base_rules + f"""
CATEGORIA: tool_discovery
TAREFA: O usuário pede ajuda com: {scen}

O modelo NÃO sabe quais tools existem. Deve:
1. Descobrir tools via run_bash: ls /app/tools/ ou equivalente
2. Ler spec da tool mais relevante via read_file
3. Usar a tool com argumentos corretos baseados na spec lida
4. Completar a tarefa e responder ao usuário

A tool pode não existir — nesse caso o modelo tenta alternativa (run_bash com comando direto).
Nunca questionar se a tool existe; agir e adaptar.
"""

    elif cat == "general_reasoning":
        scen = random.choice(CATEGORIES[cat]["scenarios"])
        return base_rules + f"""
CATEGORIA: general_reasoning (SEM tool calls)
TAREFA: O usuário pergunta: "{scen}"

O modelo deve:
- Responder diretamente SEM usar nenhuma tool
- Resposta técnica, estruturada, em PT-BR
- 300-500 palavras com exemplos concretos quando aplicável
- Tom: direto, sênior, sem fluff

NÃO inclua tool_calls. Apenas system → user → assistant.
"""

    else:  # schema_driven_use
        scen = random.choice(CATEGORIES[cat]["scenarios"])
        tool_name, params, task = scen
        params_str = json.dumps(params, ensure_ascii=False)
        return base_rules + f"""
CATEGORIA: schema_driven_use
TOOL DISPONÍVEL NO SCHEMA: {tool_name}
PARÂMETROS: {params_str}
TAREFA DO USUÁRIO: {task}

O modelo recebe a tool "{tool_name}" no schema (com name, description, parameters).
Deve usá-la SEM questionar se existe — baseando-se apenas no schema fornecido.
Após o resultado, responder ao usuário com conclusão em PT-BR.

Inclua um "system" message que lista a tool disponível com sua descrição e parâmetros.
"""


def call_ollama(prompt: str) -> str:
    """Chama Ollama e retorna o texto de resposta."""
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0.85,
            "top_p": 0.9,
            "num_predict": 2048,
        }
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return data["message"]["content"]


def extract_json(text: str) -> dict | None:
    """Extrai JSON do texto de resposta."""
    # Tenta direto
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Tenta extrair bloco ```json
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Tenta encontrar { ... } maior no texto
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        break
    return None


def validate(obj: dict, expected_id: str) -> tuple[bool, str]:
    """Valida estrutura mínima do exemplo."""
    if not isinstance(obj, dict):
        return False, "não é dict"
    if "messages" not in obj:
        return False, "sem campo messages"
    msgs = obj["messages"]
    if not isinstance(msgs, list) or len(msgs) < 2:
        return False, f"messages inválido (len={len(msgs) if isinstance(msgs, list) else 'N/A'})"

    # Valida tool_calls
    for m in msgs:
        for tc in m.get("tool_calls") or []:
            args = tc.get("function", {}).get("arguments")
            if isinstance(args, str):
                try:
                    json.loads(args)
                except json.JSONDecodeError:
                    return False, f"arguments inválido em {tc.get('function', {}).get('name')}"

    # Última mensagem deve ser assistant
    last = msgs[-1]
    if last.get("role") != "assistant":
        return False, f"última mensagem é {last.get('role')}, esperado assistant"

    # Fix id se necessário
    obj["id"] = expected_id
    return True, "ok"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET)
    parser.add_argument("--output", default=DEFAULT_OUT)
    args = parser.parse_args()

    output_path = DATASET_DIR / args.output
    log_path = LOG_DIR / f"gen_v3_27b_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Conta existentes
    existing = 0
    if output_path.exists():
        existing = sum(1 for l in output_path.read_text().splitlines() if l.strip())

    with open(log_path, "w") as logf, open(output_path, "a") as outf:
        log(f"gen_v3_27b — model={MODEL} target={args.target} output={args.output}", logf)
        log(f"Já existentes: {existing} | Gerando mais: {args.target - existing}", logf)
        log("=" * 60, logf)

        generated = existing
        errors = 0
        retries = 0
        seq = existing + 1

        while generated < args.target:
            example_id = f"v3-27b-{seq:04d}"
            cat = pick_category()

            try:
                prompt = build_prompt(cat, example_id)
                text = call_ollama(prompt)
                obj = extract_json(text)

                if obj is None:
                    log(f"SKIP {example_id} [{cat}] — JSON não encontrado na resposta", logf)
                    errors += 1
                    seq += 1
                    time.sleep(PAUSE_ERR)
                    continue

                ok, reason = validate(obj, example_id)
                if not ok:
                    log(f"SKIP {example_id} [{cat}] — validação: {reason}", logf)
                    errors += 1
                    retries += 1
                    # Não incrementa seq — tenta de novo com próxima categoria
                    time.sleep(PAUSE_ERR)
                    continue

                # Sucesso
                line = json.dumps(obj, ensure_ascii=False)
                outf.write(line + "\n")
                outf.flush()
                generated += 1
                seq += 1
                log(f"OK  {example_id} [{cat}] — total: {generated}/{args.target}", logf)
                time.sleep(PAUSE_OK)

            except requests.exceptions.Timeout:
                log(f"TIMEOUT {example_id} [{cat}] — aguardando {PAUSE_ERR}s", logf)
                errors += 1
                time.sleep(PAUSE_ERR)
            except Exception as e:
                log(f"ERRO {example_id} [{cat}] — {e}", logf)
                errors += 1
                time.sleep(PAUSE_ERR)

        log("=" * 60, logf)
        log(f"CONCLUÍDO — {generated} exemplos gerados | {errors} erros | {retries} retries", logf)
        log(f"Output: {output_path}", logf)


if __name__ == "__main__":
    main()
