#!/usr/bin/env python3
"""
Fine-tuning v2 do qwen3.5:9b — dataset 100% agentic (AgentForge).

Root cause do v1: 94% conversacional + 6% agêntico → gradiente conversacional
dominou, sem melhora real em tool chains / must compliance / completion signals.

V2 usa APENAS exemplos agênticos:
  - synth_agentforge_v2.jsonl     (1440 ex — gerado Agy, 11 categorias)
  - synth_agentforge_batch1.jsonl ( 120 ex — gerado Agy, batch inicial)
  - synth_claude_batch9.jsonl     (  60 ex — compliance / falsa_conclusao)
  Total: ~1620 exemplos

Arquivos excluídos intencionalmente:
  - gold_seed / gold_batch2      → Cláudio conversacional
  - synth_claude_batch1-8        → Cláudio conversacional
  - synth_gemini / synth_gemini* → Cláudio conversacional
  - synth.jsonl                  → conversacional misto

Uso:
    # Treino completo:
    python3 train_v2.py

    # Smoke test (20 exemplos, 5 steps):
    python3 train_v2.py --smoke-test

    # Escolher nome de saída:
    python3 train_v2.py --output-name claudio-9b-agentforge
"""

import argparse
import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_MODEL  = "Qwen/Qwen3.5-9B"   # base, sem fine-tune anterior (não continuar do v1)
OUTPUT_DIR  = Path(__file__).parent.parent / "output"
DATASET_DIR = Path(__file__).parent.parent / "dataset"
LOG_DIR     = Path(__file__).parent.parent / "logs"

# Dataset V2 — lista explícita, sem glob (evita incluir arquivos conversacionais)
V2_DATASET_FILES = [
    "synth_agentforge_v2.jsonl",      # 1440 ex — agentic, 11 categorias
    "synth_agentforge_batch1.jsonl",  #  120 ex — agentic, batch inicial
    "synth_claude_batch9.jsonl",      #   60 ex — compliance / falsa_conclusao
]

LORA_R       = 32
LORA_ALPHA   = 64          # alpha = 2×r
LORA_DROPOUT = 0.05
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

MAX_SEQ_LEN  = 4096
BATCH_SIZE   = 2           # por GPU
GRAD_ACCUM   = 8           # batch efetivo = 16
EPOCHS       = 4           # +1 epoch vs v1 — dataset menor, mais focado
LR           = 2e-4
WARMUP_RATIO = 0.05
LR_SCHEDULER = "cosine"
WEIGHT_DECAY = 0.01


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def load_dataset_files(files: list[str]) -> list[dict]:
    skipped = 0
    examples = []

    for fname in files:
        fpath = DATASET_DIR / fname
        if not fpath.exists():
            print(f"[WARN] Arquivo não encontrado: {fpath}")
            continue

        file_count = 0
        for line in fpath.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            # Valida arguments de tool_calls — pula se JSON inválido
            valid = True
            for msg in obj.get("messages", []):
                for tc in msg.get("tool_calls") or []:
                    args = tc.get("function", {}).get("arguments", "")
                    if isinstance(args, str):
                        try:
                            json.loads(args)
                        except json.JSONDecodeError:
                            valid = False
                            break
                if not valid:
                    break

            if not valid:
                skipped += 1
                continue

            examples.append(obj)
            file_count += 1

        print(f"[dataset] {fname}: {file_count} exemplos")

    if skipped:
        print(f"[dataset] {skipped} exemplos pulados (JSON inválido / args malformados)")

    print(f"[dataset] Total carregado: {len(examples)} exemplos")
    return examples


def format_for_training(examples: list[dict], tokenizer) -> list[str]:
    """Converte exemplos JSONL para o formato de chat do tokenizer."""
    texts = []
    skipped = 0

    for ex in examples:
        msgs = ex.get("messages", [])
        if not msgs:
            continue
        try:
            normalized = []
            for m in msgs:
                m = dict(m)
                if m.get("tool_calls"):
                    tcs = []
                    for tc in m["tool_calls"]:
                        tc = dict(tc)
                        fn = dict(tc.get("function", {}))
                        # Qwen chat_template espera arguments como dict, não string JSON
                        if isinstance(fn.get("arguments"), str):
                            fn["arguments"] = json.loads(fn["arguments"])
                        tc["function"] = fn
                        tcs.append(tc)
                    m["tool_calls"] = tcs
                normalized.append(m)

            text = tokenizer.apply_chat_template(
                normalized,
                tokenize=False,
                add_generation_prompt=False,
            )
            texts.append(text)
        except Exception as e:
            print(f"[WARN] Exemplo {ex.get('id', '?')} ignorado: {e}")
            skipped += 1

    print(f"[dataset] {len(texts)} exemplos formatados ({skipped} ignorados)")
    return texts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true",
                        help="20 exemplos, 5 steps — verifica que o pipeline funciona")
    parser.add_argument("--output-name", default="claudio-9b-v2",
                        help="Nome do diretório de saída (dentro de finetune/output/)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = OUTPUT_DIR / args.output_name

    print("=" * 60)
    print("Fine-tuning Cláudio 9b v2 — dataset 100% agentic")
    print("=" * 60)
    print(f"Base model  : {BASE_MODEL}")
    print(f"Output dir  : {run_dir}")
    print(f"LoRA r/α    : {LORA_R}/{LORA_ALPHA}")
    print(f"Batch efetivo: {BATCH_SIZE * GRAD_ACCUM}")
    print(f"Epochs      : {EPOCHS}")
    print(f"Max seq len : {MAX_SEQ_LEN}")
    print()

    from unsloth import FastLanguageModel
    from unsloth import is_bfloat16_supported
    from trl import SFTTrainer, SFTConfig
    from datasets import Dataset
    import torch

    print(f"[setup] CUDA: {torch.cuda.is_available()} | GPUs: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        name = torch.cuda.get_device_name(i)
        mem  = torch.cuda.get_device_properties(i).total_memory // (1024**3)
        print(f"[setup] GPU{i}: {name} ({mem} GB)")
    print(f"[setup] bfloat16: {is_bfloat16_supported()}")
    print(f"[setup] Carregando {BASE_MODEL}...")

    # -------------------------------------------------------------------------
    # Carrega modelo base com QLoRA 4-bit
    # -------------------------------------------------------------------------
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name    = BASE_MODEL,
        max_seq_length= MAX_SEQ_LEN,
        dtype         = None,
        load_in_4bit  = True,
    )

    print("[setup] Aplicando LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r                          = LORA_R,
        lora_alpha                 = LORA_ALPHA,
        target_modules             = TARGET_MODULES,
        lora_dropout               = LORA_DROPOUT,
        bias                       = "none",
        use_gradient_checkpointing = "unsloth",
        random_state               = 42,
    )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"[lora] Parâmetros treináveis: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # -------------------------------------------------------------------------
    # Dataset
    # -------------------------------------------------------------------------
    examples = load_dataset_files(V2_DATASET_FILES)

    if not examples:
        print("[ERROR] Nenhum exemplo carregado. Verifique os arquivos de dataset.")
        return

    if args.smoke_test:
        examples = examples[:20]
        print(f"[smoke] Limitando a {len(examples)} exemplos")

    texts = format_for_training(examples, tokenizer)
    if not texts:
        print("[ERROR] Nenhum exemplo válido após formatação. Abortando.")
        return

    ds = Dataset.from_dict({"text": texts})
    print(f"[dataset] Dataset final: {len(ds)} exemplos")

    # -------------------------------------------------------------------------
    # Treinamento
    # -------------------------------------------------------------------------
    max_steps    = 5  if args.smoke_test else -1
    num_epochs   = 1  if args.smoke_test else EPOCHS
    save_strategy= "no" if args.smoke_test else "epoch"

    steps_per_epoch = max(1, len(ds) // (BATCH_SIZE * GRAD_ACCUM))
    total_steps     = steps_per_epoch * num_epochs
    print(f"[train] Estimativa: {steps_per_epoch} steps/epoch × {num_epochs} epochs = ~{total_steps} steps")

    trainer = SFTTrainer(
        model         = model,
        tokenizer     = tokenizer,
        train_dataset = ds,
        args = SFTConfig(
            output_dir                  = str(run_dir),
            num_train_epochs            = num_epochs,
            max_steps                   = max_steps,
            per_device_train_batch_size = BATCH_SIZE,
            gradient_accumulation_steps = GRAD_ACCUM,
            warmup_ratio                = WARMUP_RATIO,
            learning_rate               = LR,
            lr_scheduler_type           = LR_SCHEDULER,
            weight_decay                = WEIGHT_DECAY,
            bf16                        = is_bfloat16_supported(),
            fp16                        = not is_bfloat16_supported(),
            logging_steps               = 10,
            save_strategy               = save_strategy,
            save_total_limit            = 2,
            dataset_text_field          = "text",
            max_seq_length              = MAX_SEQ_LEN,
            packing                     = True,
            report_to                   = "none",
            seed                        = 42,
        ),
    )

    print("[train] Iniciando treino...")
    trainer_stats = trainer.train()

    # -------------------------------------------------------------------------
    # Salvar e exportar
    # -------------------------------------------------------------------------
    if not args.smoke_test:
        print(f"[save] Salvando LoRA adapter em {run_dir}...")
        model.save_pretrained(str(run_dir))
        tokenizer.save_pretrained(str(run_dir))

        gguf_dir = run_dir / "gguf"
        gguf_dir.mkdir(exist_ok=True)
        print(f"[export] Exportando GGUF Q4_K_M para {gguf_dir}...")
        model.save_pretrained_gguf(
            str(gguf_dir / args.output_name),
            tokenizer,
            quantization_method="q4_k_m",
        )

    print()
    print("=" * 60)
    print("Treino concluído")
    print("=" * 60)
    print(f"  Loss final : {trainer_stats.training_loss:.4f}")
    print(f"  Tempo      : {trainer_stats.metrics.get('train_runtime', 0) / 60:.1f} min")

    if not args.smoke_test:
        print(f"  LoRA       : {run_dir}")
        gguf_files = list((run_dir / "gguf").glob("*.gguf"))
        if gguf_files:
            print(f"  GGUF       : {gguf_files[0]}")
            print()
            print("Para registrar no Ollama:")
            print(f"  ollama create {args.output_name} -f {run_dir}/gguf/Modelfile")


if __name__ == "__main__":
    main()
