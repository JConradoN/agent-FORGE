from __future__ import annotations

import json
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from agentforge.core.validation import validate_all_specs, validate_agent_spec

app = typer.Typer(help="agents-framework CLI")
console = Console()


@app.command()
def info() -> None:
    """Exibe informações básicas do projeto."""
    cwd = Path.cwd()
    console.print("[bold]agents-framework[/bold]")
    console.print("  Versão:    0.1.0")
    console.print("  Status:    bootstrap OK")
    console.print(f"  Diretório: {cwd}")


@app.command()
def validate(
    root: Path = typer.Option(Path("."), "--root", help="Raiz do projeto a validar"),
) -> None:
    """Valida os spec YAMLs do projeto."""
    results = validate_all_specs(root)

    table = Table(title="Validação de specs", show_lines=True)
    table.add_column("Arquivo", style="cyan", no_wrap=True)
    table.add_column("Tipo", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Erros")

    all_valid = True
    for r in results:
        status = "[green]OK[/green]" if r.valid else "[red]FALHOU[/red]"
        errors = "\n".join(r.errors) if r.errors else ""
        table.add_row(r.path, r.spec_type, status, errors)
        if not r.valid:
            all_valid = False

    console.print(table)

    if not all_valid:
        raise typer.Exit(code=1)


@app.command()
def wizard(
    root: Path = typer.Option(Path("."), "--root", help="Raiz do projeto"),
) -> None:
    """Wizard interativo para criar spec de agente."""
    from agentforge.wizard.flow import run_agent_wizard

    output_path = run_agent_wizard(root)
    console.print(f"\n[green]Spec do agente gerada em:[/green] {output_path}")


@app.command(name="validate-agent")
def validate_agent(
    path: Path = typer.Option(..., "--path", help="Caminho do agent.yaml a validar"),
) -> None:
    """Valida um agent.yaml."""
    try:
        spec = validate_agent_spec(path)
        console.print(f"[green]OK[/green] — {spec.agent.name} ({path})")
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        console.print(f"[red]FALHOU[/red] — {exc}")
        raise typer.Exit(code=1)


@app.command()
def generate(
    path: Path = typer.Option(..., "--path", help="Caminho do agent.yaml"),
) -> None:
    """Gera artefatos derivados de um agent.yaml."""
    from agentforge.generators.agent_files import generate_agent_files

    try:
        generated = generate_agent_files(path)
        for p in generated:
            console.print(f"  [green]gerado:[/green] {p}")
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        console.print(f"[red]ERRO[/red] — {exc}")
        raise typer.Exit(code=1)


@app.command()
def run(
    agent_dir: Path = typer.Option(Path("agents/claudio"), "--agent-dir", help="Diretório do agente"),
    input_text: str = typer.Option(..., "--input", help="Texto de entrada para o agente"),
    mode: str = typer.Option("raw", "--mode", help="Modo de saída: raw (JSON) ou pretty (human-readable)"),
) -> None:
    """Executa o agente usando o provider configurado."""
    from agentforge.providers.base import ProviderError
    from agentforge.providers.registry import ProviderNotImplementedError
    from agentforge.runtime.engine import AgentRuntime

    if mode not in ("raw", "pretty"):
        console.print(f"[red]Modo inválido:[/red] {mode}. Use 'raw' ou 'pretty'.")
        raise typer.Exit(code=1)

    try:
        runtime = AgentRuntime.from_agent_dir(agent_dir)
        result = runtime.run(input_text)

        if mode == "pretty":
            agent_id = result.get("agent_id", "unknown")
            output = result.get("output", "")
            console.print(f"[bold][{agent_id}][/bold]")
            console.print("")
            console.print(output)
        else:
            console.print_json(json.dumps(result))
    except ProviderNotImplementedError as exc:
        console.print(f"[red]Provider não disponível[/red] — {exc}")
        raise typer.Exit(code=1)
    except ProviderError as exc:
        console.print(f"[red]Erro no provider[/red] — {exc}")
        raise typer.Exit(code=1)
    except (FileNotFoundError, ValueError, ValidationError) as exc:
        console.print(f"[red]ERRO[/red] — {exc}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
