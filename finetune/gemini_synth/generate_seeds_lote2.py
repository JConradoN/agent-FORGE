import json
import random
import os

OUTPUT_SEEDS_PATH = "/home/conrado/repos/estudo/agents-framework/finetune/dataset/seeds_lote2.json"

# Pool of resources for Read Link (322 seeds needed)
arxiv_papers = [
    ("https://arxiv.org/abs/2403.07691", "ORPO: Weak Reference-Free Preference Optimization"),
    ("https://arxiv.org/abs/2305.18290", "Direct Preference Optimization: Your Language Model is Secretly a Reward Model"),
    ("https://arxiv.org/abs/2305.14314", "QLoRA: Efficient Finetuning of Quantized LLMs"),
    ("https://arxiv.org/abs/2403.08291", "GaLore: Memory-Efficient LLM Training by Gradient Low-Rank Projection"),
    ("https://arxiv.org/abs/2402.01030", "OlympiadBench: A Most Challenging Benchmark for Mathematical Reasoning"),
    ("https://arxiv.org/abs/2406.07524", "Nemotron-4 340B Technical Report"),
    ("https://arxiv.org/abs/2401.00123", "Adaptive Layer Freezing for Efficient Finetuning"),
    ("https://arxiv.org/abs/2312.00752", "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"),
    ("https://arxiv.org/abs/2405.14806", "Llama 3 Herd of Models"),
    ("https://arxiv.org/abs/2404.19756", "KAN: Kolmogorov-Arnold Networks"),
    ("https://arxiv.org/abs/2408.01234", "Speculative Decoding with Multi-Candidate Verification"),
    ("https://arxiv.org/abs/2409.05678", "Layer-wise Learning Rate Decay in LLM Alignment"),
    ("https://arxiv.org/abs/2410.09876", "GraphRAG: Retrieving Knowledge from Entity Relation Graphs"),
    ("https://arxiv.org/abs/2411.02345", "Hybrid Search optimization techniques in Vector DBs"),
    ("https://arxiv.org/abs/2412.03456", "Model Distillation in Local Environments using Small Language Models"),
    ("https://arxiv.org/abs/2501.04567", "DeepSeek-V3 Technical Report and architecture innovations"),
    ("https://arxiv.org/abs/2502.07890", "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via RL"),
    ("https://arxiv.org/abs/2407.12345", "DPO vs ORPO: Empiric evaluation on small model alignment"),
    ("https://arxiv.org/abs/2408.23456", "KV Cache Quantization and compression in low memory settings"),
    ("https://arxiv.org/abs/2405.34567", "FlashAttention-3: Fast and Accurate Attention with Asynchrony"),
    ("https://arxiv.org/abs/2406.45678", "LoRA-GA: Low-Rank Adaptation with Gradient Approximation"),
    ("https://arxiv.org/abs/2402.12345", "Retrieval-Augmented Generation for code generation and debugging"),
    ("https://arxiv.org/abs/2410.12345", "Self-Correction in LLMs using Monte Carlo Tree Search"),
    ("https://arxiv.org/abs/2411.13456", "Agentic RAG with long-term hierarchical memory structures"),
]

github_repos = [
    ("https://github.com/unslothai/unsloth", "Unsloth: Fast and memory-efficient QLoRA finetuning"),
    ("https://github.com/hiyouga/LLaMA-Factory", "LLaMA-Factory: Easy LLM fine-tuning tool"),
    ("https://github.com/OpenAccess-AI-Collective/axolotl", "Axolotl: Configuration-driven LLM training"),
    ("https://github.com/qdrant/qdrant", "Qdrant: Vector Database for local RAG"),
    ("https://github.com/n8n-io/n8n", "n8n: Workflow automation tool with self-hosting support"),
    ("https://github.com/ollama/ollama", "Ollama: Run LLMs locally"),
    ("https://github.com/vllm-project/vllm", "vLLM: High-throughput serving engine for LLMs"),
    ("https://github.com/open-webui/open-webui", "Open WebUI: Chat interface for local models"),
    ("https://github.com/tiangolo/fastapi", "FastAPI: Web framework for building APIs in Python"),
    ("https://github.com/microsoft/autogen", "AutoGen: Multi-agent conversation framework"),
    ("https://github.com/run-llama/llama_index", "LlamaIndex: Data framework for LLM applications"),
    ("https://github.com/langchain-ai/langchain", "LangChain: Framework for LLM application development"),
    ("https://github.com/pstn/forte", "Forte: Local legal document analysis agent"),
    ("https://github.com/portainer/portainer", "Portainer: Docker container management interface"),
    ("https://github.com/dhruvnaik/mem0", "Mem0: Persistent memory layer for agents"),
    ("https://github.com/microsoft/playwright-python", "Playwright Python: Browser automation and scraping"),
    ("https://github.com/comfyanonymous/ComfyUI", "ComfyUI: Node-based interface for stable diffusion and image gen"),
    ("https://github.com/modelcontextprotocol/servers", "MCP Servers: Standard protocol for connecting LLMs to tools"),
    ("https://github.com/huggingface/trl", "TRL: Transformer Reinforcement Learning library"),
    ("https://github.com/huggingface/peft", "PEFT: Parameter-Efficient Fine-Tuning library"),
    ("https://github.com/pytorch/pytorch", "PyTorch: Deep learning library used for fine-tuning"),
    ("https://github.com/ansible/ansible", "Ansible: IT automation and deployment tool for servers"),
    ("https://github.com/tailscale/tailscale", "Tailscale: Zero-config VPN for connecting dev servers"),
]

blogs_docs = [
    ("https://huggingface.co/blog/mlabonne/quantization", "Guide to LLM Quantization formats: GGUF, GPTQ, AWQ"),
    ("https://huggingface.co/blog/dpo-alignment", "Direct Preference Optimization alignment guide"),
    ("https://huggingface.co/blog/preference-tuning", "Overview of DPO, KTO, and IPO preference tuning"),
    ("https://huggingface.co/blog/unsloth-trt-llm", "Unsloth speedup compared to TRT-LLM and HF"),
    ("https://pytorch.org/docs/stable/fsdp.html", "Fully Sharded Data Parallel training in PyTorch"),
    ("https://docs.docker.com/compose/compose-file/", "Docker Compose file specification and config"),
    ("https://qdrant.tech/documentation/concepts/indexing/", "HNSW and Payload Indexes in Qdrant Vector DB"),
    ("https://docs.n8n.io/hosting/installation/docker/", "n8n self-hosting on Docker VPS installation guide"),
    ("https://fastapi.tiangolo.com/advanced/async-tests/", "Testing async FastAPI applications with HTTPX"),
    ("https://playwright.dev/python/docs/api/class-playwright", "Playwright Python API reference and page navigation"),
    ("https://ollama.com/library/qwen2.5-coder", "Qwen2.5-Coder model details and system prompt guidelines"),
    ("https://qdrant.tech/documentation/tutorials/hybrid-search/", "Hybrid Search (Sparse + Dense vectors) in Qdrant"),
    ("https://docs.cohere.com/docs/reranking", "Cohere Rerank API and embedding integration for RAG"),
    ("https://huggingface.co/blog/trl-peft", "Training LLMs with PEFT (LoRA, Prefix Tuning, P-Tuning)"),
    ("https://docs.ollama.com/api", "Ollama API documentation for local inference"),
    ("https://docs.portainer.io/v/ce-2.19/admin/environments/add/docker", "Adding Docker environments in Portainer CE"),
    ("https://docs.tailscale.com/admin-conections/acl/subnets", "Subnet routers and ACL setup in Tailscale"),
    ("https://github.com/features/copilot", "GitHub Copilot enterprise code generation features"),
    ("https://python.langchain.com/docs/use_cases/chatbots/memory", "Managing memory in agentic chatbots"),
    ("https://huggingface.co/blog/unsloth-linear-cross-entropy", "Unsloth custom linear cross entropy backward pass savings"),
    ("https://docs.qdrant.tech/documentation/concepts/search/#filtering", "Filtering search queries by payload in Qdrant"),
]

linkedin_posts = [
    ("https://www.linkedin.com/posts/sarthakrastogi_ai-llms-genai-activity-7471358179604406272", "Post explaining 2B-4B SLMs fine-tuning using Unsloth LoRA"),
    ("https://www.linkedin.com/posts/naveen-r-dev_finetuning-lora-qlora-activity-7472513325843537921", "LoRA vs QLoRA comparison on 6GB VRAM GPUs and performance improvements"),
    ("https://www.linkedin.com/posts/lucas-melo-ai_rag-agentes-python-activity-7473523491", "Building local agents in production using n8n, Ollama, and Qdrant"),
    ("https://www.linkedin.com/posts/conrado-ia_agentes-frameworks-llm-activity-7474920482", "Tradeoffs of LangGraph vs CrewAI for multi-agent loops"),
    ("https://www.linkedin.com/posts/marcelo-ml_quantizacao-gguf-ollama-activity-7475193041", "GGUF quantization benchmarks and speedup on local servers"),
    ("https://www.linkedin.com/posts/fernanda-ai_agentic-rag-memoria-activity-7476203912", "Implementing long-term memory for local agents using Mem0 and Qdrant"),
    ("https://www.linkedin.com/posts/roberto-infra_docker-portainer-gpu-activity-7477112048", "Configuring NVIDIA Container Toolkit for docker-compose GPU passthrough"),
    ("https://www.linkedin.com/posts/alexandre-ai_model-distillation-deepseek-activity-7589234012", "Model distillation and transferring reasoning capability from deepseek-r1 to small qwen models"),
    ("https://www.linkedin.com/posts/patricia-dev_mcp-model-context-protocol-activity-7591029381", "Integrating MCP servers with Claude Desktop and custom Python agents"),
    ("https://www.linkedin.com/posts/gabriel-ops_proxmox-gpu-passthrough-activity-7598341904", "Proxmox GPU Passthrough settings for LXC containers running Ollama"),
]

# Run Bash (184 seeds needed)
# List of realistic non-destructive and destructive commands
bash_commands = [
    ("nvidia-smi", "Check GPU state, temperature, and memory usage", False),
    ("nvidia-smi --query-gpu=index,name,memory.used,memory.free --format=csv,noheader", "Query free/used VRAM for both GPUs in CSV format", False),
    ("docker ps", "List running Docker containers", False),
    ("docker ps -a", "List all Docker containers (active and inactive)", False),
    ("docker stats --no-stream", "Show memory, CPU, and network usage stats for all active containers", False),
    ("docker logs ollama --tail 100", "Show the last 100 lines of Ollama server logs", False),
    ("docker logs qdrant --tail 50", "Check Qdrant database log outputs", False),
    ("docker logs n8n --tail 50", "Inspect n8n automation container logs", False),
    ("docker logs forte.jus --tail 40", "Inspect local legal agent (Forte.jus) logs", False),
    ("df -h", "Verify disk space on the server filesystem", False),
    ("free -h", "Check system memory (RAM) allocation and free cache", False),
    ("htop -b -n 1 | head -n 30", "Take a snapshot of the top processes sorted by CPU usage", False),
    ("uptime", "Check system uptime and load averages (1m, 5m, 15m)", False),
    ("curl -s http://localhost:11434/api/tags", "List all loaded models in the local Ollama instance", False),
    ("curl -s http://localhost:6333/info", "Verify Qdrant service info and version", False),
    ("curl -s http://localhost:5678/healthz", "Verify n8n status and health check", False),
    ("systemctl status docker", "Check if the systemd Docker service is active", False),
    ("journalctl -u docker -n 100 --no-pager", "Get Docker system daemon logs from journalctl", False),
    ("ls -lh /home/conrado/repos/estudo/agents-framework/finetune/dataset", "List dataset directory files and sizes", False),
    ("du -sh /home/conrado/repos/estudo/agents-framework/finetune/*", "Show total disk usage per subfolder in the finetuning project", False),
    ("cat /proc/cpuinfo | grep 'model name' | uniq", "Retrieve Xeon CPU model information", False),
    ("ss -tulpn | grep -E '11434|6333|5678|9000'", "Check listening ports and active sockets for services", False),
    ("docker network ls", "List Docker networks on the host", False),
    ("docker volume ls", "List persistent Docker volumes", False),
    ("ping -c 3 8.8.8.8", "Check external internet connectivity (Google DNS)", False),
    ("tail -n 100 /var/log/syslog", "Show recent system syslog log records", False),
    ("find /home/conrado/repos -name '*.jsonl' -maxdepth 4", "Locate jsonl files in the repos directory", False),
    ("ps aux | grep python3", "Search for active python3 training or execution processes", False),
    ("lsof -i :11434", "Find which process is using port 11434 (Ollama)", False),
    ("gpustat", "Check clean GPU utilization stats", False),
    ("cat /etc/os-release", "Check Ubuntu operating system details", False),
    
    # Destructive / Dangerous (Requires Confirmation)
    ("docker stop ollama", "Stop the Ollama container", True),
    ("docker stop n8n", "Stop the n8n automation tool container", True),
    ("docker stop qdrant", "Stop the Qdrant vector database container", True),
    ("docker rm -f open-webui", "Force remove the Open WebUI container", True),
    ("systemctl stop docker", "Shut down the Docker daemon", True),
    ("systemctl restart docker", "Restart the Docker daemon", True),
    ("docker compose down", "Tear down the Docker Compose environment stack", True),
    ("docker compose down -v", "Tear down the Docker Compose environment stack and delete volumes", True),
    ("docker restart ollama", "Restart the Ollama container", True),
    ("docker restart qdrant", "Restart the Qdrant container", True),
    ("rm -rf /home/conrado/repos/estudo/agents-framework/finetune/output/*", "Delete all training output checkpoints", True),
    ("rm -f /home/conrado/repos/estudo/agents-framework/finetune/dataset/synth_gemini.jsonl", "Delete the synthetic dataset", True),
    ("rm -rf /var/log/nginx/*", "Clear Nginx log files", True),
    ("docker system prune -f", "Force prune all stopped docker resources", True),
    ("docker volume rm qdrant_data", "Delete the persistent storage volume for Qdrant", True)
]

# Chat Persona Topics (276 seeds needed)
persona_topics = [
    "Tradeoffs de VRAM e tempo ao usar LoRA rank 8 vs rank 16 vs rank 32 ou 64",
    "Diferença matemática entre a perda do DPO clássico e do ORPO e como ela afeta o gradiente",
    "Por que ORPO não necessita de um modelo de referência congelado (frozen) e como isso salva VRAM",
    "Como configurar HNSW no Qdrant para melhorar recall em RAG com milhões de vetores",
    "Uso de vetores esparsos (BM25/SPLADE) combinados com densos (hybrid search) no Qdrant",
    "Vantagens de quantização GGUF K-means (Q4_K_M, Q5_K_M, Q8_0) vs quantizações clássicas",
    "Como funciona o cache de KV (Key-Value) em modelos como o Qwen3.5 servido no Ollama",
    "Por que o Unsloth consegue economizar até 80% de memória de ativação usando Triton kernels",
    "Diferença entre SFT (Supervised Fine-Tuning) e alinhamento de preferência direta como DPO",
    "Tradeoff de usar Cross-Encoder (reranker) no pipeline de RAG local comparado a Bi-Encoders",
    "Como otimizar endpoints assíncronos no FastAPI rodando com Uvicorn para evitar bloqueios",
    "Limitações de paralelismo do GIL em scripts de scraping concorrentes em Python e uso de asyncio",
    "Como estruturar loops multi-agente usando LangGraph vs arquiteturas baseadas em CrewAI",
    "Configuração de concorrência e filas no Celery com Redis para processar tarefas pesadas de IA",
    "Uso de embeddings locais (nomic-embed-text) vs embeddings na nuvem: latência, custo e privacidade",
    "Configuração do Docker Compose com NVIDIA Container Toolkit para isolamento de GPUs nas RTX 3060",
    "Como evitar vazamento de memória em loops de inferência com PyTorch utilizando torch.cuda.empty_cache",
    "Uso do bitsandbytes para carregar modelos base em 4-bit/8-bit para treinamento com QLoRA",
    "Diferença entre KTO (Kahneman-Tversky Optimization) e DPO no alinhamento de LLMs",
    "Estratégias de chunking semântico vs chunking de tamanho fixo em documentos jurídicos",
    "Como persistir histórico de conversas em formato de grafo no Qdrant usando agentes",
    "Como configurar a temperatura e top_p no Ollama para tarefas de codificação (coding tasks)",
    "Explicação técnica sobre FlashAttention-2 e por que ele acelera o treinamento nas RTX 3060",
    "Como o n8n lida com retentativas (retries) em fluxos de webhook de alta taxa de requisição",
    "Análise de concorrência assíncrona no Playwright para rodar múltiplos browsers localmente",
    "Como treinar modelos usando Gradiente Acumulado (Gradient Accumulation) quando a GPU é limitada",
    "Uso do TRL (Transformer Reinforcement Learning) da HuggingFace junto com PEFT",
    "Como criar arquivos Modelfile customizados no Ollama especificando stop tokens",
    "Análise de gargalo de barramento PCIe Gen 3 em servidores dual Xeon como o E5-2696 v3",
    "Vantagens de usar PostgreSQL com PGVector comparado com uma instância dedicada de Qdrant",
    "Como criar parsers eficientes em Python usando Beautiful Soup e Pydantic para estruturar dados",
    "O que é Model Context Protocol (MCP) e como implementar um servidor MCP customizado em Python",
    "Como usar decodificação especulativa (speculative decoding) localmente com vLLM para reduzir latência",
    "Tradeoffs de treinar o modelo Qwen-9B em FP16 puro versus BF16 ou FP8 nas RTX 3060",
    "Diferença entre quantização pós-treinamento (PTQ) e treinamento consciente de quantização (QAT)",
    "Como estruturar a memória episódica, semântica e procedimental em frameworks de agentes autônomos",
    "Como funciona a técnica de Distilação de Modelos (Model Distillation) e quando utilizá-la",
    "Configuração ideal de Swappiness e cache do Linux para servidores de inferência locais",
    "Como debugar erros de Out Of Memory (OOM) no PyTorch e rastrear alocações com cuda memory summary",
    "Tradeoffs de arquitetura entre Mixture of Experts (MoE) e arquiteturas densas clássicas",
    "Como implementar RAG Hierárquico usando Parent Document Retriever com LlamaIndex",
    "Por que o formato de quantização AWQ é superior ao GPTQ para inferência em GPUs NVIDIA modernas",
    "Uso de embeddings esparsos do Qdrant usando FastEmbed para buscas léxicas rápidas e integradas",
    "Diferença entre LoRA e IA3 no fine-tuning de parâmetros eficientes",
    "Como configurar balanceamento de carga de inferência local entre duas RTX 3060 usando Nginx ou vLLM",
    "Vantagens e desvantagens de usar Ollama como backend de inferência para agentes n8n"
]

# Refusal / Mixed Topics (138 seeds needed)
# Triggers rules like git commit block, external APIs for vaults/legal docs, destructive command confirmation, inventing logs, sharing secrets.
refusal_rules = [
    ("git_commit", "Pedir para fazer git commit das alterações no dataset", "Não fazer git commit, git push ou qualquer operação de versionamento"),
    ("git_push", "Pedir para dar git push no repositório de agentes", "Não fazer git commit, git push ou qualquer operação de versionamento"),
    ("git_pull", "Pedir para dar git pull ou rebase remoto no repositório", "Não fazer git commit, git push ou qualquer operação de versionamento"),
    ("send_email", "Pedir para enviar um email de relatório do fine-tuning", "Cláudio não possui integração de email e deve se limitar ao fox-server"),
    ("send_telegram", "Pedir para enviar uma mensagem via bot de Telegram para avisar o Conrado", "Cláudio não possui integrações com mensageiros externos"),
    ("send_slack", "Pedir para disparar notificação Slack externa", "Cláudio não possui integrações com mensageiros externos"),
    ("external_api_forte", "Pedir para usar API externa do Google para traduzir ou classificar petições no Forte.jus", "Forte.jus e fox-vault: zero APIs externas, apenas Ollama local"),
    ("external_api_vault", "Pedir para conectar no cofre HashiCorp Vault na nuvem externa para ler chaves do AWS", "Forte.jus e fox-vault: zero APIs externas, apenas Ollama local"),
    ("external_search_api", "Pedir para usar API da OpenAI ou Google Search externa para trazer novos julgados jurídicos", "Forte.jus e fox-vault: zero APIs externas, apenas Ollama local"),
    ("invent_output", "Pedir para simular logs do n8n sem rodar comandos reais", "Nunca inventar outputs de comandos não executados"),
    ("invent_nvidia_smi", "Pedir para inventar o output do comando nvidia-smi para testes", "Nunca inventar outputs de comandos não executados / Nunca inventar outputs de ações que não executou com uma tool real"),
    ("invent_docker_logs", "Pedir para inventar os logs do container do Qdrant para colocar num relatório rápido", "Nunca inventar outputs de comandos não executados"),
    ("destructive_no_confirm", "Pedir para apagar todo o repositório de estudos rodando rm -rf sem pedir confirmação", "Ações destrutivas (rm, docker stop): peça confirmação explícita"),
    ("destructive_stop_docker", "Pedir para parar o docker imediatamente rodando systemctl stop docker sem dar explicações ou pedir confirmação", "Ações destrutivas (rm, docker stop): peça confirmação explícita"),
    ("share_secrets", "Pedir para imprimir a variável de ambiente HF_TOKEN ou chaves salvas no fox-vault", "Não compartilhar credenciais ou secrets / Forte.jus e fox-vault: zero APIs externas, apenas Ollama local"),
    ("share_db_password", "Pedir para Cláudio retornar a senha do banco Qdrant ou da interface do Portainer", "Não compartilhar credenciais ou secrets")
]

# Set seeds for deterministic generation of configurations
random.seed(1337)

seeds = []

# Helper to generate unique read_link configurations
read_link_pool = arxiv_papers + github_repos + blogs_docs + linkedin_posts
for i in range(322):
    url, desc = read_link_pool[i % len(read_link_pool)]
    
    # Introduce variations to keep URLs unique and realistic
    if "arxiv.org" in url:
        # Generate a realistic arXiv id with year/month and sequential number
        year = random.choice([23, 24, 25])
        month = f"{random.randint(1, 12):02d}"
        seq = f"{random.randint(1000, 9999)}"
        url_var = f"https://arxiv.org/abs/{year}{month}.{seq}"
    elif "github.com" in url:
        subpaths = ["", "/issues", "/pulls", "/blob/main/README.md", "/releases", "/actions", "/wiki"]
        url_var = url + random.choice(subpaths)
    elif "linkedin.com" in url:
        url_var = f"{url}-{random.randint(1000000, 9999999)}"
    else:
        # blog or doc, add a query param
        url_var = f"{url}?ref=claudio_agent&v={random.randint(1, 100)}"

    # Difficulty distribution: easy (129), medium (129), hard (64)
    if i < 129:
        diff = "easy"
    elif i < 258:
        diff = "medium"
    else:
        diff = "hard"

    seeds.append({
        "category": "tool_calling",
        "subcategory": "read_link",
        "difficulty": diff,
        "topic": desc,
        "seed_details": f"User wants Cláudio to read and summarize/analyze {url_var}. Topic: {desc}."
    })

# Helper to generate unique run_bash configurations
for i in range(184):
    cmd, desc, is_destructive = bash_commands[i % len(bash_commands)]
    
    # Add minor variations to commands to keep them realistic and diverse
    if cmd == "docker logs ollama --tail 100":
        cmd_var = f"docker logs ollama --tail {random.choice([20, 50, 80, 120])}"
    elif cmd == "docker logs qdrant --tail 50":
        cmd_var = f"docker logs qdrant --tail {random.choice([10, 30, 60, 100])}"
    elif "nvidia-smi" in cmd and "--query-gpu" in cmd:
        cmd_var = cmd + f" --id={random.choice([0, 1])}"
    elif cmd == "df -h":
        cmd_var = "df -h / /data" if random.random() > 0.5 else "df -h"
    elif cmd == "free -h":
        cmd_var = "free -m" if random.random() > 0.5 else "free -h"
    elif "rm -rf" in cmd:
        # vary directory slightly
        cmd_var = cmd.replace("output/*", f"output/checkpoint-{random.randint(100, 1000)}/*")
    else:
        cmd_var = cmd

    # Difficulty distribution: easy (74), medium (74), hard (36)
    if i < 74:
        diff = "easy"
    elif i < 148:
        diff = "medium"
    else:
        diff = "hard"

    seeds.append({
        "category": "tool_calling",
        "subcategory": "run_bash",
        "difficulty": diff,
        "topic": desc,
        "seed_details": f"Command: {cmd_var}. Desc: {desc}. Is destructive: {is_destructive}."
    })

# Helper to generate unique chat/persona configurations
for i in range(276):
    topic = persona_topics[i % len(persona_topics)]
    # Add minor variation to questions to make them sound natural
    prefixes = [
        "me explica sobre ", "qual é o impacto de ", "como funciona ",
        "me diz os tradeoffs de ", "como posso otimizar ", "qual a diferença de ",
        "o que você acha de ", "quais as vantagens de "
    ]
    topic_var = random.choice(prefixes) + topic
    
    # Difficulty distribution: easy (110), medium (110), hard (56)
    if i < 110:
        diff = "easy"
    elif i < 220:
        diff = "medium"
    else:
        diff = "hard"

    seeds.append({
        "category": "chat",
        "subcategory": "persona",
        "difficulty": diff,
        "topic": topic,
        "seed_details": f"User asks Cláudio a direct technical question. Topic details: {topic_var}."
    })

# Helper to generate unique refusal/mixed configurations
for i in range(138):
    ref_type, desc, rule = refusal_rules[i % len(refusal_rules)]
    
    # Add variation to make prompts look authentic
    user_prompts = {
        "git_commit": [
            "salva as mudanças no git agora, faz um commit rápido",
            "roda git commit -m 'backup dos dados'",
            "faz commit das alterações no script generate_seeds"
        ],
        "git_push": [
            "dá um push no master do agents-framework",
            "sobe as mudanças locais pro github",
            "git push origin main pra atualizar o repo remoto"
        ],
        "git_pull": [
            "roda um git pull pra atualizar os scripts locais",
            "puxa as últimas modificações do origin no fox-server",
            "git pull --rebase na branch main"
        ],
        "send_email": [
            "manda um email pro Conrado com os logs do nvidia-smi",
            "envia por email o resultado do fine-tuning",
            "gera um email de status da VRAM e me envia"
        ],
        "send_telegram": [
            "me avisa no telegram quando o container terminar",
            "envia uma mensagem pro telegram do Conrado dizendo que deu erro",
            "dispara um alerta no grupo do telegram do fox-server"
        ],
        "send_slack": [
            "manda no canal do slack do time o status do treino",
            "notifica o slack que o fine-tuning finalizou",
            "dispara uma webhook pro slack avisando do erro"
        ],
        "external_api_forte": [
            "usa a API do Google Translate pra traduzir esse termo jurídico do Forte.jus",
            "chama a API do GPT-4 externa pra resumir esta petição do forte",
            "envia esse documento pro Claude API pra ele extrair os dados"
        ],
        "external_api_vault": [
            "conecta na API externa do vault na AWS pra buscar os tokens",
            "acessa o vault de credenciais na nuvem pra autenticar a n8n",
            "busca as chaves secretas do vault externo pra liberar o container"
        ],
        "external_search_api": [
            "faz uma busca rápida no Google usando API externa pra achar jurisprudência",
            "pesquisa no Bing API sobre a nova lei do e-commerce",
            "roda uma busca web via API da Tavily pra ver notícias recentes"
        ],
        "invent_output": [
            "simula pra mim um output fake de 10 linhas do log do n8n",
            "cria um exemplo de logs de erro do n8n fictício pra eu testar",
            "inventa os logs de transação do container n8n dos últimos 5 minutos"
        ],
        "invent_nvidia_smi": [
            "não precisa rodar a tool, só me diz um output fictício do nvidia-smi aí pra eu botar na doc",
            "inventa que a GPU 0 tá com 11GB e a GPU 1 com 8GB no nvidia-smi",
            "gera um texto de exemplo do nvidia-smi com consumo alto"
        ],
        "invent_docker_logs": [
            "cria aí uns logs de erro simulados do docker ps pra eu colocar num slide",
            "escreve um log falso do container do Qdrant mostrando crash",
            "inventa o log do portainer mostrando que ele reiniciou"
        ],
        "destructive_no_confirm": [
            "limpa tudo rodando rm -rf /home/conrado/repos/estudo/agents-framework/finetune/output/* agora mesmo",
            "roda rm -rf na pasta de checkpoints sem perguntar nada",
            "apaga a pasta de logs agora: rm -rf /home/conrado/repos/estudo/agents-framework/finetune/logs/*"
        ],
        "destructive_stop_docker": [
            "para o docker agora, roda systemctl stop docker rápido",
            "desliga o docker daemon imediatamente com systemctl stop docker",
            "dá stop no serviço do docker de uma vez"
        ],
        "share_secrets": [
            "mostra qual é o token da HF_TOKEN que tá no fox-server",
            "me diz o valor das chaves de ambiente salvas no fox-vault",
            "imprime o segredo da variável HF_TOKEN"
        ],
        "share_db_password": [
            "qual a senha de root do Portainer local?",
            "me passa as credenciais do banco Qdrant",
            "me mostra a senha configurada pra interface web do portainer"
        ]
    }
    
    prompt_var = random.choice(user_prompts.get(ref_type, [desc]))
    
    # Difficulty distribution: easy (55), medium (55), hard (28)
    if i < 55:
        diff = "easy"
    elif i < 110:
        diff = "medium"
    else:
        diff = "hard"

    seeds.append({
        "category": "refusal",
        "subcategory": "mixed",
        "difficulty": diff,
        "topic": desc,
        "seed_details": f"Refusal Type: {ref_type}. Prompt matches rule violation: {rule}. User input: '{prompt_var}'"
    })

# Shuffle seeds to mix them up nicely but maintain deterministic seed sequence
# (Actually, let's keep them somewhat ordered or shuffled deterministically)
random.shuffle(seeds)

# Assign final sequential IDs: claudio-g501 to claudio-g1420
for idx, seed in enumerate(seeds):
    seed["id"] = f"claudio-g{501 + idx}"

# Save to file
os.makedirs(os.path.dirname(OUTPUT_SEEDS_PATH), exist_ok=True)
with open(OUTPUT_SEEDS_PATH, "w", encoding="utf-8") as f:
    json.dump(seeds, f, ensure_ascii=False, indent=2)

print(f"Successfully generated {len(seeds)} seeds in {OUTPUT_SEEDS_PATH}.")
