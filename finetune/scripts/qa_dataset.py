#!/usr/bin/env python3
"""
QA e homologação do dataset de fine-tuning do Cláudio.

Verifica conformidade com o padrão gold em todos os arquivos JSONL.
Gera relatório de qualidade e marcadores para revisão humana.

Uso:
    python3 qa_dataset.py                   # verifica todos os arquivos
    python3 qa_dataset.py --file synth.jsonl  # arquivo específico
    python3 qa_dataset.py --fix             # corrige problemas automáticos (system prompt)
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DATASET_DIR   = Path(__file__).parent.parent / "dataset"
SYSTEM_FILE   = Path(__file__).parent.parent / "system_prompt.txt"
CANONICAL_SYS = SYSTEM_FILE.read_text().strip()

# ---------------------------------------------------------------------------
# Regras de validação
# ---------------------------------------------------------------------------

MARKDOWN_PATTERN = re.compile(
    r"(?m)^#{1,6} "           # títulos markdown
    r"|^\*{1,2}\S"            # bullet * ou **bold
    r"|\*\*[^*]+\*\*"         # **bold**
    r"|(?<!\`)\*[^*\s][^*]*\*(?!\`)"  # *italic* (fora de crases)
    r"|^\\[(\[]"              # \( \[ escapado no início de linha
)

MIN_ASSISTANT_LEN = 10   # resposta muito curta suspeita
MAX_ASSISTANT_LEN = 3000  # resposta muito longa suspeita
MIN_TOOL_RESULT   = 20   # tool result muito curto = simulação ruim

REQUIRED_FIELDS = {"id", "category", "subcategory", "difficulty", "source", "messages"}
VALID_CATEGORIES = {"tool_calling", "chat", "refusal", "multi_turn", "agentic"}
VALID_SUBCATS = {
    "tool_calling": {"read_link", "run_bash", "multi_tool"},
    "chat":         {"persona", "mixed"},
    "refusal":      {"mixed", "no_hallucination", "destructive", "no_tool_invention",
                     "external_api"},
    "multi_turn":   {"read_link", "run_bash", "mixed"},
    "agentic":      {"mixed"},
}
VALID_DIFFICULTIES = {"easy", "medium", "hard"}


class Issue:
    def __init__(self, level: str, code: str, detail: str = ""):
        self.level  = level   # ERROR | WARN | INFO
        self.code   = code
        self.detail = detail

    def __str__(self):
        return f"[{self.level}] {self.code}" + (f": {self.detail}" if self.detail else "")


def validate_example(obj: dict) -> list[Issue]:
    issues = []

    # 1. Campos obrigatórios
    missing = REQUIRED_FIELDS - set(obj.keys())
    if missing:
        issues.append(Issue("ERROR", "MISSING_FIELDS", str(missing)))
        return issues  # inútil continuar sem os campos básicos

    # 2. Valores de categoria
    cat = obj.get("category", "")
    sub = obj.get("subcategory", "")
    dif = obj.get("difficulty", "")

    if cat not in VALID_CATEGORIES:
        issues.append(Issue("ERROR", "INVALID_CATEGORY", cat))
    if cat in VALID_SUBCATS and sub not in VALID_SUBCATS.get(cat, set()):
        issues.append(Issue("WARN", "UNEXPECTED_SUBCAT", f"{cat}/{sub}"))
    if dif not in VALID_DIFFICULTIES:
        issues.append(Issue("WARN", "INVALID_DIFFICULTY", dif))

    msgs = obj.get("messages", [])

    # 3. System prompt
    if not msgs or msgs[0].get("role") != "system":
        issues.append(Issue("ERROR", "NO_SYSTEM_PROMPT"))
    else:
        sys_content = msgs[0].get("content", "")
        if sys_content.strip() != CANONICAL_SYS:
            # Verifica se é apenas whitespace diferente
            if sys_content.strip()[:100] != CANONICAL_SYS[:100]:
                issues.append(Issue("ERROR", "WRONG_SYSTEM_PROMPT",
                                    f"início: {repr(sys_content[:60])}"))
            else:
                issues.append(Issue("WARN", "SYSTEM_PROMPT_WHITESPACE"))

    # 4. Estrutura mínima de mensagens
    if len(msgs) < 3:
        issues.append(Issue("ERROR", "TOO_FEW_MESSAGES", str(len(msgs))))
        return issues

    # 5. Tool_calling: tool_call + tool_result obrigatórios
    if cat == "tool_calling":
        has_tool_call   = any("tool_calls" in m and m.get("tool_calls") for m in msgs)
        has_tool_result = any(m.get("role") == "tool" for m in msgs)

        if not has_tool_call:
            issues.append(Issue("ERROR", "MISSING_TOOL_CALL"))
        if not has_tool_result:
            issues.append(Issue("ERROR", "MISSING_TOOL_RESULT"))

        # Verifica nome da tool e JSON dos arguments
        for m in msgs:
            tcs = m.get("tool_calls") or []
            for tc in tcs:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                if sub in ("read_link", "run_bash") and name != sub:
                    issues.append(Issue("ERROR", "WRONG_TOOL_NAME", f"esperado={sub} recebido={name}"))
                args_str = fn.get("arguments", "")
                try:
                    args = json.loads(args_str) if isinstance(args_str, str) else args_str
                    if not args:
                        issues.append(Issue("WARN", "EMPTY_TOOL_ARGS"))
                    elif name == "read_link" and "url" not in args:
                        issues.append(Issue("ERROR", "MISSING_URL_ARG"))
                    elif name == "run_bash" and "command" not in args:
                        issues.append(Issue("ERROR", "MISSING_COMMAND_ARG"))
                except json.JSONDecodeError:
                    issues.append(Issue("ERROR", "INVALID_TOOL_ARGS_JSON", args_str[:60]))

        # Tool result não pode ser muito curto
        for m in msgs:
            if m.get("role") == "tool":
                content = m.get("content", "")
                if len(content) < MIN_TOOL_RESULT:
                    issues.append(Issue("WARN", "SHORT_TOOL_RESULT", f"{len(content)} chars"))

    # 6. Chat/refusal: não deve ter tool calls
    if cat in ("chat", "refusal"):
        if any("tool_calls" in m for m in msgs):
            issues.append(Issue("WARN", "UNEXPECTED_TOOL_CALL_IN_CHAT"))

    # 7. Última mensagem deve ser do assistant
    last = msgs[-1]
    if last.get("role") != "assistant":
        issues.append(Issue("ERROR", "LAST_MSG_NOT_ASSISTANT", last.get("role", "?")))
    else:
        content = last.get("content") or ""
        if not content.strip():
            issues.append(Issue("ERROR", "EMPTY_ASSISTANT_RESPONSE"))
        elif len(content) < MIN_ASSISTANT_LEN:
            issues.append(Issue("WARN", "SHORT_RESPONSE", f"{len(content)} chars"))
        elif len(content) > MAX_ASSISTANT_LEN:
            issues.append(Issue("WARN", "LONG_RESPONSE", f"{len(content)} chars"))

        # Markdown na resposta final
        if MARKDOWN_PATTERN.search(content):
            m = MARKDOWN_PATTERN.search(content)
            issues.append(Issue("WARN", "MARKDOWN_IN_RESPONSE",
                                repr(content[m.start():m.start()+40])))

    return issues


# ---------------------------------------------------------------------------
# Fix automático: corrige system prompt
# ---------------------------------------------------------------------------

def fix_system_prompt(obj: dict) -> bool:
    msgs = obj.get("messages", [])
    if msgs and msgs[0].get("role") == "system":
        if msgs[0].get("content", "").strip() != CANONICAL_SYS:
            msgs[0]["content"] = CANONICAL_SYS
            return True
    return False


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def run_qa(files: list[Path], fix: bool = False) -> dict:
    stats = {
        "total": 0,
        "ok": 0,
        "warn_only": 0,
        "errors": 0,
        "by_category": defaultdict(lambda: {"total": 0, "ok": 0, "errors": 0}),
        "by_difficulty": defaultdict(lambda: {"total": 0, "ok": 0}),
        "issue_counts": defaultdict(int),
        "examples_with_issues": [],
    }

    for fpath in files:
        if not fpath.exists():
            print(f"[SKIP] {fpath.name} — não encontrado")
            continue

        lines = fpath.read_text().splitlines()
        fixed_lines = []
        changed = False

        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                stats["errors"] += 1
                stats["total"] += 1
                print(f"  [{fpath.name}:{i}] [ERROR] JSON_PARSE: {e}")
                fixed_lines.append(line)
                continue

            if fix:
                if fix_system_prompt(obj):
                    changed = True
                    line = json.dumps(obj, ensure_ascii=False)

            issues = validate_example(obj)
            stats["total"] += 1
            cat = obj.get("category", "unknown")
            sub = obj.get("subcategory", "")
            dif = obj.get("difficulty", "")
            key = f"{cat}/{sub}"

            stats["by_category"][key]["total"] += 1
            stats["by_difficulty"][dif]["total"] += 1

            errors = [x for x in issues if x.level == "ERROR"]
            warns  = [x for x in issues if x.level == "WARN"]

            for iss in issues:
                stats["issue_counts"][iss.code] += 1

            if errors:
                stats["errors"] += 1
                stats["by_category"][key]["errors"] += 1
                record = {
                    "id":     obj.get("id", f"{fpath.name}:{i}"),
                    "file":   fpath.name,
                    "issues": [str(x) for x in issues],
                }
                stats["examples_with_issues"].append(record)
            elif warns:
                stats["warn_only"] += 1
                stats["by_category"][key]["ok"] += 1
                stats["by_difficulty"][dif]["ok"] += 1
            else:
                stats["ok"] += 1
                stats["by_category"][key]["ok"] += 1
                stats["by_difficulty"][dif]["ok"] += 1

            fixed_lines.append(line)

        if fix and changed:
            fpath.write_text("\n".join(fixed_lines) + "\n")
            print(f"[FIX] {fpath.name} — system prompts corrigidos")

    return stats


def print_report(stats: dict):
    total  = stats["total"]
    ok     = stats["ok"]
    warns  = stats["warn_only"]
    errors = stats["errors"]

    print("\n" + "=" * 60)
    print("RELATÓRIO DE QA — DATASET CLÁUDIO")
    print("=" * 60)
    print(f"\nTotal de exemplos:  {total}")
    print(f"  OK (sem issues):  {ok}  ({100*ok//max(total,1)}%)")
    print(f"  Warnings only:    {warns}  ({100*warns//max(total,1)}%)")
    print(f"  Com erros:        {errors}  ({100*errors//max(total,1)}%)")

    print(f"\n--- Distribuição por categoria ---")
    for key in sorted(stats["by_category"]):
        d = stats["by_category"][key]
        print(f"  {key:35s}  total={d['total']:4d}  ok={d['ok']:4d}  erros={d['errors']}")

    print(f"\n--- Distribuição por dificuldade ---")
    for dif in ("easy", "medium", "hard"):
        d = stats["by_difficulty"].get(dif, {"total": 0, "ok": 0})
        print(f"  {dif:8s}  total={d['total']:4d}  ok={d['ok']:4d}")

    if stats["issue_counts"]:
        print(f"\n--- Issues mais frequentes ---")
        for code, count in sorted(stats["issue_counts"].items(), key=lambda x: -x[1])[:15]:
            print(f"  {code:35s}  {count:4d}×")

    if stats["examples_with_issues"]:
        print(f"\n--- Exemplos com erros (primeiros 10) ---")
        for rec in stats["examples_with_issues"][:10]:
            print(f"  {rec['id']} ({rec['file']})")
            for iss in rec["issues"]:
                print(f"    {iss}")

    verdict = "APROVADO" if errors == 0 else f"REPROVADO ({errors} erros)"
    print(f"\n{'='*60}")
    print(f"VEREDICTO: {verdict}")
    print("=" * 60)

    return errors == 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Arquivo JSONL específico (relativo ao dataset/)")
    parser.add_argument("--fix",  action="store_true", help="Corrige system prompts automaticamente")
    args = parser.parse_args()

    if args.file:
        files = [DATASET_DIR / args.file]
    else:
        files = sorted(DATASET_DIR.glob("*.jsonl"))

    if not files:
        print("Nenhum arquivo JSONL encontrado em", DATASET_DIR)
        sys.exit(1)

    print(f"Verificando {len(files)} arquivo(s):")
    for f in files:
        print(f"  {f.name} ({f.stat().st_size // 1024} KB)" if f.exists() else f"  {f.name} (não encontrado)")

    stats = run_qa(files, fix=args.fix)
    passed = print_report(stats)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
