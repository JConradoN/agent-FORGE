# AgentForge

**AgentForge** é um framework Python *spec-first* e *local-first* projetado para a criação, experimentação e execução de agentes LLM em ambientes on-premise. 

Diferente de frameworks genéricos de IA, o AgentForge foca na previsibilidade do comportamento do agente através de uma separação rigorosa entre a **definição** (specs) e a **execução** (runtime). O fluxo de trabalho é centrado no **Ollama**, garantindo privacidade e controle total dos dados.

### Diferenciais
- **Spec-Driven:** O agente nasce de uma especificação YAML (`agent.yaml`) e gera artefatos de runtime imutáveis.
- **Local-First:** Otimizado para Ollama, com foco em modelos como `qwen3.5:9b` e `qwen3.5:27b`.
- **Artefatos Explícitos:** O framework separa o `system_prompt.md` das configurações de modelo, facilitando o versionamento e a auditoria de prompts.
- **Provider Registry:** Abstração de infraestrutura que permite alternar entre execução real (Ollama) e testes determinísticos (Mock) via configuração de deployment.

---

## Requisitos e Instalação

### Requisitos
- **SO:** Linux (Ubuntu/Debian recomendado).
- **Python:** 3.11 ou superior.
- **Ollama:** Instalado e rodando (localmente ou via Docker).
- **Modelo recomendado:** `qwen3.5:9b` (melhor custo-benefício, 7GB VRAM) ou `qwen3.5:27b` (tarefas complexas, 17GB VRAM).

### Instalação
1. Clone o repositório:
   ```bash
   git clone <URL-do-repo>
   cd agents-framework
   ```

2. Crie e ative um ambiente virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Instale o pacote em modo editável:
   ```bash
   pip install -e .
   ```

---

## Fluxo Básico (CLI)

O ciclo de vida de um agente no AgentForge segue três etapas principais via terminal:

### 1. Criar a especificação (Wizard)
Inicie o fluxo interativo para definir persona, ferramentas e políticas do seu agente.
```bash
agentforge wizard
```
Isso gerará o arquivo `agents/<id>/agent.yaml`.

### 2. Gerar artefatos (Generate)
Transforme a spec YAML nos arquivos de runtime que o agente utilizará.
```bash
agentforge generate --path agents/<id>/agent.yaml
```
Arquivos gerados em `agents/<id>/`:
- `system_prompt.md`: O prompt de sistema consolidado e estruturado.
- `runtime.yaml`: Configurações de deployment e parâmetros de modelo.
- `tools.yaml`: Definição de ferramentas para o modelo.
- `eval.yaml`: Configurações para avaliação de qualidade.
- `README.md`: Documentação técnica automática do agente.

### 3. Executar (Run)
Rode o agente diretamente pelo diretório gerado.
```bash
# Execução usando o provider configurado no agent.yaml (default: ollama)
agentforge run --agent-dir agents/<id> --input "Olá, quem é você?"
```

> **Dica:** Para testar sem gastar recursos do Ollama, você pode alterar o campo `deployment.provider` para `mock` no seu `agent.yaml`, rodar o `generate` novamente e executar o `run`.

---

## Estrutura do Projeto

- `specs/`: Schemas de validação para o framework e orquestrador.
- `agents/`: Diretório padrão onde os agentes e seus artefatos residem.
- `src/agentforge/core/`: Modelos de dados (Pydantic) e lógica de validação.
- `src/agentforge/wizard/`: Lógica do fluxo interativo de criação.
- `src/agentforge/generators/`: Geradores de arquivos (System Prompt, YAMLs de runtime).
- `src/agentforge/runtime/`: Engine que carrega os artefatos e gerencia o ciclo de vida do agente.
- `src/agentforge/providers/`: Implementação dos conectores (Ollama, Mock).
- `tests/`: Suíte completa de testes unitários e de integração.

---

## Conceitos Principais

- **AgentSpec (`agent.yaml`):** A única fonte de verdade. Contém a identidade, persona e regras do agente.
- **DeploymentSpec:** Define qual provider será usado (ex: `ollama`, `mock`).
- **System Prompt:** Documento Markdown gerado que injeta as instruções de formato e restrições no LLM.
- **Runtime Engine:** Carrega o diretório do agente, resolve o provider e executa a inferência de forma isolada.

---

## Roadmap e Limites Atuais

O projeto está em desenvolvimento ativo. Confira o [ROADMAP.md](ROADMAP.md) para a visão completa.

**Limitações atuais:**
- Suporte inicial a **tool calling** (definição pronta, execução em implementação).
- Interface de chat **stateless** (entrada/saída simples, sem histórico multi-turno persistente).
- Sem suporte a streaming de tokens na CLI.
- Execução síncrona (sem suporte a canais assíncronos como Telegram/Web nesta fase).

---

## Desenvolvimento e Testes

O projeto utiliza `pytest` para garantir a estabilidade das especificações e do runtime. É recomendado rodar os testes após qualquer alteração no `AgentSpec` ou na lógica dos providers.

```bash
# Rodar todos os testes de forma silenciosa
pytest -q
```
