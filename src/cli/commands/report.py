"""
CLI command for generating resumption reports.
Phase 3: Triggers multi-agent report pipeline and outputs Markdown.
"""
import sys

import click
from rich.console import Console

from src.config.settings import settings
from src.models.database.session import get_project_by_key, init_db
from src.services.report_generator.generator import ReportWorkflow
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def report():
    """Generate resumption reports for projects."""
    pass


@report.command("generate")
@click.argument("project_key")
@click.option("--format", "fmt", default="markdown", type=click.Choice(["markdown", "json", "text"]),
              help="Output format (default: markdown).")
@click.option("--output", "-o", default=None, help="Save report to this file.")
@click.option("--model", default=None, help="OpenRouter model to use.")
def generate(project_key: str, fmt: str, output: str, model: str):
    """
    Generate a resumption report for a project.

    Uses the multi-agent pipeline:
    Context Retriever → LLM Analyzer → Validator

    Falls back to raw data summary if OpenRouter is unavailable.
    """
    try:
        init_db()
        project = get_project_by_key(project_key)
        if not project:
            console.print(f"[bold red]Error:[/bold red] Project '{project_key}' not found.")
            sys.exit(1)

        console.print(f"[cyan]Generating report for: {project['name']}...[/cyan]")

        # Initialize workflow
        api_key = settings.openrouter_api_key if hasattr(settings, 'openrouter_api_key') else None
        workflow_model = model or (settings.openrouter_model if hasattr(settings, 'openrouter_model') else "anthropic/claude-3.5-sonnet")

        workflow = ReportWorkflow(
            openrouter_api_key=api_key,
            model=workflow_model,
        )

        # Generate report
        with console.status("[bold yellow]Generating report...[/bold yellow]"):
            report_text = workflow.generate(project["id"])

        # Format output
        from src.services.report_generator.context_retriever import ContextRetriever
        context = ContextRetriever().retrieve(project["id"])
        formatted_report = workflow.format_report(report_text, context, fmt=fmt)

        # Output
        if output:
            with open(output, "w") as f:
                f.write(formatted_report)
            console.print(f"[bold green]✓[/bold green] Report saved to [dim]{output}[/dim] ([dim]format: {fmt}[/dim])")
        else:
            if fmt == "json":
                # Pretty-print JSON
                console.print_json(formatted_report)
            else:
                console.print("\n" + formatted_report)

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
