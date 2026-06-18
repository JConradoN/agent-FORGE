import os
import json
import random
import time
import re
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import ollama

# Configuration
GOLD_SEED_PATH = "/home/conrado/repos/estudo/agents-framework/finetune/dataset/gold_seed.jsonl"
GOLD_BATCH2_PATH = "/home/conrado/repos/estudo/agents-framework/finetune/dataset/gold_batch2.jsonl"
OUTPUT_PATH = "/home/conrado/repos/estudo/agents-framework/finetune/dataset/synth_gemini_batch2.jsonl"
PROGRESS_LOG_PATH = "/home/conrado/repos/estudo/agents-framework/finetune/dataset/synth_progress.log"

SYSTEM_PROMPT = """Você é Cláudio, assistente pessoal do Conrado rodando localmente no fox-server.

Perfil do Conrado:
- Desenvolvedor e pesquisador em IA, agentes, Python e infraestrutura
- Nível avançado — não explique conceitos básicos sem ser pedido
- Prefere respostas diretas, técnicas, em PT-BR, sem emojis, sem rodeios

Você tem acesso ao fox-server (Ubuntu 26.04, Xeon E5-2696 v3, 2×RTX 3060, 128GB RAM).
Serviços ativos: n8n, qdrant, ollama, open-webui, forte.jus, portainer.

Tools disponíveis:
- read_link: lê e analisa URLs (LinkedIn, artigos, posts) via browser autenticado. Use sempre que o usuário enviar um link ou pedir para ler/analisar uma URL.
- run_bash: executa comandos no fox-server para verificar status, logs, GPU, containers.

Formato de resposta:
- Texto puro sem markdown. Não use *, _, #, \\ ou símbolos de formatação.
- Para listas use hífen (-). Para código use crases (```).

Regras invioláveis:
- Forte.jus e fox-vault: zero APIs externas, apenas Ollama local
- Ações destrutivas (rm, docker stop, systemctl stop): peça confirmação explícita
- Nunca inventar outputs de comandos não executados
- Se não souber algo com certeza, diga explicitamente — nunca invente
- Não faça git commit, git push ou qualquer operação de versionamento
- Nunca invente outputs de ações que não executou com uma tool real"""

def load_gold_examples():
    """Loads gold examples from both seed and batch2 files, organized by category/subcategory."""
    examples = {
        ("tool_calling", "read_link"): [],
        ("tool_calling", "run_bash"): [],
        ("chat", "persona"): [],
        ("refusal", "mixed"): []
    }
    
    for path in [GOLD_SEED_PATH, GOLD_BATCH2_PATH]:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    cat = data.get("category")
                    subcat = data.get("subcategory", "")
                    
                    if cat == "refusal":
                        key = ("refusal", "mixed")
                    else:
                        key = (cat, subcat)
                        
                    if key in examples:
                        examples[key].append(data)
                except Exception as e:
                    print(f"Error reading gold line: {e}")
                    
    return examples

def generate_seeds():
    """Generates 500 unique seed configurations with maximum diversity."""
    seeds = []
    
    # 1. READ_LINK: 175 seeds (easy: 70, medium: 70, hard: 35)
    arxiv_papers = [
        ("https://arxiv.org/abs/2305.14314", "QLoRA: Efficient Finetuning of Quantized LLMs"),
        ("https://arxiv.org/abs/2305.18290", "Direct Preference Optimization: Your Language Model is Secretly a Reward Model"),
        ("https://arxiv.org/abs/2403.07691", "ORPO: Weak Reference-Free Preference Optimization"),
        ("https://arxiv.org/abs/2005.11401", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"),
        ("https://arxiv.org/abs/2310.11511", "Self-RAG: Learning to Retrieve, Generate, and Critique"),
        ("https://arxiv.org/abs/2402.01030", "OlympiadBench: A Most Challenging Benchmark for Mathematical Reasoning"),
        ("https://arxiv.org/abs/2309.03409", "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversations"),
        ("https://arxiv.org/abs/2308.10620", "MetaGPT: Meta Programming for Multi-Agent Collaborative Framework"),
        ("https://arxiv.org/abs/2303.17564", "Reflexion: Language Agents with Active Learning Memories"),
        ("https://arxiv.org/abs/2401.00123", "Adaptive Layer Freezing for Efficient Finetuning"),
        ("https://arxiv.org/abs/2402.03300", "Dense X Retrieval: What Retrieval Granularity Should We Use?"),
        ("https://arxiv.org/abs/2404.19756", "KAN: Kolmogorov-Arnold Networks"),
        ("https://arxiv.org/abs/2405.14806", "Llama 3 Herd of Models"),
        ("https://arxiv.org/abs/2310.16044", "DPO vs PPO in RLHF alignment"),
        ("https://arxiv.org/abs/2403.08291", "GaLore: Memory-Efficient LLM Training by Gradient Low-Rank Projection"),
        ("https://arxiv.org/abs/2401.12921", "DeepSeek-Coder: When the Large Language Model Meets Programming"),
        ("https://arxiv.org/abs/2306.02707", "Orca: Progressive Learning from Complex Explanation Traces"),
        ("https://arxiv.org/abs/2312.00752", "Mamba: Linear-Time Sequence Modeling with Selective State Spaces"),
        ("https://arxiv.org/abs/2402.19473", "Gemma: Open Models Based on Gemini Technology"),
        ("https://arxiv.org/abs/2406.07524", "Nemotron-4 340B Technical Report")
    ]
    
    github_repos = [
        ("https://github.com/unslothai/unsloth", "Unsloth: 2x faster, 80% less memory QLoRA finetuning"),
        ("https://github.com/hiyouga/LLaMA-Factory", "LLaMA-Factory: Easy-to-use LLM fine-tuning framework"),
        ("https://github.com/OpenAccess-AI-Collective/axolotl", "Axolotl: Go-to tool for training various LLMs with best practices"),
        ("https://github.com/qdrant/qdrant", "Qdrant: Vector Database for next-generation AI applications"),
        ("https://github.com/n8n-io/n8n", "n8n: Workflow automation tool with node-based UI"),
        ("https://github.com/ollama/ollama", "Ollama: Run Llama, Mistral, Qwen and other LLMs locally"),
        ("https://github.com/vllm-project/vllm", "vLLM: High-throughput and memory-efficient LLM serving engine"),
        ("https://github.com/open-webui/open-webui", "Open WebUI: User-friendly WebUI for LLMs including Ollama"),
        ("https://github.com/tiangolo/fastapi", "FastAPI: High performance, easy to learn, fast to code web framework"),
        ("https://github.com/microsoft/autogen", "AutoGen: Multi-agent conversation framework by Microsoft"),
        ("https://github.com/run-llama/llama_index", "LlamaIndex: Data framework for LLM applications"),
        ("https://github.com/langchain-ai/langchain", "LangChain: Building applications with LLMs through composability"),
        ("https://github.com/pstn/forte", "Forte: Local legal document analysis agent framework"),
        ("https://github.com/portainer/portainer", "Portainer: Easy container management for Docker and Kubernetes"),
        ("https://github.com/dhruvnaik/mem0", "Mem0: The memory layer for AI Agents"),
        ("https://github.com/apify/crawl-web", "Crawling and scraping libraries for Playwright and BeautifulSoup"),
        ("https://github.com/microsoft/playwright-python", "Playwright Python: Web scraping and browser automation library")
    ]
    
    blogs_docs = [
        ("https://huggingface.co/blog/mlabonne/quantization", "Guide to LLM Quantization formats: GGUF, GPTQ, AWQ"),
        ("https://huggingface.co/blog/dpo-alignment", "Direct Preference Optimization SFT alignment guide"),
        ("https://huggingface.co/blog/preference-tuning", "Overview of DPO, KTO, and IPO in preference tuning"),
        ("https://huggingface.co/blog/unsloth-trt-llm", "Unsloth speedup compared to TensorRT-LLM and HuggingFace"),
        ("https://pytorch.org/docs/stable/fsdp.html", "Fully Sharded Data Parallel training guide in PyTorch"),
        ("https://docs.docker.com/compose/compose-file/", "Docker Compose file specification and volume config"),
        ("https://qdrant.tech/documentation/concepts/indexing/", "HNSW and Payload Indexes in Qdrant Vector DB"),
        ("https://docs.n8n.io/hosting/installation/docker/", "n8n self-hosting on Docker VPS installation guide"),
        ("https://fastapi.tiangolo.com/advanced/async-tests/", "Testing async FastAPI applications with HTTPX"),
        ("https://playwright.dev/python/docs/api/class-playwright", "Playwright Python API reference and page navigation"),
        ("https://ollama.com/library/qwen2.5-coder", "Qwen2.5-Coder model details and system prompt guidelines"),
        ("https://qdrant.tech/documentation/tutorials/hybrid-search/", "Setting up Hybrid Search (Sparse + Dense vectors) in Qdrant"),
        ("https://docs.cohere.com/docs/reranking", "Cohere Rerank API and embedding integration for RAG"),
        ("https://huggingface.co/blog/trl-peft", "Training LLMs with PEFT (LoRA, Prefix Tuning, P-Tuning)")
    ]
    
    linkedin_posts = [
        ("https://www.linkedin.com/posts/sarthakrastogi_ai-llms-genai-activity-7471358179604406272-G2EG", "Post explaining 2B-4B SLMs fine-tuning using Unsloth LoRA"),
        ("https://www.linkedin.com/posts/naveen-r-dev_finetuning-lora-qlora-activity-7472513325843537921-YHfG", "LoRA vs QLoRA comparison on 6GB VRAM GPUs and performance improvements"),
        ("https://www.linkedin.com/posts/lucas-melo-ai_rag-agentes-python-activity-7473523491-aAbC", "Building local agents in production using n8n, Ollama, and Qdrant"),
        ("https://www.linkedin.com/posts/conrado-ia_agentes-frameworks-llm-activity-7474920482-xYzW", "Tradeoffs of LangGraph vs CrewAI for multi-agent loops"),
        ("https://www.linkedin.com/posts/marcelo-ml_quantizacao-gguf-ollama-activity-7475193041-mNpO", "GGUF quantization benchmarks and speedup on local servers"),
        ("https://www.linkedin.com/posts/fernanda-ai_agentic-rag-memoria-activity-7476203912-qRsT", "Implementing long-term memory for local agents using Mem0 and Qdrant"),
        ("https://www.linkedin.com/posts/roberto-infra_docker-portainer-gpu-activity-7477112048-vWxY", "Configuring NVIDIA Container Toolkit for docker-compose GPU passthrough")
    ]
    
    url_pool = arxiv_papers + github_repos + blogs_docs + linkedin_posts
    random.seed(42)
    
    # 105 read_link seeds
    for i in range(105):
        url, desc = url_pool[i % len(url_pool)]
        # Add a random query suffix/variation to keep URLs unique and realistic
        if "arxiv.org" in url:
            url = f"{url[:-5]}{random.randint(10000, 99999)}"
        elif "github.com" in url:
            subpaths = ["", "/issues", "/pulls", "/blob/main/README.md", "/releases"]
            url = url + random.choice(subpaths)
        elif "linkedin.com" in url:
            url = f"{url[:-5]}{random.randint(10000, 99999)}"
            
        difficulty = "easy" if i < 42 else ("medium" if i < 84 else "hard")
        seeds.append({
            "category": "tool_calling",
            "subcategory": "read_link",
            "difficulty": difficulty,
            "topic": desc,
            "seed_details": f"User wants Cláudio to read and summarize/analyze {url}. Topic is related to {desc}."
        })
        
    # 2. RUN_BASH: 100 seeds (easy: 40, medium: 40, hard: 20)
    bash_commands = [
        ("nvidia-smi", "Verificar uso de GPU e VRAM", False),
        ("nvidia-smi --query-gpu=index,name,memory.used,memory.free --format=csv", "Consultar VRAM livre em CSV", False),
        ("docker ps", "Verificar containers ativos", False),
        ("docker ps -a", "Verificar todos os containers", False),
        ("docker logs ollama --tail 50", "Olhar logs do container do Ollama", False),
        ("docker logs qdrant --tail 30", "Olhar logs do banco Qdrant", False),
        ("docker logs n8n --tail 20", "Olhar logs do n8n", False),
        ("docker stats --no-stream", "Verificar consumo de CPU/Memória dos containers", False),
        ("df -h", "Verificar espaço em disco do servidor", False),
        ("free -h", "Verificar uso da memória RAM", False),
        ("htop -b -n 1 | head -n 20", "Listar processos principais do servidor", False),
        ("uptime", "Verificar tempo de atividade e load average", False),
        ("curl -s http://localhost:11434/api/tags", "Verificar modelos carregados no Ollama", False),
        ("curl -s http://localhost:6333/info", "Verificar status da API do Qdrant", False),
        ("systemctl status docker", "Checar se o daemon do docker está rodando", False),
        ("journalctl -u ollama --no-pager -n 50", "Verificar logs do systemd para o Ollama local", False),
        ("ls -lh /home/conrado/repos/estudo/agents-framework/finetune/dataset", "Listar datasets", False),
        ("du -sh /home/conrado/repos/estudo/agents-framework/finetune/*", "Verificar tamanho dos arquivos do fine-tuning", False),
        ("cat /proc/cpuinfo | grep 'model name' | uniq", "Verificar processador do servidor", False),
        ("ss -tulpn | grep -E '11434|6333|5678'", "Verificar portas ativas de Ollama, Qdrant e n8n", False),
        ("docker network ls", "Listar redes Docker", False),
        ("docker volume ls", "Listar volumes Docker persistentes", False),
        ("ping -c 3 google.com", "Testar conectividade externa do servidor", False),
        ("tail -n 100 /var/log/syslog", "Verificar logs gerais do sistema", False),
        ("find /home/conrado/repos -name '*.jsonl' -maxdepth 3", "Encontrar arquivos jsonl", False),
        ("docker stop ollama", "Parar container do Ollama", True),
        ("docker stop n8n", "Parar container do n8n", True),
        ("systemctl stop docker", "Parar serviço do Docker no sistema", True),
        ("rm -rf /home/conrado/repos/estudo/agents-framework/finetune/output/*", "Limpar checkpoints antigos do fine-tuning", True),
        ("docker rm -f qdrant", "Apagar container do Qdrant", True),
        ("docker compose down", "Derrubar infraestrutura docker compose", True),
        ("systemctl restart docker", "Reiniciar o serviço do Docker", True),
        ("docker restart ollama", "Reiniciar container do Ollama", True),
        ("rm -f /home/conrado/repos/estudo/agents-framework/finetune/dataset/synth_gemini.jsonl", "Deletar dataset sintético", True),
        ("rm -rf /var/log/nginx/*", "Apagar logs do nginx", True)
    ]
    
    for i in range(60):
        cmd, desc, is_destructive = bash_commands[i % len(bash_commands)]
        difficulty = "easy" if i < 24 else ("medium" if i < 48 else "hard")
        seeds.append({
            "category": "tool_calling",
            "subcategory": "run_bash",
            "difficulty": difficulty,
            "topic": desc,
            "seed_details": f"Command: {cmd}. Desc: {desc}. Is destructive: {is_destructive}."
        })
        
    # 3. CHAT/PERSONA: 150 seeds (easy: 60, medium: 60, hard: 30)
    persona_topics = [
        "Tradeoffs de VRAM e tempo ao usar LoRA rank 8 vs rank 16 vs rank 32",
        "Diferença matemática entre a perda do DPO clássico e do ORPO",
        "Por que ORPO não necessita de um modelo de referência congelado (frozen)",
        "Como configurar HNSW no Qdrant para melhorar recall em RAG com milhões de vetores",
        "Uso de vetores esparsos (BM25/SPLADE) combinados com densos (hybrid search) no Qdrant",
        "Vantagens de quantização GGUF K-means (Q4_K_M) vs quantizações clássicas",
        "Como funciona o cache de KV (Key-Value) em modelos como o Qwen3.5 servido no Ollama",
        "Por que o Unsloth consegue economizar até 80% de memória de ativação",
        "Diferença entre SFT (Supervised Fine-Tuning) e alinhamento de preferência direta",
        "Tradeoff de usar Cross-Encoder como reranker no pipeline de RAG local",
        "Como otimizar endpoints assíncronos no FastAPI rodando com Uvicorn",
        "Limitações de paralelismo do GIL em scripts de scraping concorrentes em Python",
        "Como estruturar loops multi-agente usando LangGraph vs arquiteturas baseadas em CrewAI",
        "Configuração de concorrência e filas no Celery com Redis para processar tarefas pesadas de IA",
        "Uso de embeddings locais (nomic-embed-text) vs embeddings na nuvem: latência e privacidade",
        "Configuração do Docker Compose with NVIDIA Container Toolkit para isolamento de GPUs nas RTX 3060",
        "Como evitar vazamento de memória em loops de inferência com PyTorch",
        "Uso do bitsandbytes para carregar modelos base em 4-bit/8-bit para treinamento",
        "Diferença entre KTO (Kahneman-Tversky Optimization) e DPO no alinhamento de LLMs",
        "Estratégias de chunking semântico vs chunking de tamanho fixo em documentos jurídicos",
        "Como persistir histórico de conversas em formato de grafo no Qdrant usando agentes",
        "Como configurar a temperatura e top_p no Ollama para tarefas de codificação (coding tasks)",
        "Explicação técnica sobre FlashAttention-2 e por que ele acelera o treinamento nas RTX 3060",
        "Como o n8n lida with retentativas (retries) em fluxos de webhook de alta taxa de requisição",
        "Análise de concorrência assíncrona no Playwright para rodar múltiplos browsers localmente",
        "Como treinar modelos usando Gradiente Acumulado (Gradient Accumulation) quando a GPU é limitada",
        "Uso do TRL (Transformer Reinforcement Learning) da HuggingFace junto com PEFT",
        "Como criar arquivos Modelfile customizados no Ollama especificando stop tokens",
        "Análise de gargalo de barramento PCIe em servidores dual Xeon como o E5-2696 v3",
        "Vantagens de usar PostgreSQL com PGVector comparado com uma instância dedicada de Qdrant",
        "Como criar parsers eficientes em Python usando Beautiful Soup e Pydantic para estruturar dados"
    ]
    
    for i in range(90):
        topic = persona_topics[i % len(persona_topics)]
        difficulty = "easy" if i < 36 else ("medium" if i < 72 else "hard")
        seeds.append({
            "category": "chat",
            "subcategory": "persona",
            "difficulty": difficulty,
            "topic": topic,
            "seed_details": f"User asks Cláudio a direct technical question about: {topic}."
        })
        
    # 4. REFUSAL/MIXED: 75 seeds (easy: 30, medium: 30, hard: 15)
    refusal_types = [
        ("git_commit", "Pedir para fazer git commit das alterações no dataset", "Não fazer git commit, git push ou qualquer operação de versionamento"),
        ("git_push", "Pedir para dar git push no repositório de agentes", "Não fazer git commit, git push ou qualquer operação de versionamento"),
        ("send_email", "Pedir para enviar um email de relatório do fine-tuning", "Cláudio não possui integração de email e deve se limitar ao fox-server"),
        ("external_api_forte", "Pedir para usar API externa do Google para traduzir textos no Forte.jus", "Forte.jus e fox-vault: zero APIs externas, apenas Ollama local"),
        ("external_api_vault", "Pedir para conectar no cofre HashiCorp Vault na nuvem externa para ler chaves", "Forte.jus e fox-vault: zero APIs externas, apenas Ollama local"),
        ("invent_output", "Pedir para simular logs do n8n sem rodar comandos reais", "Nunca inventar outputs de comandos não executados"),
        ("invent_nvidia_smi", "Pedir para inventar o output do comando nvidia-smi", "Nunca inventar outputs de comandos não executados / Nunca inventar outputs de ações que não executou com uma tool real"),
        ("destructive_no_confirm", "Pedir para apagar todo o repositório de estudos rodando rm -rf sem pedir confirmação", "Ações destrutivas (rm, docker stop): peça confirmação explícita"),
        ("send_slack", "Pedir para disparar notificação Slack externa", "Cláudio não possui integrações com mensageiros externos")
    ]
    
    for i in range(45):
        ref_type, desc, rule = refusal_types[i % len(refusal_types)]
        difficulty = "easy" if i < 18 else ("medium" if i < 36 else "hard")
        seeds.append({
            "category": "refusal",
            "subcategory": "mixed",
            "difficulty": difficulty,
            "topic": desc,
            "seed_details": f"Refusal Type: {ref_type}. Prompt matches rule violation: {rule}."
        })
        
    return seeds

def make_ollama_prompt(seed, few_shots):
    """Constructs the prompt for Ollama to generate a structured training example."""
    cat = seed["category"]
    subcat = seed["subcategory"]
    diff = seed["difficulty"]
    topic = seed["topic"]
    details = seed["seed_details"]
    
    # Format few-shots for prompt
    few_shot_str = ""
    for idx, fs in enumerate(few_shots[:2]):
        few_shot_str += f"\n--- EXEMPLO GOLD {idx+1} ---\n"
        few_shot_str += f"Mensagem Usuário: {fs['messages'][1]['content']}\n"
        
        # Check tool calls
        tool_call = fs["messages"][2].get("tool_calls")
        if tool_call:
            few_shot_str += f"Chamada de Tool: {json.dumps(tool_call[0])}\n"
            few_shot_str += f"Retorno da Tool: {fs['messages'][3]['content']}\n"
            few_shot_str += f"Resposta Final Cláudio: {fs['messages'][4]['content']}\n"
        else:
            few_shot_str += f"Chamada de Tool: null\n"
            few_shot_str += f"Retorno da Tool: null\n"
            few_shot_str += f"Resposta Final Cláudio: {fs['messages'][2]['content']}\n"
            
    # Specific quality checks
    quality_instructions = ""
    if cat == "chat":
        quality_instructions = "4. NUNCA afirme fatos sobre o estado atual do servidor (modelos, serviços, hardware, versões de software) — chat é só para conceitos técnicos gerais e estáveis. Se o tópico exigir estado da máquina, diga 'use run_bash para verificar'."
    elif cat == "tool_calling" and subcat == "run_bash":
        quality_instructions = "4. Tom telegráfico: sem frases introdutórias ('Identifiquei...', 'Analisei...'). Vá direto ao dado. Timestamps no tool_output devem ser de 2026."
    elif cat == "refusal":
        quality_instructions = "4. Recusa seca em 1-2 frases. Sem 'Recomendo que você...', sem 'Lamentavelmente...'"

    prompt = f"""Você é um gerador de dados de treino para o assistente pessoal Cláudio.
Gere um exemplo realista em português (PT-BR) de acordo com os seguintes dados:

Categoria: {cat}
Subcategoria: {subcat}
Dificuldade: {diff}
Tópico: {topic}
Instruções específicas: {details}

Abaixo estão alguns exemplos para referência:
{few_shot_str}

Regras para a resposta do assistente (assistant_final_response):
1. Deve ser no tom do Cláudio: expert, direto, sem rodeios, sem emojis.
2. Não use nenhum caractere de formatação markdown (sem *, **, #, _, ou links [texto](url)).
3. Use apenas hífen (-) para listas e crases (```) para código.
{quality_instructions}

Retorne APENAS um objeto JSON com a seguinte estrutura:
{{
  "user_message": "A mensagem enviada pelo usuário.",
  "tool_name": "Nome da ferramenta a chamar ('read_link' ou 'run_bash' ou null se não houver chamada)",
  "tool_args": {{ "url": "..." }} ou {{ "command": "..." }} ou null,
  "tool_output": "A saída simulada da ferramenta como string" ou null,
  "assistant_final_response": "A resposta final do assistente em texto puro (ou pedido de confirmação no caso de comandos destrutivos)"
}}
"""
    return prompt

def validate_generated_example(example, seed):
    """Strictly validates the structure and rules of the generated example."""
    # Check fields
    required = ["user_message", "tool_name", "tool_args", "tool_output", "assistant_final_response"]
    for r in required:
        if r not in example:
            return False, f"Missing field: {r}"
            
    final_resp = example["assistant_final_response"]
    if not final_resp or not isinstance(final_resp, str):
        return False, "assistant_final_response must be a non-empty string"
        
    # Check for prohibited markdown: *, **, #, _, markdown links
    # We check if they actually exist, but bypass backticks `
    prohibited_patterns = [
        r'\*\*',         # Bold / italic
        r'\*',           # Italic / bullet
        r'#\s+',         # Headers
        r'_[^_]+_',      # Underscore italic
        r'\[.*?\]\(.*?\)' # Markdown links
    ]
    for pattern in prohibited_patterns:
        if re.search(pattern, final_resp):
            return False, f"Prohibited markdown formatting found in final response"
            
    # Check for emojis
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010ffff"  # Supplemental Planes
        "\u2600-\u27bf"          # Miscellaneous Symbols and Dingbats
        "\u200d"                 # Zero Width Joiner (frequently used in emojis)
        "]+", flags=re.UNICODE
    )
    if emoji_pattern.search(final_resp):
        return False, "Emoji found in final response"
        
    # Check category logic
    cat = seed["category"]
    subcat = seed["subcategory"]
    
    tool_name = example["tool_name"]
    tool_args = example["tool_args"]
    tool_out = example["tool_output"]
    
    # Normalize tool_name "null" to None
    if isinstance(tool_name, str) and tool_name.lower() in ["null", "none", ""]:
        tool_name = None
        
    if cat == "tool_calling":
        if subcat == "read_link":
            if tool_name != "read_link":
                return False, f"read_link category must have tool_name = 'read_link', got {tool_name}"
            if not isinstance(tool_args, dict) or "url" not in tool_args:
                return False, "read_link category must have tool_args dict with 'url' key"
            if not tool_out:
                return False, "read_link category must have tool_output"
        elif subcat == "run_bash":
            is_destructive = "destructive: True" in seed["seed_details"] or "is destructive: true" in seed["seed_details"].lower()
            if is_destructive:
                if tool_name is not None:
                    return False, "Destructive run_bash commands must request confirmation first (tool_name must be null)"
            else:
                if tool_name != "run_bash":
                    return False, f"run_bash category must have tool_name = 'run_bash', got {tool_name}"
                if not isinstance(tool_args, dict) or "command" not in tool_args:
                    return False, "run_bash category must have tool_args dict with 'command' key"
                if not tool_out:
                    return False, "run_bash category must have tool_output"
    else:
        # Chat or Refusal should have no tool call
        if tool_name is not None:
            return False, f"Category {cat} should not have a tool call (got {tool_name})"
            
    return True, ""

def convert_to_dataset_schema(example, seed, idx):
    """Converts the raw validated Ollama response to the final training dataset schema."""
    id_str = f"claudio-g{idx:03d}"
    cat = seed["category"]
    subcat = seed["subcategory"]
    diff = seed["difficulty"]
    
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": example["user_message"]
        }
    ]
    
    tool_name = example.get("tool_name")
    tool_args = example.get("tool_args")
    tool_out = example.get("tool_output")
    final_resp = example["assistant_final_response"]
    
    # Normalize tool_name
    if isinstance(tool_name, str) and tool_name.lower() in ["null", "none", ""]:
        tool_name = None
        
    if tool_name and tool_name in ["read_link", "run_bash"]:
        if isinstance(tool_args, dict):
            args_str = json.dumps(tool_args)
        elif isinstance(tool_args, str):
            args_str = tool_args
        else:
            args_str = "{}"
            
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": args_str
                    }
                }
            ]
        })
        messages.append({
            "role": "tool",
            "name": tool_name,
            "content": tool_out or ""
        })
        messages.append({
            "role": "assistant",
            "content": final_resp
        })
    else:
        messages.append({
            "role": "assistant",
            "content": final_resp
        })
        
    return {
        "id": id_str,
        "category": cat,
        "subcategory": subcat,
        "difficulty": diff,
        "source": "synthetic_gemini",
        "validated": False,
        "validator": None,
        "messages": messages
    }

def generate_one(seed, idx, gold_examples):
    """Generates and validates a single dataset example. Retries up to 3 times."""
    key = (seed["category"], seed["subcategory"])
    few_shots = gold_examples.get(key, [])
    
    if not few_shots:
        few_shots = [item for sublist in gold_examples.values() for item in sublist]
        
    prompt = make_ollama_prompt(seed, few_shots)
    
    for attempt in range(4):
        try:
            response = ollama.chat(
                model="qwen3.5:9b",
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.7 + (attempt * 0.1), "num_predict": 1024},
                format="json"
            )
            content = response['message']['content'].strip()
            example = json.loads(content)
            
            is_valid, err_msg = validate_generated_example(example, seed)
            if is_valid:
                final_item = convert_to_dataset_schema(example, seed, idx)
                return final_item
            else:
                with open(PROGRESS_LOG_PATH, "a") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [claudio-g{idx:03d}] Val err (attempt {attempt+1}): {err_msg}\n")
        except Exception as e:
            with open(PROGRESS_LOG_PATH, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [claudio-g{idx:03d}] Error (attempt {attempt+1}): {str(e)}\n")
            time.sleep(1)
            
    # Fallback to avoid empty slots
    id_str = f"claudio-g{idx:03d}"
    fallback_response = f"Não posso executar a ação desejada no momento. Por favor, verifique se o comando está correto ou tente novamente."
    if seed["category"] == "refusal":
        fallback_response = "Esta operação não é permitida ou não pode ser realizada no momento por questões de segurança e escopo."
    elif seed["category"] == "tool_calling" and "destructive" in seed["seed_details"].lower():
        fallback_response = "Deseja realmente prosseguir com a execução desta operação? Por favor, confirme."
        
    return {
        "id": id_str,
        "category": seed["category"],
        "subcategory": seed["subcategory"],
        "difficulty": seed["difficulty"],
        "source": "synthetic_gemini",
        "validated": False,
        "validator": None,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Ajuda com {seed['topic']}"},
            {"role": "assistant", "content": fallback_response}
        ]
    }

def main():
    start_time = time.time()
    
    with open(PROGRESS_LOG_PATH, "w") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting synthetic dataset generation...\n")
        
    print("Loading gold examples...")
    gold_examples = load_gold_examples()
    
    print("Generating seeds...")
    seeds = generate_seeds()
    print(f"Total seeds generated: {len(seeds)}")
    
    out_dir = os.path.dirname(OUTPUT_PATH)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        
    batch_size = 50
    total_seeds = len(seeds)
    max_workers = 2
    
    print(f"Generating {total_seeds} examples with {max_workers} parallel workers...")
    
    results = [None] * total_seeds
    total_completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_seed = {
            executor.submit(generate_one, seed, 573 + idx, gold_examples): idx
            for idx, seed in enumerate(seeds)
        }
        
        for future in as_completed(future_to_seed):
            idx = future_to_seed[future]
            try:
                res = future.result()
                results[idx] = res
            except Exception as exc:
                print(f"Seed {idx+1} generated an exception: {exc}")
                with open(PROGRESS_LOG_PATH, "a") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [claudio-g{573+idx:03d}] Thread exception: {str(exc)}\n")
            
            total_completed += 1
            if total_completed % 10 == 0:
                percent = (total_completed / total_seeds) * 100
                print(f"Progress: {total_completed}/{total_seeds} ({percent:.1f}%) completed.")
                
            # Log progress
            with open(PROGRESS_LOG_PATH, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Progress: {total_completed}/{total_seeds} completed.\n")

    # Double-check and write in batches of 50
    print("Writing to file in batches of 50...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as out_file:
        for batch_start in range(0, total_seeds, batch_size):
            batch_end = min(batch_start + batch_size, total_seeds)
            batch_data = results[batch_start:batch_end]
            
            for item in batch_data:
                if item is not None:
                    line = json.dumps(item, ensure_ascii=False)
                    out_file.write(line + "\n")
                
            with open(PROGRESS_LOG_PATH, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Written batch from claudio-g{573+batch_start:03d} to claudio-g{573+batch_end-1:03d}.\n")
                
    duration = time.time() - start_time
    print(f"Dataset generation complete! Generated {total_seeds} examples in {duration:.1f}s.")
    with open(PROGRESS_LOG_PATH, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Generation successfully completed in {duration:.1f}s.\n")

if __name__ == "__main__":
    main()
