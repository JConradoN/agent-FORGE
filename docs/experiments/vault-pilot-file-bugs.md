# Experimentos Vault-Pilot: Bugs de Listagem e Análise de Arquivos

## Contexto
- **Agente**: `vault-pilot`
- **Modelo**: `gemma4:e4b` via Ollama local
- **Objetivo**: Investigar bugs de listagem de arquivos e análise de documentos, especificamente falhas no path resolver e alucinações em históricos longos.

## V1 — Tool Output Compression Benchmark
- **Problema**: `scan_directory` retornando muitos arquivos (ex: 342 arquivos, ~25k tokens) causava saturação de contexto, levando o modelo a ignorar o output real e inventar arquivos.
- **Solução Implementada**:
  - `_summarize_scan_output`: Suporta modos `full`, `top_n`, `summary`, `by_folder`, `plain_text`.
  - `_maybe_compress_tool_output`: Aplica compressão baseada em `_TOKEN_THRESHOLD ≈ 800`.
  - `_build_input_with_tool_results_with_name`: Garante que o nome da tool seja injetado no prompt final.
- **Resultados**:
  - N=5 → `faithfulness ≈ 1.0`
  - N=20 → `faithfulness ≈ 0.0` (sem compressão)
  - N=342 (com summary) → `faithfulness ≈ 1.0`

## V2 — Document Content Injection Benchmark
- **Foco**: Testar diferentes formatos de injeção de `<file_content>` (tags, posição, força das instruções).
- **Resultados**:
  - Em single-turn limpo (histórico vazio), o modelo usa o conteúdo do contrato corretamente em quase todos os modos.
  - Modos `current_tag` e `instruction_strong` atingiram `faithfulness ≈ 1.0`.
  - Nenhum modo produziu `tool_call_attempt = True` erroneamente.

## V3 — History Corruption Benchmark
- **Foco**: Impacto de históricos sintéticos "sujos" (`assistant: ""` e scans falsos).
- **Cenários**: `clean`, `dirty1`, `dirty2`, `dirty3`.
- **Descobertas**:
  - Histórico sujo reduz a fidelidade (perda de detalhes como CNPJ/cidade).
  - `clean_history` ingênuo (remover assistant vazios + truncar) mostrou-se instável.
  - `instruction_strong` é mais robusto, mas não reproduziu o bug específico de `<tool_call>` alucinado.

## Análise de `agents/vault-pilot/history.json`
- **Formato**: Lista de dicionários `{"role": str, "content": str}`.
- **Observação**: Tool outputs (`<tool_results>`, `<file_content>`) existem apenas no prompt `final_input`, não são persistidos no histórico.
- **Bug Observado**: System summary contendo lista de arquivos fabricados, gerando loops de "arquivo não encontrado".

## V4 — Summary + Loops Benchmark
- **Cenários**: `summary_only` e `summary_loops`, com e sem truncamento simples.
- **Resultados**:
  - `faithfulness` entre 0.25–0.50 (devido a limitações de OCR/ground truth).
  - `bug_reproduced = False` em todas as configurações; o modelo consegue ler o contrato se o `<file_content>` estiver presente, mesmo com summary alucinado.

## Conclusão Global
- **Bug A (Confirmado)**:
  - **Causa Raiz**: `_extract_filename_intent` falha ao resolver o path solicitado.
  - **Consequência**: `extract_file_content` falha → `<file_content>` não chega ao modelo → respostas "arquivo não encontrado" e summary alucinado.
- **Bug B (Observado)**:
  - Alucinações de `<tool_call>` e empresas fictícias parecem depender de turns vazios, presença de conteúdo real e histórico longo simultaneamente.
- **Próximos Passos**: V5 focará no benchmark e correção do path resolver.

---
**Scripts Relacionados**:
- `scripts/run_v1_benchmark.py`
- `scripts/run_v2_benchmark.py`
- `scripts/run_v3_benchmark.py`
- `scripts/run_v4_benchmark_summary.py`
