# STATUS — agents-framework (vault-pilot)

## Componentes principais

- **Engine (Runtime)**:
  - `src/agentforge/runtime/engine.py` — Funções implementadas para benchmark:
    - `_summarize_scan_output`: Modos full, top_n, summary, by_folder, plain_text.
    - `_maybe_compress_tool_output`: Compressão automática via threshold de tokens.
    - `_build_input_with_file_content`: 7 modos de injeção de conteúdo (tags, position).
    - `_extract_filename_intent_fuzzy`: (V5) Path resolver experimental com SequenceMatcher e token overlap.
- **Agente**:
  - `agents/vault-pilot/`: Definição de system prompt e histórico base para reprodução.
- **Benchmarks (Scripts)**:
  - `run_v1_benchmark.py` (Compression)
  - `run_v2_benchmark.py` (Injection)
  - `run_v3_benchmark.py` (History Corruption)
  - `run_v4_benchmark_summary.py` (Loops)
  - `run_v5_path_benchmark.py` (Fuzzy Resolver)
- **Resultados**:
  - `results/benchmarks/V1/ ` ... `V5/` (Logs JSON de cada execução).

## Estado dos experimentos (no agents-framework)

- **V1**: [OK] Scripts e resultados consolidados. `_maybe_compress_tool_output` integrado como PoC.
- **V2**: [OK] Benchmark de injeção concluído. Identificado modo `current_tag` como ideal.
- **V3**: [OK] Teste de corrupção de histórico. `instruction_strong` validado como mitigação parcial.
- **V4**: [OK] Reprodução de loops. Confirmado que falha de path resolution é a causa raiz.
- **V5**: [OK] Benchmark de Path Resolver rodado em 2026-04-27. Resultados em `results/benchmarks/V5/`.

## Pendências técnicas

- [ ] **V5.1**: Melhorar `_extract_query_name` para lidar melhor com cases de "extraia X do arquivo Y".
- [ ] **V5.2**: Integrar o `_extract_filename_intent_fuzzy` no runtime oficial (hoje é experimental/apenas para benchmark).
- [ ] **Limpeza**: Padronizar o output dos benchmarks para facilitar a leitura no `llms-on-prem`.
- [ ] **Refatoração**: Mover funções experimentais de `engine.py` para um módulo de `utils` ou `research` para não poluir o engine estável.
