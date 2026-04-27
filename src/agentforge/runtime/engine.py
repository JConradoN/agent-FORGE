from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from agentforge.core.agent_models import AgentSpec, ToolSpec
from agentforge.core.validation import load_yaml_file, validate_agent_spec
from agentforge.providers.base import BaseProvider, ProviderRequest
from agentforge.providers.registry import get_default_registry
from agentforge.runtime.memory import apply_window, load_history, save_history
from agentforge.tools.registry import execute_tool


_TOOL_PREVIEW_PREFIX = """
<tool_results>
"""


def _summarize_scan_output(tool_data: dict, mode: str = "full", max_items: int = 20) -> dict:
    """
    Transforma o tool_data de scan_directory em diferentes formatos para benchmark.
    mode: "full" | "top_n" | "summary" | "by_folder" | "plain_text"

    Esta função NÃO altera o comportamento padrão do engine.
    Uso destinado exclusivamente a scripts de benchmark e testes internos.
    """
    files = tool_data.get("files", [])
    total = tool_data.get("file_count", len(files))
    base = tool_data.get("directory", "")

    if mode == "full":
        return tool_data

    if mode == "top_n":
        return {
            "directory": base,
            "file_count": total,
            "showing": min(max_items, total),
            "files": [
                {"path": f.get("path"), "extension": f.get("extension")}
                for f in files[:max_items]
            ],
        }

    if mode == "summary":
        from collections import Counter
        from pathlib import Path as _Path
        ext_count = Counter(f.get("extension") for f in files)
        folder_count = Counter(
            str(_Path(f.get("path") or "raiz").parent)
            for f in files
        )
        return {
            "directory": base,
            "total_files": total,
            "by_extension": dict(ext_count.most_common(10)),
            "by_folder": dict(folder_count.most_common(10)),
            "sample_files": [f.get("path") for f in files[:5]],
        }

    if mode == "by_folder":
        from collections import defaultdict
        folders: dict[str, list[str]] = defaultdict(list)
        for f in files:
            path = f.get("path") or ""
            parts = path.split("/")
            folder = "/".join(parts[:-1]) if len(parts) > 1 else "raiz"
            folders[folder].append(f.get("name") or path)
        return {
            "directory": base,
            "total_files": total,
            "folders": {
                k: {"count": len(v), "examples": v[:3]}
                for k, v in list(folders.items())[:15]
            },
        }

    if mode == "plain_text":
        lines = [f"Diretório: {base}", f"Total: {total} arquivos", ""]
        for f in files[:max_items]:
            lines.append(f"- {f.get('path')}")
        if total > max_items:
            lines.append(f"... e mais {total - max_items} arquivos")
        return {"_text": "\n".join(lines)}

    return tool_data


_TOKEN_THRESHOLD = 800  # heurístico baseado no V1


def _maybe_compress_tool_output(tool_data: dict, tool_name: str) -> dict:
    """
    Comprime tool outputs grandes automaticamente antes de injetar no prompt.
    Usado inicialmente no vault-pilot como PoC.
    """
    try:
        estimated_tokens = len(json.dumps(tool_data)) // 4
    except TypeError:
        return tool_data

    if estimated_tokens <= _TOKEN_THRESHOLD:
        return tool_data

    if tool_name == "scan_directory":
        return _summarize_scan_output(tool_data, mode="summary")

    if any(k in tool_data for k in ("files", "items", "results")):
        return _summarize_scan_output(tool_data, mode="top_n", max_items=20)

    return tool_data


def _build_input_with_file_content(
    input_text: str,
    file_text: str,
    mode: str = "current_tag",
    tool_prefix: str = "",
) -> str:
    """
    Monta o prompt injetando conteúdo de documento em diferentes formatos.
    mode: "current_tag" | "tool_response_tag" | "plain_block" |
          "instruction_strong" | "instruction_role" | "content_last" |
          "no_tag"

    Esta função NÃO altera o comportamento padrão do engine.
    Uso destinado exclusivamente a benchmarks e testes internos.
    """
    if mode == "current_tag":
        return f"{tool_prefix}<file_content>\n{file_text}\n</file_content>\n\nUser: {input_text}"

    if mode == "tool_response_tag":
        return f"{tool_prefix}<tool_response>\n{file_text}\n</tool_response>\n\nUser: {input_text}"

    if mode == "plain_block":
        return (
            f"{tool_prefix}CONTEÚDO DO ARQUIVO:\n"
            f"---\n{file_text}\n---\n\n"
            f"User: {input_text}"
        )

    if mode == "instruction_strong":
        return (
            f"{tool_prefix}NÃO chame nenhuma ferramenta. "
            f"Use APENAS o texto abaixo para responder.\n\n"
            f"{file_text}\n\n"
            f"User: {input_text}"
        )

    if mode == "instruction_role":
        return (
            f"{tool_prefix}Você recebeu o seguinte documento. "
            f"Analise-o sem chamar nenhuma ferramenta:\n\n"
            f"{file_text}\n\n"
            f"User: {input_text}"
        )

    if mode == "content_last":
        return (
            f"{tool_prefix}User: {input_text}\n\n"
            f"Conteúdo do documento:\n{file_text}"
        )

    if mode == "no_tag":
        return f"{tool_prefix}{file_text}\n\nUser: {input_text}"

    return f"{tool_prefix}{file_text}\n\nUser: {input_text}"


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_version: str
    agent_id: str
    provider: str
    model_default: str
    model_fallback: str | None = None
    workflow_mode: str
    channel_type: str
    memory_enabled: bool
    memory_type: str | None = None
    memory_max_turns: int = 0
    memory_policy: str = "truncate"
    output_mode: str
    output_format: str | None = None
    conversation_multi_turn: bool = False

    @model_validator(mode="before")
    @classmethod
    def _flatten_nested(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        model = values.get("model") or {}
        workflow = values.get("workflow") or {}
        channel = values.get("channel") or {}
        memory = values.get("memory") or {}
        output = values.get("output") or {}
        conversation = values.get("conversation") or {}
        return {
            "runtime_version": values.get("runtime_version", ""),
            "agent_id": values.get("agent_id", ""),
            "provider": values.get("provider", ""),
            "model_default": model.get("default", ""),
            "model_fallback": model.get("fallback"),
            "workflow_mode": workflow.get("mode", ""),
            "channel_type": channel.get("type", ""),
            "memory_enabled": memory.get("enabled", False),
            "memory_type": memory.get("type"),
            "memory_max_turns": memory.get("max_turns", 0),
            "memory_policy": memory.get("policy", "truncate"),
            "output_mode": output.get("mode", ""),
            "output_format": output.get("format"),
            "conversation_multi_turn": conversation.get("multi_turn", False),
        }


class AgentRuntime:
    def __init__(
        self,
        agent_spec: AgentSpec,
        runtime_config: RuntimeConfig,
        tools: list[ToolSpec],
        root_dir: Path,
    ) -> None:
        self.agent_spec = agent_spec
        self.runtime_config = runtime_config
        self.tools = tools
        self.root_dir = root_dir
        self.logger = logging.getLogger(__name__)

        # Load persisted history if memory is enabled; always start fresh for single-turn.
        if runtime_config.conversation_multi_turn:
            self._history: list[dict[str, str]] = load_history(
                root_dir,
                memory_type=runtime_config.memory_type or "none",
                enabled=runtime_config.memory_enabled,
                max_turns=runtime_config.memory_max_turns,
                policy=runtime_config.memory_policy,
            )
        else:
            self._history = []

    @classmethod
    def from_agent_dir(cls, path: str | Path) -> "AgentRuntime":
        root_dir = Path(path)
        agent_spec = validate_agent_spec(root_dir / "agent.yaml")

        runtime_data = load_yaml_file(root_dir / "runtime.yaml")
        runtime_config = RuntimeConfig.model_validate(runtime_data)

        tools: list[ToolSpec] = []
        tools_yaml = root_dir / "tools.yaml"
        if tools_yaml.exists():
            tools_data = load_yaml_file(tools_yaml)
            tools = [ToolSpec.model_validate(t) for t in (tools_data.get("tools") or [])]

        logging.getLogger(__name__).info(
            "Loaded agent '%s' from %s", agent_spec.agent.id, root_dir
        )
        return cls(
            agent_spec=agent_spec,
            runtime_config=runtime_config,
            tools=tools,
            root_dir=root_dir,
        )

    def _get_provider(self) -> BaseProvider:
        return get_default_registry().create(self.runtime_config.provider)

    def _read_system_prompt(self) -> str | None:
        path = self.root_dir / "system_prompt.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    def _execute_tool(self, tool_name: str) -> dict | None:
        return execute_tool(tool_name)

    def _build_input_with_tool_results(self, input_text: str, tool_data: dict) -> str:
        tool_json = json.dumps(tool_data, indent=2, default=str)
        return f"{_TOOL_PREVIEW_PREFIX}{tool_json}\n</tool_results>\n\nUser: {input_text}"

    def _build_input_with_tool_results_with_name(
        self, input_text: str, tool_data: dict, tool_name: str = ""
    ) -> str:
        tool_data = _maybe_compress_tool_output(tool_data, tool_name)

        if "_text" in tool_data:
            tool_content = tool_data["_text"]
        else:
            tool_json = json.dumps(tool_data, indent=2, default=str)
            tool_content = tool_json

        return f"{_TOOL_PREVIEW_PREFIX}{tool_content}\n</tool_results>\n\nUser: {input_text}"

    @property
    def history(self) -> list[dict[str, str]]:
        return list(self._history)

    def clear_history(self) -> None:
        self._history = []
        from agentforge.runtime.memory import clear_history
        clear_history(self.root_dir)

    def _detect_log_intent(self, input_text: str) -> bool:
        log_keywords = [
            "log",
            "syslog",
            "últimas linhas",
            "últimas linhas do",
            "erros recentes",
            "eventos recentes",
            "events",
            "ver log",
            "verificar log",
        ]
        lower_input = input_text.lower()
        return any(kw in lower_input for kw in log_keywords)

    def _detect_file_intent(self, input_text: str) -> bool:
        keywords = [
            "analise",
            "analisar",
            "conteúdo",
            "extraia",
            "extrair",
            "qual o conteúdo",
            "me explique",
            "descreva",
            "describe",
            "what is",
            "explain",
        ]
        lower = input_text.lower()
        return any(kw in lower for kw in keywords)

    def _extract_filename_intent(self, input_text: str) -> str | None:
        import re
        text = input_text
        
        m = re.search(r"([A-Z][a-zA-Z]+/[A-Za-z]+/[^\s]+\.(?:pdf|docx?|odt|pptx?))", text)
        if m:
            return m.group(1)
        
        m = re.search(r"([A-Z][a-zA-Z]+/[^\s]+\.(?:pdf|docx?|odt|pptx?))", text)
        if m:
            return m.group(1)
        
        m = re.search(r"([^\s]+\.(?:pdf|docx?|odt|pptx?))", text)
        if m:
            candidate = m.group(1)
            if len(candidate) > 10:
                return candidate
        return None

    def _detect_log_path(self, input_text: str) -> str:
        lower = input_text.lower()
        if "syslog" in lower:
            return "/var/log/syslog"
        if "kern" in lower:
            return "/var/log/kern.log"
        if "messages" in lower:
            return "/var/log/messages"
        return "/var/log/syslog"

    def run(self, input_text: str, *, metadata: dict | None = None) -> dict:
        provider = self._get_provider()

        tool_data = None
        final_input = input_text

        required_tool = next((t for t in self.tools if t.required), None)
        if required_tool:
            tool_data = self._execute_tool(required_tool.name)
            if tool_data:
                if self.runtime_config.agent_id == "vault-pilot":
                    final_input = self._build_input_with_tool_results_with_name(
                        input_text, tool_data, tool_name=required_tool.name
                    )
                else:
                    final_input = self._build_input_with_tool_results(input_text, tool_data)

        if self._detect_log_intent(input_text):
            log_tool = next((t for t in self.tools if t.name == "read_log_tail"), None)
            if log_tool:
                log_path = self._detect_log_path(input_text)
                log_data = execute_tool(log_tool.name, log_path=log_path)
                if log_data:
                    log_json = json.dumps(log_data, indent=2, default=str)
                    final_input = f"{final_input}\n\n<log_results>\n{log_json}\n</log_results>"

        if self._detect_file_intent(input_text):
            extract_tool = next((t for t in self.tools if t.name == "extract_file_content"), None)
            if extract_tool:
                filename = self._extract_filename_intent(input_text)
                if filename:
                    if not filename.startswith("/"):
                        filename = f"/home/conrado/testes/vault/input/{filename}"
                    file_data = execute_tool(extract_tool.name, file_path=filename)
                    if file_data and not file_data.get("error"):
                        file_json = json.dumps(file_data, indent=2, default=str)
                        final_input = f"{final_input}\n\n<file_content>\n{file_json}\n</file_content>"

        history = list(self._history) if self.runtime_config.conversation_multi_turn else []

        request = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text=final_input,
            system_prompt=self._read_system_prompt(),
            model=self.runtime_config.model_default,
            history=history,
        )

        self.logger.info(
            "run: agent=%s provider=%s model=%s turn=%d input=%r",
            self.runtime_config.agent_id,
            self.runtime_config.provider,
            self.runtime_config.model_default,
            len(history) // 2 + 1,
            input_text,
        )

        response = provider.generate(request)

        # Update in-memory history for multi-turn sessions.
        if self.runtime_config.conversation_multi_turn:
            self._history.append({"role": "user", "content": input_text})
            self._history.append({"role": "assistant", "content": response.output_text})
            self._history = apply_window(
                self._history,
                self.runtime_config.memory_max_turns,
                self.runtime_config.memory_policy,
            )
            if self.runtime_config.memory_enabled and self.runtime_config.memory_type != "none":
                save_history(self.root_dir, self._history)

        raw_response = response.raw_response
        if not self.runtime_config.conversation_multi_turn and raw_response and "context" in raw_response:
            raw_response = {k: v for k, v in raw_response.items() if k != "context"}

        return {
            "agent_id": self.runtime_config.agent_id,
            "provider": response.provider,
            "input": input_text,
            "output": response.output_text,
            "metadata": {
                "provider": self.runtime_config.provider,
                "workflow_mode": self.runtime_config.workflow_mode,
                "channel_type": self.runtime_config.channel_type,
                "model_default": self.runtime_config.model_default,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_executed": required_tool.name if required_tool else None,
                "tool_data": tool_data,
                "conversation_turn": len(self._history) // 2,
                **(metadata or {}),
            },
            "provider_response": {
                "provider": response.provider,
                "model": response.model,
                "raw_response": raw_response,
            },
        }

    def _run_with_tool_data(self, input_text: str, tool_data: dict) -> str:
        """
        Executa uma chamada ao modelo injetando tool_data pré-formatado,
        sem passar pela detecção automática de intent.

        Uso destinado exclusivamente a benchmarks e testes internos.
        NÃO use este método no pipeline de produção (CLI normal).
        NÃO altera o comportamento de run() nem do fluxo normal.
        """
        if "_text" in tool_data:
            tool_content = tool_data["_text"]
            prompt = f"{_TOOL_PREVIEW_PREFIX}{tool_content}\n</tool_results>\n\nUser: {input_text}"
        else:
            prompt = self._build_input_with_tool_results(input_text, tool_data)

        request = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text=prompt,
            system_prompt=self._read_system_prompt(),
            model=self.runtime_config.model_default,
            history=[],
        )
        provider = self._get_provider()
        response = provider.generate(request)
        return response.output_text

    def _run_with_file_content(
        self,
        input_text: str,
        file_text: str,
        mode: str = "current_tag",
        history: list | None = None,
    ) -> str:
        """
        Executa uma chamada ao modelo injetando conteúdo de documento
        em diferentes formatos, sem passar pela detecção automática de intent.

        history:
          - None → history vazio (mesmo comportamento do V2).
          - lista fornecida → usada diretamente; permite injetar histórico
            sintético para benchmarks de corrupção de contexto.

        Uso destinado exclusivamente a benchmarks e testes internos.
        NÃO use no pipeline de produção.
        """
        prompt = _build_input_with_file_content(
            input_text=input_text,
            file_text=file_text,
            mode=mode,
            tool_prefix="",
        )

        request = ProviderRequest(
            agent_id=self.runtime_config.agent_id,
            input_text=prompt,
            system_prompt=self._read_system_prompt(),
            model=self.runtime_config.model_default,
            history=history if history is not None else [],
        )
        provider = self._get_provider()
        response = provider.generate(request)
        return response.output_text
