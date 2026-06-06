from __future__ import annotations


def run_agent(agent_dir: str, input: str) -> dict:
    """Loads an AgentRuntime and executes a task. Returns output and agent_id."""
    from agentforge.runtime.engine import AgentRuntime  # lazy — avoids circular import

    runtime = AgentRuntime.from_agent_dir(agent_dir)
    result = runtime.run(input)
    return {
        "agent_id": result["agent_id"],
        "output": result["output"],
    }
