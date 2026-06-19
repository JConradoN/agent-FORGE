#!/bin/bash
# Monta o dataset final V3 para treino do claudio-9b-v3
#
# Composição:
#   V2  agentforge   1620 ex  (synth_agentforge_v2 + batch1 + claude_batch9)
#   V1  tool synth    700 ex  (sample de synth_gemini* + synth.jsonl — diversidade de schemas)
#   V1  no-tool       400 ex  (sample de chat+refusal — previne catastrophic forgetting)
#   V1  gold human    100 ex  (gold_seed + gold_batch2 — alta qualidade + multi-turn)
#   V3  novos         300 ex  (synth_v3_overnight — gaps + generalização)
#   ─────────────────────────
#   TOTAL            ~3120 ex
#
# Uso: bash finetune/scripts/assemble_v3_dataset.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DATASET_DIR="$REPO_ROOT/finetune/dataset"
OUTPUT="$DATASET_DIR/train_v3_final.jsonl"

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "Montando dataset V3 final..."
log "Output: $OUTPUT"

# Limpa saída anterior
> "$OUTPUT"

# ── V2 AGENTFORGE (1620 ex) ─────────────────────────────────────────────────
log "Adicionando V2 agentforge..."
cat "$DATASET_DIR/synth_agentforge_v2.jsonl"    >> "$OUTPUT"
cat "$DATASET_DIR/synth_agentforge_batch1.jsonl" >> "$OUTPUT"
cat "$DATASET_DIR/synth_claude_batch9.jsonl"     >> "$OUTPUT"
V2_COUNT=$(wc -l < "$OUTPUT")
log "  V2: $V2_COUNT exemplos"

# ── V1 GOLD HUMAN (100 ex — todos) ──────────────────────────────────────────
log "Adicionando V1 gold human..."
cat "$DATASET_DIR/gold_seed.jsonl"   >> "$OUTPUT"
cat "$DATASET_DIR/gold_batch2.jsonl" >> "$OUTPUT"
GOLD_COUNT=$(( $(wc -l < "$OUTPUT") - V2_COUNT ))
log "  V1 gold: $GOLD_COUNT exemplos"

# ── V1 TOOL SYNTH — sample 700 (diversidade de schemas) ─────────────────────
log "Adicionando V1 tool synth (sample 700)..."
DATASET_DIR="$DATASET_DIR" python3 << PYEOF >> "$OUTPUT"
import json, random, pathlib, os

SEED = 42
TARGET = 700
dataset_dir = pathlib.Path(os.environ["DATASET_DIR"])

sources = [
    "synth_gemini.jsonl", "synth_gemini_batch2.jsonl", "synth_gemini_batch3.jsonl",
    "synth.jsonl",
    "synth_claude_batch1.jsonl", "synth_claude_batch2.jsonl", "synth_claude_batch3.jsonl",
    "synth_claude_batch4.jsonl", "synth_claude_batch5.jsonl", "synth_claude_batch6.jsonl",
    "synth_claude_batch7.jsonl", "synth_claude_batch8.jsonl",
]

pool = []
for fname in sources:
    p = dataset_dir / fname
    if not p.exists(): continue
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line: continue
        try:
            ex = json.loads(line)
            if any(m.get("tool_calls") for m in ex.get("messages", [])):
                pool.append(line)
        except: pass

random.seed(SEED)
sample = random.sample(pool, min(TARGET, len(pool)))
import sys; print(f"Pool V1 tool: {len(pool)} | Sample: {len(sample)}", file=sys.stderr)
for line in sample: print(line)
PYEOF

TOOL_COUNT=$(( $(wc -l < "$OUTPUT") - V2_COUNT - GOLD_COUNT ))
log "  V1 tool synth: $TOOL_COUNT exemplos"

# ── V1 NO-TOOL (chat+refusal) — sample 400 ───────────────────────────────────
log "Adicionando V1 no-tool — chat+refusal (sample 400)..."
BEFORE_NOTOOL=$(wc -l < "$OUTPUT")
DATASET_DIR="$DATASET_DIR" python3 << PYEOF >> "$OUTPUT"
import json, random, pathlib, os, sys

SEED = 43
TARGET = 400
dataset_dir = pathlib.Path(os.environ["DATASET_DIR"])

# Fontes com exemplos no-tool (chat, refusal)
sources = [
    "synth_gemini.jsonl", "synth_gemini_batch2.jsonl", "synth_gemini_batch3.jsonl",
    "synth.jsonl",
    "synth_claude_batch1.jsonl", "synth_claude_batch2.jsonl", "synth_claude_batch3.jsonl",
    "synth_claude_batch4.jsonl", "synth_claude_batch5.jsonl",
    "synth_claude_batch8.jsonl",
]

pool = []
for fname in sources:
    p = dataset_dir / fname
    if not p.exists(): continue
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line: continue
        try:
            ex = json.loads(line)
            # Inclui exemplos SEM tool_calls (conversacional, refusal)
            has_tool = any(m.get("tool_calls") for m in ex.get("messages", []))
            if not has_tool:
                pool.append(line)
        except: pass

random.seed(SEED)
sample = random.sample(pool, min(TARGET, len(pool)))
print(f"Pool V1 no-tool: {len(pool)} | Sample: {len(sample)}", file=sys.stderr)
for line in sample: print(line)
PYEOF

NOTOOL_COUNT=$(( $(wc -l < "$OUTPUT") - BEFORE_NOTOOL ))
log "  V1 no-tool: $NOTOOL_COUNT exemplos"

# ── V3 NOVOS — Agy overnight ────────────────────────────────────────────────
V3_FILE="$DATASET_DIR/synth_v3_overnight.jsonl"
if [ -f "$V3_FILE" ] && [ -s "$V3_FILE" ]; then
    log "Adicionando V3 Agy overnight..."
    BEFORE_V3=$(wc -l < "$OUTPUT")
    cat "$V3_FILE" >> "$OUTPUT"
    V3_AGY_COUNT=$(( $(wc -l < "$OUTPUT") - BEFORE_V3 ))
    log "  V3 Agy: $V3_AGY_COUNT exemplos"
else
    log "  AVISO: $V3_FILE não encontrado — gere com gen_v3_overnight.sh"
    V3_AGY_COUNT=0
fi

# ── V3 NOVOS — qwen3.5:27b local ────────────────────────────────────────────
V3_27B_FILE="$DATASET_DIR/synth_v3_27b.jsonl"
if [ -f "$V3_27B_FILE" ] && [ -s "$V3_27B_FILE" ]; then
    log "Adicionando V3 qwen3.5:27b..."
    BEFORE_27B=$(wc -l < "$OUTPUT")
    cat "$V3_27B_FILE" >> "$OUTPUT"
    V3_27B_COUNT=$(( $(wc -l < "$OUTPUT") - BEFORE_27B ))
    log "  V3 27b: $V3_27B_COUNT exemplos"
else
    log "  INFO: $V3_27B_FILE não encontrado — pular ou gere com gen_v3_27b.py"
    V3_27B_COUNT=0
fi

# ── SHUFFLE e RELATÓRIO ──────────────────────────────────────────────────────
log "Embaralhando dataset final..."
FINAL_BEFORE=$(wc -l < "$OUTPUT")
DATASET_DIR="$DATASET_DIR" python3 << PYEOF
import random, pathlib, os

output = pathlib.Path(os.environ["DATASET_DIR"]) / "train_v3_final.jsonl"
lines = [l for l in output.read_text().splitlines() if l.strip()]
random.seed(99)
random.shuffle(lines)
output.write_text("\n".join(lines) + "\n")
print(f"Shuffled: {len(lines)} linhas")
PYEOF

FINAL=$(wc -l < "$OUTPUT")
log ""
log "════════════════════════════════════════"
log "Dataset V3 montado: $OUTPUT"
log "Total: $FINAL exemplos"
log ""
log "Composição:"
log "  V2 agentforge : $V2_COUNT"
log "  V1 gold human : $GOLD_COUNT"
log "  V1 tool synth : $TOOL_COUNT"
log "  V1 no-tool    : $NOTOOL_COUNT"
log "  V3 Agy        : ${V3_AGY_COUNT:-0}"
log "  V3 27b        : ${V3_27B_COUNT:-0}"
log "════════════════════════════════════════"
log ""
log "Próximo passo:"
log "  source finetune/.venv/bin/activate"
log "  python3 finetune/scripts/train_v3.py"
