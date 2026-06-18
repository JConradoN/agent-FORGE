#!/usr/bin/env python3
"""
Fine-tuning do qwen3.5:9b para o Cláudio usando QLoRA + Unsloth.

Uso:
    # Dataset gerado (gold + sintético):
    python3 train.py

    # Só gold (50 exemplos, útil para smoke test):
    python3 train.py --dataset-only gold

    # Smoke test: 5 steps, sem salvar:
    python3 train.py --smoke-test
"""

import argparse
import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE_MODEL    = "Qwen/Qwen3.5-9B"   # instruct (sem -Base), quantizado on-the-fly
OUTPUT_DIR    = Path(__file__).parent.parent / "output"
DATASET_DIR   = Path(__file__).parent.parent / "dataset"
LOG_DIR       = Path(__file__).parent.parent / "logs"

LORA_R        = 32          # rank — maior = mais expressivo, mais VRAM
LORA_ALPHA    = 64          # alpha = 2×r é boa prática
LORA_DROPOUT  = 0.05
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
]

MAX_SEQ_LEN   = 4096        # cobertura confortável para exemplos multi-turn
BATCH_SIZE    = 2           # por GPU; gradient_accumulation compensa
GRAD_ACCUM    = 8           # batch efetivo = 2×8 = 16
EPOCHS        = 3
LR            = 2e-4
WARMUP_RATIO  = 0.05
LR_SCHEDULER  = "cosine"
WEIGHT_DECAY  = 0.01

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

def load_dataset_files(mode: str) -> list[dict]:
    if mode == "gold":
        files = [DATASET_DIR / "gold_seed.jsonl", DATASET_DIR / "gold_batch2.jsonl"]
    elif mode == "synth":
        files = [f for f in sorted(DATASET_DIR.glob("synth*.jsonl"))]
    else:  # all
        files = sorted(DATASET_DIR.glob("*.jsonl"))

    skipped = 0
    examples = []
    for fpath in files:
        if not fpath.exists():
            print(f"[WARN] Dataset não encontrado: {fpath}")
            continue
        for line in fpath.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            # Valida args de tool_calls — pula se JSON inválido dentro do arguments
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

    if skipped:
        print(f"[dataset] {skipped} exemplos pulados (JSON inválido ou args malformados)")
    print(f"[dataset] {len(examples)} exemplos carregados (modo={mode})")
    return examples


def format_for_training(examples: list[dict], tokenizer) -> list[str]:
    """Converte exemplos JSONL para o formato de chat do tokenizer."""
    texts = []
    for ex in examples:
        msgs = ex.get("messages", [])
        if not msgs:
            continue
        try:
            # Qwen chat_template espera arguments como dict, não JSON string
            normalized = []
            for m in msgs:
                m = dict(m)
                if m.get("tool_calls"):
                    tcs = []
                    for tc in m["tool_calls"]:
                        tc = dict(tc)
                        fn = dict(tc.get("function", {}))
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
            print(f"[WARN] Erro no exemplo {ex.get('id', '?')}: {e}")
    print(f"[dataset] {len(texts)} exemplos formatados com chat_template")
    return texts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-only", default="all",
                        choices=["all", "gold", "synth"],
                        help="Qual arquivo de dataset usar")
    parser.add_argument("--smoke-test", action="store_true",
                        help="5 steps rápidos para verificar que o pipeline funciona")
    parser.add_argument("--output-name", default="claudio-9b-v1",
                        help="Nome do diretório de saída")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = OUTPUT_DIR / args.output_name

    # Imports pesados só quando realmente rodar
    from unsloth import FastLanguageModel
    from unsloth import is_bfloat16_supported
    from trl import SFTTrainer, SFTConfig
    from datasets import Dataset
    import torch

    print(f"[setup] CUDA: {torch.cuda.is_available()} | GPUs: {torch.cuda.device_count()}")
    print(f"[setup] bfloat16: {is_bfloat16_supported()}")
    print(f"[setup] Carregando {BASE_MODEL}...")

    # -------------------------------------------------------------------------
    # Carrega modelo com QLoRA 4-bit
    # -------------------------------------------------------------------------
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name    = BASE_MODEL,
        max_seq_length= MAX_SEQ_LEN,
        dtype         = None,       # auto: bf16 se suportado
        load_in_4bit  = True,
        # device_map="auto" distribui nas duas GPUs
    )

    print("[setup] Aplicando LoRA...")
    model = FastLanguageModel.get_peft_model(
        model,
        r                  = LORA_R,
        lora_alpha         = LORA_ALPHA,
        target_modules     = TARGET_MODULES,
        lora_dropout       = LORA_DROPOUT,
        bias               = "none",
        use_gradient_checkpointing = "unsloth",  # economia de VRAM
        random_state       = 42,
    )

    # Resumo de parâmetros treináveis
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total     = sum(p.numel() for p in model.parameters())
    print(f"[lora] Parâmetros treináveis: {trainable:,} / {total:,} ({100*trainable/total:.2f}%)")

    # -------------------------------------------------------------------------
    # Dataset
    # -------------------------------------------------------------------------
    examples = load_dataset_files(args.dataset_only)
    if args.smoke_test:
        examples = examples[:20]
        print("[smoke] Limitando a 20 exemplos")

    texts = format_for_training(examples, tokenizer)
    if not texts:
        print("[ERROR] Nenhum exemplo válido. Abortando.")
        return

    ds = Dataset.from_dict({"text": texts})
    print(f"[dataset] Dataset final: {len(ds)} exemplos")

    # -------------------------------------------------------------------------
    # Treinamento
    # -------------------------------------------------------------------------
    max_steps = 5 if args.smoke_test else -1  # -1 = usa num_train_epochs

    trainer = SFTTrainer(
        model     = model,
        tokenizer = tokenizer,
        train_dataset = ds,
        args = SFTConfig(
            output_dir               = str(run_dir),
            num_train_epochs         = EPOCHS if not args.smoke_test else 1,
            max_steps                = max_steps,
            per_device_train_batch_size = BATCH_SIZE,
            gradient_accumulation_steps = GRAD_ACCUM,
            warmup_ratio             = WARMUP_RATIO,
            learning_rate            = LR,
            lr_scheduler_type        = LR_SCHEDULER,
            weight_decay             = WEIGHT_DECAY,
            bf16                     = is_bfloat16_supported(),
            fp16                     = not is_bfloat16_supported(),
            logging_steps            = 10,
            save_strategy            = "epoch",
            save_total_limit         = 2,
            dataset_text_field       = "text",
            max_seq_length           = MAX_SEQ_LEN,
            packing                  = True,   # concatena exemplos curtos — +throughput
            report_to                = "none",  # sem wandb
            seed                     = 42,
        ),
    )

    print("[train] Iniciando treino...")
    trainer_stats = trainer.train()

    if not args.smoke_test:
        print(f"[train] Salvando LoRA adapter em {run_dir}...")
        model.save_pretrained(str(run_dir))
        tokenizer.save_pretrained(str(run_dir))

        # Exporta para GGUF (Q4_K_M — melhor qualidade para Ollama)
        gguf_dir = run_dir / "gguf"
        gguf_dir.mkdir(exist_ok=True)
        print(f"[export] Exportando GGUF Q4_K_M para {gguf_dir}...")
        model.save_pretrained_gguf(
            str(gguf_dir / "claudio-9b"),
            tokenizer,
            quantization_method = "q4_k_m",
        )
        print(f"[export] GGUF salvo.")

    print("\n=== Treino concluído ===")
    print(f"  Loss final: {trainer_stats.training_loss:.4f}")
    print(f"  Tempo: {trainer_stats.metrics.get('train_runtime', 0)/60:.1f} min")
    if not args.smoke_test:
        print(f"  LoRA adapter: {run_dir}")
        gguf_path = list((run_dir / "gguf").glob("*.gguf"))
        if gguf_path:
            print(f"  GGUF: {gguf_path[0]}")
            print(f"\nPara testar no Ollama:")
            print(f"  ollama create claudio-9b -f {run_dir}/gguf/Modelfile")


if __name__ == "__main__":
    main()
