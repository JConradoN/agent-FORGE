from __future__ import annotations


def run_agent(agent_dir: str, input: str) -> dict:
    """Carrega um AgentRuntime e executa uma tarefa. Retorna output e agent_id."""
    from agentforge.runtime.engine import AgentRuntime  # lazy — evita import circular

    runtime = AgentRuntime.from_agent_dir(agent_dir)
    result = runtime.run(input)
    return {
        "agent_id": result["agent_id"],
        "output": result["output"],
    }
