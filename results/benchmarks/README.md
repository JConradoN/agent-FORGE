# Resultados de Benchmarks

Este diretório armazena os resultados (artefatos JSON) dos experimentos de eficácia conduzidos no framework AgentForge.

## Estrutura de Diretórios

- `V1/`: Impacto da compressão de output da ferramenta `scan_directory`.
- `V2/`: Formatos de injeção de conteúdo de documento (`file_content`).
- `V3/`: Corrupção de histórico (turns vazios e scans falsos).
- `V4/`: Resumo de sistema alucinado e loops de erro.

## Formato dos Arquivos

Cada execução gera um arquivo JSON nomeado como `VX-label-TIMESTAMP.json` e um arquivo consolidado `VX-summary-TIMESTAMP.json`.

### Campos Principais nos JSONs:

- `label`: Identificador do cenário testado.
- `faithfulness_score`: Pontuação de 0.0 a 1.0 indicando o quão fiel a resposta foi aos dados reais.
- `fact_hits`: Número de fatos corretos extraídos (para V2, V3, V4).
- `tool_call_attempt` / `tool_call_markup`: Booleano indicando se o modelo tentou chamar uma ferramenta indevidamente.
- `hallucination_detected`: Booleano indicando presença de dados conhecidamente inventados (ex: "Tech Soluções Alpha").
- `bug_reproduced`: (Apenas V4) Booleano indicando se o comportamento problemático foi observado.

## Uso dos Resultados

Estes arquivos servem como base para a tomada de decisão arquitetural (ex: escolha do melhor formato de prompt ou estratégia de limpeza de histórico) e para garantir que novas alterações no engine não causem regressões na eficácia dos agentes.
