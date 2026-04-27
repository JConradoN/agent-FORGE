# Scripts de Benchmark e Utilitários

Este diretório contém scripts para benchmarking e testes de eficácia do framework AgentForge, com foco nos experimentos realizados para o agente `vault-pilot`.

## Scripts de Benchmark

### 1. `run_v1_benchmark.py`
- **Propósito**: Testar o impacto da compressão de output da ferramenta `scan_directory` (V1).
- **Funcionalidade**: Simula diferentes volumes de arquivos (5 a 342) e modos de compressão (`full`, `summary`, `top_n`, etc.) para verificar se o modelo mantém a fidelidade na listagem.
- **Resultados**: `results/benchmarks/V1/`

### 2. `run_v2_benchmark.py`
- **Propósito**: Testar modos de injeção de conteúdo de arquivo (`file_text`) em single-turn (V2).
- **Funcionalidade**: Avalia como diferentes tags e instruções (`current_tag`, `instruction_strong`, etc.) afetam a capacidade do modelo de extrair dados de um contrato.
- **Resultados**: `results/benchmarks/V2/`

### 3. `run_v3_benchmark.py`
- **Propósito**: Avaliar o impacto de históricos de conversa corrompidos ou "sujos" (V3).
- **Funcionalidade**: Injeta mensagens de assistente vazias e resultados de scan falsos para medir a degradação da fidelidade e a tendência a alucinações.
- **Resultados**: `results/benchmarks/V3/`

### 4. `run_v4_benchmark_summary.py`
- **Propósito**: Testar o impacto de `system summary` alucinado e loops de erro (V4).
- **Funcionalidade**: Simula cenários onde o resumo do sistema contém informações falsas e a conversa entra em loops de erro de "arquivo não encontrado", verificando se o modelo consegue se recuperar ao receber o conteúdo correto do arquivo.
- **Resultados**: `results/benchmarks/V4/`

## Scripts de Inicialização (Bootstrap)

- `bootstrap_vault_pilot.sh`: Configura o ambiente inicial para o agente `vault-pilot`.
- `bootstrap_vault_pilot_tools.sh`: Prepara as ferramentas específicas do `vault-pilot`.

## Como Executar

A maioria dos scripts de benchmark pode ser executada diretamente via Python (com o ambiente virtual ativado):

```bash
python scripts/run_v2_benchmark.py
```

*Nota: Certifique-se de que o Ollama está rodando localmente com o modelo configurado (ex: gemma4:e4b).*
