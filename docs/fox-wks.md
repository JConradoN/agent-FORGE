# fox-wks — Worker Node Windows 11

Máquina Windows 11 integrada ao lab como worker de inferência e workspace isolado.

**Reformatado/reinstalado:** 2026-06-27

## Hardware

| Item | Detalhe |
|---|---|
| Host | FOX-WKS |
| IP | 192.168.88.202 (LAN) / lease fixo MikroTik |
| OS | Windows 11 Pro Build 26200.8655 (x64) |
| Placa-mãe | ASRock Z590 Pro4 (Intel Z590, LGA1200) — BIOS P2.10 |
| CPU | Intel Core i5-10400F 6c/12t @ 2.90 GHz (Turbo 4.3 GHz, 65W TDP) |
| RAM | **48 GB** DDR4-2667 Dual Channel — 4 slots: A1 8GB Kingston + A2 16GB + B1 8GB Kingston + B2 16GB |
| GPU | NVIDIA RTX 3060 **12 GB** GDDR6 — Driver 610.62, PCIe Gen3 |
| NVMe (C:) | WD Green SN3000 1TB — ~831 GB livres |
| HD SATA (D:) | WD WD10SPZX-75Z10T2 1TB — D: DADOS HD, ~916 GB livres, workspace do worker |
| NIC principal | RTL8153 USB Ethernet (Ethernet 2) — MAC 00-E0-4C-68-15-95 |
| NIC secundária | MAC A8-A1-59-72-90-F6 — IP 192.168.100.40 (NIO) |
| Usuário admin | morph |

## Serviços em execução (NSSM — auto-start)

| Serviço | Porta | Detalhe |
|---|---|---|
| `llama-server` | 8082 | TurboQuant qwen3.5-9b-q4km, **262k ctx**, turbo3 KV cache, mmproj F16 visão, **66 tok/s** |
| `open-webui` | **8080** | Interface web, DATA_DIR=`C:\open-webui-data`, launcher `C:\start-open-webui.bat` |
| `fox-terminal` | 9900 | FastAPI + PowerShell, Bearer auth `foxwks-terminal-2026` |

### Configuração llama-server (NSSM)

```
C:\llama.cpp\llama-server.exe
  -m C:\llama.cpp\models\qwen3.5-9b-q4km.gguf
  --mmproj C:\llama.cpp\models\mmproj-qwen3.5-9b-F16.gguf
  -ngl 99 -c 262144
  --cache-type-k turbo3 --cache-type-v turbo3
  --flash-attn auto --parallel 1
  --host 0.0.0.0 --port 8082
  --chat-template-file C:\llama.cpp\qwen35_no_think.jinja
  --metrics
```

Thinking desabilitado globalmente via Jinja2 (`{%- set enable_thinking = false %}`).
Visão ativa — mmproj F16 carregado, ~9.9 GB VRAM total (modelo + KV cache 262k).

### Configuração open-webui (NSSM)

Launcher: `C:\start-open-webui.bat` (usar `scp` do fox-server para editar — `echo >>` adiciona trailing spaces)

```batch
@echo off
set DATA_DIR=C:\open-webui-data
set OPENAI_API_BASE_URL=http://localhost:8082/v1
set OPENAI_API_KEY=sk-none
set WEBUI_SECRET_KEY=At5b7bUUNHfARMDA
set ENABLE_OLLAMA_API=False
set ENABLE_BASE_MODELS_CACHE=False
set FRONTEND_BUILD_DIR=C:\open-webui-venv\Lib\site-packages\open_webui\frontend
C:\open-webui-venv\Scripts\open-webui.exe serve
```

Admin: `jconrado@gmail.com` / `foxwks2026`

**Nota:** `open-webui serve` ignora `PORT` env var — porta hardcoded 8080.
**Nota:** Config do terminal em `C:\open-webui-data\webui.db` (tabela config, chave `terminal_server.connections`, estrutura JSON aninhada — não usar chave dotted literal).

### Configuração fox-terminal (NSSM)

Código: `agents/wks-worker/fox_terminal_server.py`
FastAPI + PowerShell, workspace D:\\, auth via primeira mensagem WebSocket `{"type":"auth","token":"foxwks-terminal-2026"}`.
Endpoints: `/api/config`, `/api/terminals`, `/files/list`, `/files/read`, `/files/write`, `/ports`.

## Workspace D:\

O modelo tem acesso isolado ao D:\ — **nunca pode tocar C:\\**.

Isolamento via `os.path.normpath(os.path.abspath(path)).upper().startswith("D:\\")`.

## Open WebUI — Tool `fox_wks_system`

Código: `agents/wks-worker/tool_fox_wks_system.py`
Update: copiar para `C:\Users\morph\fox_wks_tool.py` e rodar `C:\Users\morph\update_tool_db.py`.

**Confirmado em produção:** `write_file` criou `D:\teste_tools.txt` via prompt (2026-06-28).

### Funções disponíveis (13)

| Função | Descrição |
|---|---|
| `get_full_health()` | Saúde completa: OS, CPU, RAM, GPU, disco D |
| `get_system_info()` | OS, CPU, RAM |
| `get_gpu_info()` | GPU: temperatura, uso, VRAM, wattagem |
| `list_directory(path)` | Lista **diretório** em D:\ (passar o DIRETÓRIO PAI, nunca um arquivo) |
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

```bash
forge-wks "qual a saúde do fox-wks?"
LLAMACPP_HOST=http://192.168.88.202:8082 python3 src/agentforge/cli/main.py run --agent-dir agents/wks-worker --input "<pergunta>"
```

## SSH fox-server → fox-wks

```bash
ssh morph@192.168.88.202
```

## Notas de implementação

- **RAM real: 48 GB** (4 DIMMs) — WMI reportava 32 GB por limitação de leitura anterior
- **GPU WMI reporta 4 GB** (limitação de API 32-bit) — real: 12 GB (confirmado nvidia-smi)
- **Windows 11 vs 10**: `platform.release()` retorna `"10"`. Detectar via build ≥ 22000.
- **trailing spaces em batch**: `echo >>` via SSH/cmd adiciona espaços antes do CRLF, corrompendo env vars (DATA_DIR inválido para SQLite). Usar `scp` do fox-server para criar/editar batch files.
- **`--reasoning-budget 0`** trava o llama-server — usar template Jinja2 com `enable_thinking = false`.
- **Open WebUI roda como SYSTEM**: env vars configuradas via batch file (não NSSM AppEnvironmentExtra).
- **Terminal WebSocket**: proxy técnico funciona (testado), mas frontend fecha — pendente investigação.
- **RAM em ~42% sem WSL**: Windows + llama-server 262k ctx + Open WebUI + fox-terminal ≈ 20 GB.
