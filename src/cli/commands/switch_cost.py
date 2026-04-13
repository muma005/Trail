"""
CLI commands for managing context switch costs.
Phase 6.5: trail switch-cost set/list
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def switch_cost():
    """Manage context switch penalties between projects."""
    pass


@switch_cost.command("set")
@click.option("--from", "from_project", required=True, help="Source project key.")
@click.option("--to", "to_project", required=True, help="Destination project key.")
@click.option("--minutes", required=True, type=int, help="Penalty in minutes.")
def set_cost(from_project: str, to_project: str, minutes: int):
    """Set switch cost between two projects."""
    try:
        init_db()
        from src.services.work_planner.context_switch import set_switch_cost

        # Look up project IDs
        from src.models.database.base import SessionLocal
        from src.models.database.models import Project

        db = SessionLocal()
        try:
            from_proj = db.query(Project).filter(Project.project_key == from_project).first()
            to_proj = db.query(Project).filter(Project.project_key == to_project).first()

            if not from_proj:
                console.print(f"[bold red]Error:[/bold red] Project '{from_project}' not found.")
                sys.exit(1)
            if not to_proj:
                console.print(f"[bold red]Error:[/bold red] Project '{to_project}' not found.")
                sys.exit(1)

            set_switch_cost(str(from_proj.id), str(to_proj.id), minutes)
            console.print(
                f"[bold green]✓[/bold green] Switch cost: {from_project} → {to_project} = {minutes} min"
            )
        finally:
            db.close()

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
