# Tool System

## Overview

The tool system is AgentForge's mechanism for giving agents the ability to interact with the outside world — read files, execute commands, call APIs, send messages, and even create new tools.

Tools are registered in a global registry and exposed to models via OpenAI-compatible function schemas.

## Tool Registry

**Location**: `src/agentforge/tools/registry.py`

The registry is a simple global dict:

```python
_ToolRegistry: dict[str, Callable] = {}
```

Key operations:
| Function | Description |
|----------|-------------|
| `register_tool(name, func, **default_kwargs)` | Register a callable with optional default kwargs |
| `get_tool(name)` | Retrieve a callable by name |
| `execute_tool(name, **kwargs)` | Execute a tool, returning result or None |
| `list_tools()` | List all registered tool names |
| `_register_builtin_tools()` | Auto-register all builtins at startup |

Tools can have default kwargs injected via `functools.partial` — e.g., `read_log_tail` has `log_path="/var/log/syslog"` pre-bound.

### Built-in Tools

Registered at startup in `_register_builtin_tools()`:

| Tool | File | Description |
|------|------|-------------|
| `collect_system_health` | `system_health.py` | CPU, memory, disk, GPU, process metrics |
| `collect_wks_health` | `wks_health.py` | Windows workstation health (fox-wks worker) |
| `read_log_tail` | `read_log_tail.py` | Last lines of a log file (default: /var/log/syslog) |
| `scan_directory` | `vault_scan.py` | Directory scanning in vault workspace |
| `extract_file_content` | `vault_extract.py` | Extract file content from vault |
| `run_agent` | `run_agent.py` | Multi-agent delegation tool |
| `http_get` | `http_get.py` | HTTP GET request |
| `write_file` | `write_file.py` | Write content to file in agent working directory |
| `read_file` | `write_file.py` | Read content from file |
| `append_file` | `write_file.py` | Append to file |
| `run_bash` | `run_bash.py` | Bash execution with destructive command blocklist |
| `send_claudio` | `send_claudio.py` | Send notification via Claudio Telegram bot |
| `fetch_social_url` | `fetch_social.py` | Fetch social media URLs |
| `register_tool_file` | `register_tool_file.py` | Register a new Python tool at runtime |
| `tts_omnivoice` | `tts_omnivoice.py` | Text-to-speech via OmniVoice |
| `heygen_credits` | `heygen_mcp.py` | HeyGen API credits check |
| `heygen_video_agent` | `heygen_mcp.py` | HeyGen video agent |
| `heygen_get_agent_session` | `heygen_mcp.py` | HeyGen agent session |
| `heygen_video_creator` | `heygen_mcp.py` | HeyGen video creator |
| `heygen_upload_audio` | `heygen_mcp.py` | HeyGen audio upload |
| `heygen_upload_image` | `heygen_mcp.py` | HeyGen image upload |
| `heygen_create_photo_avatar` | `heygen_mcp.py` | HeyGen photo avatar creation |
| `heygen_poll_avatar_ready` | `heygen_mcp.py` | HeyGen avatar ready polling |
| `heygen_list_avatars` | `heygen_mcp.py` | HeyGen avatar listing |
| `heygen_get_video` | `heygen_mcp.py` | HeyGen video retrieval |
| `heygen_wallet_report` | `heygen_wallet.py` | HeyGen wallet report |

### Tool Registration Order

Built-in tools are registered first, then dynamic tools are loaded after. This ensures the builtin `register_tool_file` is available when agents create new tools.

## Dynamic Tool Loader

**Location**: `src/agentforge/tools/dynamic_loader.py`

Loads tools from the `tool_registry/` directory on startup. Tools created by agents persist across sessions via this mechanism.

## Tool Self-Registration (Voyager Pattern)

**Location**: `src/agentforge/tools/register_tool_file.py`

Agents can create new tools at runtime using the Voyager pattern:

```
1. Agent writes implementation.py via write_file()
2. Agent writes test_implementation.py via write_file()
3. Agent runs pytest via run_bash()
4. Agent calls register_tool_file(implementation.py, test_implementation.py)
   → Validates test results
   → Copies implementation to tool_registry/
   → Updates tool_registry/registry.yaml
   → Tool is available to all agents immediately (re-load or next session)
```

The `register_tool_file` tool validates:
- Test file exists
- Tests pass (exit code 0)
- Implementation is valid Python
- Tool name matches filename

## Tool Spec in Agent Spec

Tools available to an agent are declared in `agent.yaml` under `tools:`:

```yaml
tools:
  - name: collect_system_health
    required: true
    description: "Collects CPU, RAM, disk, and GPU metrics"
    when_to_use: "Whenever the user asks about server status"
    when_not_to_use: "Do not use for questions about specific logs"
    input_schema: '{"type":"object","properties":{},"required":[]}'
```

The schema fields map to `ToolSpec` Pydantic model fields:

- `name` — must match a registered tool
- `required` — marks the tool as mandatory for this agent
- `description` — shown to the model in tool schema
- `when_to_use` — decision hint injected into description
- `when_not_to_use` — negative hint to reduce incorrect calls
- `input_schema` — JSON schema string for the model's arguments
- `output_schema` — expected output format description

## Tool Schema to Model

When a tool-calling agent runs, the engine builds an OpenAI-compatible tool schema:

```python
schema.append({
    "type": "function",
    "function": {
        "name": tool.name,
        "description": description + " Use when: " + when_to_use + " Do not use when: " + when_not_to_use,
        "parameters": json.loads(input_schema),
    },
})
```

This schema is passed to the provider's chat endpoint, and the model decides which tools to call based on the task.

## Special Tools

### run_agent (Multi-Agent Delegation)

**Location**: `src/agentforge/tools/run_agent.py`

When an agent declares workers in `workflow.agents`, the engine injects `run_agent` as a tool:

```python
run_agent(agent_dir: str, input: str) → str
```

The engine:
1. Loads the worker's `agent.yaml` and `runtime.yaml`
2. Creates a temporary `AgentRuntime` for the worker
3. Calls `runtime.run(input)`
4. Returns the worker's output

The orchestrator can then synthesize results from multiple workers.

### run_bash (with Guardrails)

**Location**: `src/agentforge/tools/run_bash.py`

Bash execution with a blocklist of destructive commands (rm, chmod, mkfs, dd, etc.). Prevents agents from accidentally destroying the system.

### write_file / read_file / append_file

**Location**: `src/agentforge/tools/write_file.py`

File operations restricted to the agent's working directory (`AGENT_WORKDIR`). Used extensively by agents for:
- Writing analysis reports
- Creating test files for self-registration
- Persisting outputs

### send_claudio

**Location**: `src/agentforge/tools/send_claudio.py`

Sends notifications via the Claudio Telegram bot. Used by agents to push alerts when tasks complete or anomalies are detected.

### HeyGen Tools

**Location**: `src/agentforge/tools/heygen_mcp.py`, `heygen_wallet.py`

A collection of HeyGen API tools for video generation, avatar creation, and wallet management. These integrate with HeyGen's MCP-compatible API.

### Vault Tools

**Location**: `src/agentforge/tools/vault_scan.py`, `vault_extract.py`

Tools for scanning and extracting content from the vault workspace. Used by the vault-pilot agent.

### system_health vs wks_health

| Tool | Target | Source |
|------|--------|--------|
| `collect_system_health` | Linux servers | `system_health.py` — psutil-based metrics |
| `collect_wks_health` | Windows workstations | `wks_health.py` — fox-wks worker integration |

## Source References

| File | Role |
|------|------|
| `src/agentforge/tools/registry.py` | Global tool registry, builtin registration |
| `src/agentforge/tools/dynamic_loader.py` | Load tools from `tool_registry/` |
| `src/agentforge/tools/register_tool_file.py` | Voyager self-registration |
| `src/agentforge/tools/run_agent.py` | Multi-agent delegation |
| `src/agentforge/tools/run_bash.py` | Bash execution with blocklist |
| `src/agentforge/tools/write_file.py` | File I/O in agent working directory |
| `src/agentforge/tools/http_get.py` | HTTP GET |
| `src/agentforge/tools/system_health.py` | Linux system health metrics |
| `src/agentforge/tools/wks_health.py` | Windows workstation health |
| `src/agentforge/tools/read_log_tail.py` | Log file tail |
| `src/agentforge/tools/send_claudio.py` | Telegram notification |
| `src/agentforge/tools/fetch_social.py` | Social media URL fetching |
| `src/agentforge/tools/tts_omnivoice.py` | Text-to-speech |
| `src/agentforge/tools/heygen_mcp.py` | HeyGen MCP tools |
| `src/agentforge/tools/heygen_wallet.py` | HeyGen wallet |
| `src/agentforge/tools/vault_scan.py` | Vault directory scanning |
| `src/agentforge/tools/vault_extract.py` | Vault file extraction |
| `tool_registry/` | Dynamically registered tools |
| `tool_registry/registry.yaml` | Tool registry manifest |
