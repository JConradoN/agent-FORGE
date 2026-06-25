# fox-wks — Worker Node Windows 11

Máquina Windows 11 integrada ao lab como worker de inferência e workspace isolado.

## Hardware

| Item | Detalhe |
|---|---|
| Host | FOX-WKS |
| IP | 192.168.88.202 (LAN) / Tailscale 100.98.0.128 |
| OS | Windows 11 (build 26200) |
| CPU | Intel i5-10400F 6c/12t |
| RAM | 32 GB |
| GPU | NVIDIA RTX 3060 12 GB |
| Disco workspace | D:\ (~930 GB livres) |

## Serviços em execução (NSSM)

| Serviço | Porta | Detalhe |
|---|---|---|
| `llama-server` | 8082 | TurboQuant qwen3.5-9b-q4km, 131k ctx, turbo3 KV cache |
| `open-webui` | 3001 | Interface web conectada ao llama-server |

### Configuração llama-server (NSSM)

```
C:\llama.cpp\llama-server.exe
  -m C:\llama.cpp\models\qwen3.5-9b-q4km.gguf
  -ngl 99 -c 131072
  --cache-type-k turbo3 --cache-type-v turbo3
  --flash-attn auto --parallel 1
  --host 0.0.0.0 --port 8082
  --chat-template-file C:\llama.cpp\qwen35_no_think.jinja
```

Thinking desabilitado globalmente via template Jinja2 (`{%- set enable_thinking = false %}`).

### Configuração open-webui (NSSM)

```
C:\open-webui-venv\Scripts\open-webui.exe serve --host 0.0.0.0 --port 3001

Env vars:
  DATA_DIR=C:\Users\morph\.open-webui
  OPENAI_API_BASE_URL=http://localhost:8082/v1
  OPENAI_API_KEY=sk-none
  WEBUI_SECRET_KEY=At5b7bUUNHfARMDA
```

Usuário admin: `jconrado@gmail.com`

## Workspace D:\

O modelo tem acesso isolado ao D:\ — **nunca pode tocar C:\\**.

Isolamento implementado via `os.path.normpath(os.path.abspath(path)).upper().startswith("D:\\")` em todas as operações de arquivo.

## Open WebUI — Tool `fox_wks_system`

Código fonte em `agents/wks-worker/tool_fox_wks_system.py`.
Atualizar no banco: copiar para `C:\Users\morph\fox_wks_tool.py` e rodar `update_tool_db.py`.

### Funções disponíveis (13)

| Função | Descrição |
|---|---|
| `get_full_health()` | Saúde completa: OS (Win11 detectado), CPU, RAM, GPU, disco D |
| `get_system_info()` | OS, CPU, RAM |
| `get_gpu_info()` | GPU: temperatura, uso, VRAM, wattagem |
| `list_directory(path)` | Lista D:\ ou subdiretório |
| `create_directory(path)` | Cria dir em D:\ (inclusive subpastas) |
| `write_file(path, content)` | Grava qualquer texto em D:\ (html, py, md, json...) |
| `read_file(path)` | Lê arquivo em D:\ |
| `delete_file(path)` | Deleta arquivo em D:\ |
| `delete_directory(path)` | Deleta dir e conteúdo em D:\ |
| `run_powershell(command)` | PowerShell read-only no fox-wks |
| `fox_server_health()` | Saúde do fox-server via SSH (CPU, RAM, disco, GPU, containers) |
| `read_agent_memory(limit)` | Lê memórias do agent-mesh do fox-server |
| `write_agent_memory(key, value)` | Grava memória no agent-mesh (fonte: fox-wks) |

### SSH fox-wks → fox-server

- Chave privada: `C:\ProgramData\open-webui-ssh\id_rsa`
- Usuário/host: `conrado@192.168.88.200`
- Chave pública adicionada em `/home/conrado/.ssh/authorized_keys`

## AgentForge — agente `wks-worker`

Agente leve para tarefas básicas usando o modelo do fox-wks como backend de inferência.

### Uso

```bash
forge-wks "qual a saúde do fox-wks?"
forge-wks "qual a saúde do fox-server?"
forge-wks --agent <outro-agente> "<pergunta>"
```

O script `~/bin/forge-wks` define `LLAMACPP_HOST=http://192.168.88.202:8082` e invoca o AgentForge CLI.

### Tool `collect_wks_health`

Coleta via SSH (fox-server → fox-wks):
- CPU e RAM via PowerShell remoto (`Get-CimInstance Win32_OperatingSystem`)
- GPU via `nvidia-smi`
- Disco D:\ via `Get-PSDrive`
- Status do llama-server via HTTP GET `/health`

### Usar fox-wks como backend em qualquer agente

```bash
LLAMACPP_HOST=http://192.168.88.202:8082 \
PYTHONPATH=src \
python3 src/agentforge/cli/main.py run --agent-dir agents/<agente> --input "<pergunta>"
```

## SSH fox-server → fox-wks

Acesso direto já disponível: `ssh morph@192.168.88.202`

## Notas de implementação

- **Windows 11 vs 10**: `platform.release()` retorna `"10"` no Windows 11. Detectar via build number: `build >= 22000` = Windows 11.
- **Tool syntax no Open WebUI**: usar arquivo `.py` separado + script de update para evitar problemas com triple-quotes no SQLite.
- **`--reasoning-budget 0`** trava o llama-server — usar template Jinja2 com `enable_thinking = false`.
- **Open WebUI roda como SYSTEM**: env vars devem ser configuradas via NSSM `AppEnvironmentExtra`, não em perfil de usuário.
