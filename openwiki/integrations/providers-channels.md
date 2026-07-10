# Providers & Channels

## Providers

Providers are the LLM backend abstraction. All providers implement `BaseProvider.generate(ProviderRequest) → ProviderResponse`.

### Provider Interface

```python
class BaseProvider(ABC):
    name: str
    
    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse: ...
```

**ProviderRequest** fields: `agent_id`, `input_text`, `system_prompt`, `model`, `history`, `metadata`, `tools_schema`.

**ProviderResponse** fields: `provider`, `model`, `output_text`, `raw_response`, `metadata`, `tool_calls`.

### Provider Registry

**Location**: `src/agentforge/providers/registry.py`

The `ProviderRegistry` class provides a registry pattern for backend providers:

```python
registry = ProviderRegistry()
registry.register("ollama", OllamaProvider)
registry.register("mock", MockProvider)
registry.register("llamacpp", LlamaCppProvider)
```

`get_default_registry()` returns the default registry with all three providers. New providers can be registered by subclassing `BaseProvider` and calling `registry.register(name, ProviderClass)`.

### Ollama Provider

**Location**: `src/agentforge/providers/ollama.py`

The primary backend, optimized for local Qwen3.5 models.

**Configuration**:
| Env Var | Default | Description |
|---------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TIMEOUT` | `900` | Request timeout in seconds |

**Endpoints**:
- `/api/generate` — Simple text generation (no history, no tools). Used for single-turn prompts.
- `/api/chat` — Chat with history, system prompt, and tool support. Uses OpenAI-compatible format.

**Special handling**:
1. **`think: false`**: Always sent in chat payloads to disable Qwen3 thinking mode (avoids empty `message.content`).
2. **Thinking fallback**: If `message.content` is empty but `message.thinking` exists, the thinking text is used as output.
3. **Regex tool call extraction**: If the API doesn't return tool_calls, regex patterns extract tool calls from output text.
4. **Empty message guard**: Empty user messages after tool results confuse qwen3.5:9b, so they're skipped.

### LlamaCpp Provider (TurboQuant)

**Location**: `src/agentforge/providers/llamacpp.py`

Alternative backend for local inference via llama.cpp / TurboQuant. Registered as `"llamacpp"` in the provider registry.

Used in fine-tuning benchmarks and as a fallback for Ollama-unavailable hardware.

### Mock Provider

**Location**: `src/agentforge/providers/mock.py`

Deterministic provider for testing. Returns pre-configured responses without any external API calls. Used by all 278 tests to run without Ollama.

## Channels

Channels are the user-facing interfaces through which agents receive input and return output. The same agent spec runs on all four channels without modification.

### CLI Channel

**Location**: `src/agentforge/cli/main.py`

The main entry point via Typer CLI. Commands:

| Command | Description |
|---------|-------------|
| `agentforge wizard` | Interactive agent spec creation |
| `agentforge generate --path <yaml>` | Generate artifacts from spec |
| `agentforge validate [--root .]` | Validate all framework specs |
| `agentforge validate-agent --path <yaml>` | Validate a single agent.yaml |
| `agentforge run --agent-dir <dir> --input <text> [--mode raw\|pretty]` | Run the agent |
| `agentforge eval --agent-dir <dir> --dataset <yaml>` | Evaluate agent with test dataset |
| `agentforge serve --agent-dir <dir> [--port 8080]` | Start HTTP server |
| `agentforge mcp [--transport stdio\|http]` | Start MCP server |
| `agentforge telegram --agent-dir <dir>` | Start Telegram bot |

The `run` command creates an `AgentRuntime` from the agent directory and calls `runtime.run(input_text)`.

### HTTP Channel

**Location**: `src/agentforge/channels/http.py`

FastAPI-based REST API server for integration with n8n and other automation tools.

**Endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/run` | Run agent with `{ "input": "text" }` |
| `GET` | `/health` | Health check |

The server is started via `agentforge serve` using `uvicorn.run(fast_app, host, port, reload)`.

### MCP Channel

**Location**: `src/agentforge/channels/mcp_server.py`

FastMCP server exposing agent tools to Claude Code and Claude Desktop.

**Transports**:
- `stdio` — Standard I/O (Claude Code integration). Started via `agentforge mcp --transport stdio`.
- `http` — HTTP/SSE server. Started via `agentforge mcp --transport http --port 8081`.

**Exposed tools**: `collect_system_health`, `read_log_tail`, `scan_directory`, `run_agent`, plus any tools configured in the connected agent spec.

**MCP Client**: `src/agentforge/channels/mcp_client.py` provides client-side MCP connectivity.

### Telegram Channel

**Location**: `src/agentforge/channels/telegram.py`

Async Telegram bot using polling mode. Starts via `agentforge telegram --agent-dir <dir> --token <token>` or `TELEGRAM_BOT_TOKEN` env var.

**Behavior**:
1. Receives text message from user
2. Creates `AgentRuntime` and runs the agent
3. Shows "typing..." status during processing
4. Sends reply with agent output
5. Signals in reply text if guardrails were triggered

## Configuration

### Provider Selection

Provider is selected at the agent level via `deployment.provider` in `agent.yaml`. Common values:

| Provider | Use Case |
|----------|----------|
| `ollama` | Default — local Ollama server |
| `llamacpp` | TurboQuant / llama.cpp inference |
| `mock` | Testing without external dependencies |

### Model Selection

Models are configured in `model_policy.default_model` and `model_policy.fallback_model` in `agent.yaml`. Environment variable `AGENTFORGE_MODEL` can override the default at runtime.

**Recommended models** (empirically validated):

| Model | VRAM | Speed | Use Case |
|-------|------|-------|----------|
| `qwen3.5:9b` | ~7 GB | ~45 tok/s | Monitoring, orchestration, simple queries |
| `qwen3.5:27b` | ~17 GB | ~25 tok/s | Coding with tests, multi-step analysis |

## Source References

| File | Role |
|------|------|
| `src/agentforge/providers/base.py` | `BaseProvider`, `ProviderRequest`, `ProviderResponse` |
| `src/agentforge/providers/registry.py` | `ProviderRegistry`, `get_default_registry()` |
| `src/agentforge/providers/ollama.py` | `OllamaProvider` — Ollama API integration |
| `src/agentforge/providers/llamacpp.py` | `LlamaCppProvider` — TurboQuant backend |
| `src/agentforge/providers/mock.py` | `MockProvider` — deterministic testing |
| `src/agentforge/channels/http.py` | `create_app()` — FastAPI HTTP server |
| `src/agentforge/channels/mcp_server.py` | `run_stdio()`, `run_http()` — MCP server |
| `src/agentforge/channels/mcp_client.py` | MCP client |
| `src/agentforge/channels/telegram.py` | `run_polling()` — Telegram bot |
| `src/agentforge/cli/main.py` | Typer CLI — all agentforge commands |
