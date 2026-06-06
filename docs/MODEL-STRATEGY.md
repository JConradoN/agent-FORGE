# Estratégia de Modelos — AgentForge

## Decisão

O AgentForge foi **otimizado empiricamente para a família qwen3.5** (Qwen 3.5 da Alibaba), com base em 4 meses de benchmarks sistemáticos cobrindo 19 modelos locais distintos.

O framework **funciona com qualquer modelo disponível via Ollama**, mas os defaults, os parâmetros de runtime e os cenários de avaliação foram calibrados para qwen3.5:9b e qwen3.5:27b.

---

## Evidência

Os benchmarks que embasam essa decisão, em ordem cronológica:

| Framework | Escopo | Resultado qwen3.5 |
|---|---|---|
| **ABS** (Agent Benchmark Suite) | 23 cenários, escala 0-4, 19 modelos | qwen3.5:27b campeão geral |
| **LOP** (Local Ops) | Tool use operacional com fixtures reais | qwen3.5:27b e 9b no top-4 |
| **FORGE** | Tarefas reais encadeadas (web, câmbio, análise) | F3: 94.4% com 27b |
| **REAL** | Browser, coding, skill gen | P4: 91.7%, F3: 94.4% com 27b |

**Tese validada:** dentro de famílias bem treinadas, escala entrega qualidade. A família qwen3.5 demonstrou consistência superior em instruction-following, coerência entre múltiplos tool calls e fidelidade a guardrails explícitos.

---

## Política de Seleção por Complexidade

```
qwen3.5:9b  (~7 GB VRAM, ~45 tok/s no fox-server)
└── Tarefas simples e intermediárias:
    - Monitoramento e diagnóstico (fox-health, lab-ops)
    - Orquestração de subtarefas com contexto curto
    - Consultas diretas sem multi-step tool use
    - Classificação e triagem

qwen3.5:27b  (~17 GB VRAM, ~25 tok/s no fox-server)
└── Tarefas complexas:
    - Coding com testes reais (REAL P3)
    - Geração de documentação técnica completa (REAL P4)
    - Análise multi-step com APIs externas (FORGE F3)
    - Orquestração com múltiplos agentes subordinados
    - Qualquer tarefa com coerência exigida entre 3+ tool calls
```

**Critério prático:** se o agente precisa manter coerência de nomes, tipos ou contratos entre múltiplas chamadas `write_file` ou `run_bash` separadas, use 27b. O 9b tende a introduzir inconsistências sutis (diferença de casing em mensagens de erro, nomes de função com variação de prefixo).

---

## Parâmetro `think: False`

O Ollama suporta o parâmetro `think` para modelos da família Qwen3, que ativa raciocínio interno extendido. Por padrão, quando não especificado, modelos Qwen3 ativam o thinking mode e podem retornar `message.content` vazio durante o tool calling loop — o que causa erro no provider.

O AgentForge desativa explicitamente o thinking mode em chamadas de chat:

```python
# src/agentforge/providers/ollama.py
payload = {
    "model": request.model,
    "messages": messages,
    "stream": False,
    "think": False,  # evita message.content vazio durante tool calling
}
```

Isso garante comportamento determinístico durante o loop de tool calling. Para outros modelos que não suportam `think`, o parâmetro é simplesmente ignorado pelo Ollama.

---

## Usando Outros Modelos

O framework roda com qualquer modelo suportado pelo Ollama. Para trocar o modelo de um agente:

```yaml
# agents/<id>/agent.yaml
model_policy:
  default_model: llama3.3:70b   # ou qualquer modelo disponível
  fallback_model: qwen3.5:9b    # usado se o principal falhar
```

Ou via variável de ambiente no script de benchmark:

```bash
python3 scripts/run_benchmark_eval.py --scenarios P3 --model llama3.3:70b
```

**Nota sobre comparabilidade:** os auto_checks e os critérios de avaliação dos cenários FORGE e REAL foram desenhados para serem model-agnostic (verificam arquivos, sintaxe Python, resultados de pytest — não dependem de vocabulário específico de nenhum modelo). Os resultados são comparáveis entre modelos.

---

## Referência de Resultados (qwen3.5 — junho/2026)

| Cenário | Dimensão | 9b | 27b |
|---|---|---|---|
| FORGE F3 | Análise de mercado (câmbio + relatório + Claudio) | 94.4% | 94.4% |
| REAL P3 | Python tool com testes reais | 66.7% | 66.7%* |
| REAL P4 | Geração de skill Claude | 91.7% | 91.7% |

*O 27b passa 7/8 testes (vs 0/8 do 9b), mas ambos perdem os 4 pontos do `python_tests_pass` porque 1 teste falha por incoerência de casing em mensagem de ValueError gerada entre dois `write_file` separados. O 27b é superior em qualidade interna mesmo com score idêntico.

**Recomendação:** use 27b como padrão para agentes de produção sempre que a VRAM permitir (≥17 GB disponíveis).
