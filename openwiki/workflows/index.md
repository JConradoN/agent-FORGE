# Files

- [Execution Pipeline](execution-pipeline.md)
- [Multi-Agent Orchestration](multi-agent-orchestration.md) - How orchestrator agents delegate work to worker agents through the auto-injected run_agent tool, and how worker output is injected back into orchestrator history for synthesis.
- [Tool Self-Registration (Voyager Pattern)](tool-self-registration.md) - Walkthrough of the Voyager-pattern flow in which the tool-builder agent writes a Python tool, tests it with pytest, and permanently registers it via register_tool_file so dynamic_loader makes it available in every future session.
