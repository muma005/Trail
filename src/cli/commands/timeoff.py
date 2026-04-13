"""
CLI commands for managing time-off (holidays, PTO).
Phase 6.5: trail timeoff add/list/remove
"""
import sys
from datetime import date

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def timeoff():
    """Manage time-off days (holidays, PTO)."""
    pass


@timeoff.command("add")
@click.option("--start", required=True, help="Start date (YYYY-MM-DD).")
@click.option("--end", required=True, help="End date (YYYY-MM-DD).")
@click.option("--reason", default="", help="Reason for time-off.")
def add_timeoff(start: str, end: str, reason: str):
    """Add a time-off period."""
    try:
        init_db()
        from src.services.work_planner.holiday_manager import add_time_off

        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)

        record_id = add_time_off(start_date, end_date, reason)
        console.print(
            f"[bold green]✓[/bold green] Time-off added: {start} to {end} ({reason})"
        )
    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@timeoff.command("list")
def list_timeoff():
    """List upcoming time-off periods."""
    try:
        init_db()
        from src.services.work_planner.holiday_manager import list_time_off

        records = list_time_off(upcoming_only=True)
        if not records:
            console.print("[green]No upcoming time-off.[/green]")
            return

        table = Table(title="Upcoming Time-Off")
        table.add_column("Start", style="cyan")
        table.add_column("End", style="cyan")
        table.add_column("Reason")
        table.add_column("Working?", justify="center")

        for r in records:
            table.add_row(
                r["start_date"],
                r["end_date"],
                r["reason"] or "—",
                "Yes" if r["is_working"] else "No",
            )

        console.print(table)

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@timeoff.command("remove")
@click.option("--id", "record_id", required=True, help="Record ID to remove.")
def remove_timeoff(record_id: str):
    """Remove a time-off record by ID."""
    try:
        init_db()
        from src.services.work_planner.holiday_manager import remove_time_off

        success = remove_time_off(record_id)
        if success:
            console.print(f"[bold green]✓[/bold green] Time-off record {record_id} removed.")
        else:
            console.print(f"[yellow]Record {record_id} not found.[/yellow]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
