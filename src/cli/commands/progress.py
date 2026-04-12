"""
CLI command for showing project progress.
Phase 3: Displays simple and weighted progress with task breakdown.
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.core.enrichment.progress_calculator import (
    calculate_simple_progress,
    calculate_weighted_progress,
    get_commit_stats,
)
from src.models.database.session import get_project_by_key, init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def progress():
    """View project progress and statistics."""
    pass


@progress.command("show")
@click.argument("project_key")
def show(project_key: str):
    """
    Show current progress for a project.

    Displays simple progress (%), weighted progress (%), task breakdown,
    and recent commit activity.
    """
    try:
        init_db()
        project = get_project_by_key(project_key)
        if not project:
            console.print(f"[bold red]Error:[/bold red] Project '{project_key}' not found.")
            sys.exit(1)

        # Calculate progress
        simple = calculate_simple_progress(project["id"])
        weighted = calculate_weighted_progress(project["id"])
        commits = get_commit_stats(project["id"])

        # Header
        console.print(f"\n[bold cyan]Progress: {project['name']}[/bold cyan]")
        console.print(f"  [dim]Key:[/dim] {project['project_key']}")
        console.print(f"  [dim]Last synced:[/dim] {project.get('last_synced_at', 'Never')}")

        # Progress bars
        console.print(f"\n[bold]Simple Progress: {simple['completion_percentage']:.1f}%[/bold]")
        console.print(
            f"[{'█' * int(simple['completion_percentage'] / 5)}{'░' * (20 - int(simple['completion_percentage'] / 5))}]"
        )
        console.print(f"[bold]Weighted Progress: {weighted['weighted_percentage']:.1f}%[/bold]")
        console.print(
            f"[{'█' * int(weighted['weighted_percentage'] / 5)}{'░' * (20 - int(weighted['weighted_percentage'] / 5))}]"
        )

        # Task breakdown
        breakdown = Table.grid(padding=(0, 2))
        breakdown.add_column(style="dim", width=18)
        breakdown.add_column()

        breakdown.add_row("Total tasks:", str(simple["total_tasks"]))
        breakdown.add_row("Completed:", f"[green]{simple['completed_tasks']}[/green]")
        breakdown.add_row("In Progress:", f"[yellow]{simple['in_progress_tasks']}[/yellow]")
        breakdown.add_row("Blocked:", f"[red]{simple['blocked_tasks']}[/red]")
        breakdown.add_row("Not Started:", f"[dim]{simple['not_started_tasks']}[/dim]")

        console.print(f"\n[bold]Task Breakdown:[/bold]")
        console.print(breakdown)

        # Commit stats
        console.print(f"\n[bold]Commit Activity:[/bold]")
        console.print(f"  [dim]Total commits:[/dim] {commits['total_commits']}")
        console.print(f"  [dim]Lines added:[/dim] {commits['lines_added']}")
        console.print(f"  [dim]Lines deleted:[/dim] {commits['lines_deleted']}")

        # Recent commits
        if commits["recent_commits"]:
            console.print(f"\n[dim]Recent commits:[/dim]")
            for c in commits["recent_commits"][:5]:
                console.print(f"  [dim]{c['sha']}[/dim] {c['message']} ([dim]{c['date']}[/dim])")

        console.print()

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
