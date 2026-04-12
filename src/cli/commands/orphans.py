"""
CLI command for listing unclassified commits (orphans).
Phase 1.5: Lists commits where needs_classification = True.
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import get_orphan_commits, init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def orphans():
    """List commits without parsed task IDs (orphans)."""
    pass


@orphans.command()
@click.option("--project", "project_key", default=None, help="Show orphans for this project only.")
def list(project_key: str):
    """
    List commits that need manual classification (no task ID found in message).

    Use --project to filter by a specific project key.
    """
    try:
        init_db()
        commits = get_orphan_commits(project_key)

        if not commits:
            msg = "No orphan commits found."
            if project_key:
                msg += f" (project: {project_key})"
            console.print(f"[green]{msg}[/green]")
            return

        table = Table(title="Orphan Commits (Need Classification)")
        table.add_column("Project", style="cyan", no_wrap=True)
        table.add_column("SHA", style="dim", no_wrap=True)
        table.add_column("Date", style="dim")
        table.add_column("Message", style="white")

        for c in commits:
            sha_short = c["sha"][:8]
            date_str = c["date"].strftime("%Y-%m-%d %H:%M") if c["date"] else "N/A"

            table.add_row(
                f"{c['project_key']}",
                sha_short,
                date_str,
                c["message"],
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(commits)} orphan commit(s)[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
