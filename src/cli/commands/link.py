"""
CLI command for reviewing commit-task link suggestions.
Phase 2: Lists embedding-based suggestions, allows accept/ignore.
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import (
    accept_suggestion,
    get_link_suggestions,
    ignore_suggestion,
    init_db,
)
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def link():
    """Manage commit-to-task links."""
    pass


@link.command("suggestions")
@click.option("--project", "project_key", default=None, help="Show suggestions for this project only.")
def suggestions(project_key: str):
    """
    List suggested commit-task links from embedding similarity.

    Shows commits without parsed task IDs that match Notion tasks by semantic similarity.
    Accept to create a permanent link (confidence=1.0), or ignore to dismiss.
    """
    try:
        init_db()
        suggestions_list = get_link_suggestions(project_key)

        if not suggestions_list:
            msg = "No link suggestions found."
            if project_key:
                msg += f" (project: {project_key})"
            console.print(f"[green]{msg}[/green]")
            return

        table = Table(title="Link Suggestions")
        table.add_column("Project", style="cyan", no_wrap=True)
        table.add_column("Commit SHA", style="dim", no_wrap=True)
        table.add_column("Commit Message", style="white")
        table.add_column("Task", style="green")
        table.add_column("Confidence", style="yellow", justify="right")
        table.add_column("Action", style="dim")

        for s in suggestions_list:
            sha_short = s["commit_sha"][:8]
            conf_pct = f"{s['confidence']:.0%}"

            table.add_row(
                s["project_key"],
                sha_short,
                s["commit_message"],
                s["task_title"][:30],
                conf_pct,
                "accept/ignore",
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(suggestions_list)} suggestion(s)[/dim]")
        console.print("[dim]Use: trail link accept <commit_sha> <task_page_id>[/dim]")
        console.print("[dim]Use: trail link ignore <commit_sha> <task_page_id>[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@link.command("accept")
@click.argument("commit_sha")
@click.argument("task_page_id")
def accept(commit_sha: str, task_page_id: str):
    """Accept a link suggestion (set confidence to 1.0)."""
    try:
        init_db()
        result = accept_suggestion(commit_sha, task_page_id)
        if result:
            console.print(f"[bold green]✓[/bold green] Link accepted: {commit_sha[:8]} → {task_page_id[:8]}")
        else:
            console.print(f"[yellow]No suggestion found for this commit/task pair.[/yellow]")
    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@link.command("ignore")
@click.argument("commit_sha")
@click.argument("task_page_id")
def ignore(commit_sha: str, task_page_id: str):
    """Ignore/delete a link suggestion."""
    try:
        init_db()
        result = ignore_suggestion(commit_sha, task_page_id)
        if result:
            console.print(f"[bold green]✓[/bold green] Suggestion ignored: {commit_sha[:8]} → {task_page_id[:8]}")
        else:
            console.print(f"[yellow]No suggestion found for this commit/task pair.[/yellow]")
    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
