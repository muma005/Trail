"""
CLI command for showing task details.
Phase 2.5: Displays task info, sub-tasks, and dependencies.
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import get_task_details, init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def task():
    """View and manage tasks."""
    pass


@task.command("show")
@click.argument("task_id")
def show(task_id: str):
    """
    Display full details for a task.

    Shows title, status, priority, due date, progress, estimated minutes,
    size tag, sub-tasks (with completion), and dependencies.

    TASK_ID can be either the local UUID or the Notion page ID.
    """
    try:
        init_db()
        details = get_task_details(task_id)

        if not details:
            console.print(f"[bold red]Error:[/bold red] Task '{task_id}' not found.")
            sys.exit(1)

        # Header
        console.print(f"\n[bold cyan]Task: {details['title']}[/bold cyan]")
        console.print(f"  [dim]ID:[/dim] {details['notion_page_id'][:12]}...")

        # Details table
        info = Table.grid(padding=(0, 2))
        info.add_column(style="dim", width=18)
        info.add_column()

        info.add_row("Status:", details.get("status") or "—")
        info.add_row("Priority:", details.get("priority") or "—")
        due = details.get("due_date")
        info.add_row("Due Date:", str(due) if due else "—")
        progress = details.get("progress_percentage")
        info.add_row("Progress:", f"{progress}%" if progress is not None else "—")
        est = details.get("estimated_minutes")
        info.add_row("Estimate:", f"{est} min" if est is not None else "—")

        # Size tag with color coding
        size_tag = details.get("size_tag")
        if size_tag:
            size_colors = {"quick": "green", "medium": "yellow", "large": "red"}
            color = size_colors.get(size_tag, "white")
            info.add_row("Size:", f"[{color}]{size_tag}[/{color}]")
        else:
            info.add_row("Size:", "—")

        console.print(info)

        # Sub-tasks
        subtasks = details.get("sub_tasks", [])
        if subtasks:
            console.print(f"\n[bold]Sub-tasks ({len(subtasks)}):[/bold]")
            sub_table = Table(show_header=False, box=None, padding=(0, 2))
            sub_table.add_column("Status", width=4)
            sub_table.add_column("Title")

            for st in subtasks:
                checkbox = "[green]✓[/green]" if st["is_completed"] else "[dim]○[/dim]"
                sub_table.add_row(checkbox, st["title"])

            console.print(sub_table)

        # Dependencies
        deps = details.get("dependencies", [])
        if deps:
            console.print(f"\n[bold]Dependencies ({len(deps)}):[/bold]")
            for dep in deps:
                dep_type = dep.get("type", "blocks")
                dep_id = (dep.get("depends_on") or "unknown")[:12]
                console.print(f"  [dim]{dep_type}:[/dim] {dep_id}...")
        else:
            console.print(f"\n[dim]No dependencies.[/dim]")

        console.print()

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
