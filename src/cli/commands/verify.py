"""
CLI commands for verification.
Phase 7: trail verify today/--date
"""
import sys
from datetime import date

import click
from rich.console import Console

from src.models.database.session import init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def verify():
    """Verify planned work against actual activity."""
    pass


@verify.command("today")
def verify_today():
    """Run verification for today's planned tasks."""
    try:
        init_db()
        from src.services.verification.verifier import verify_today

        results = verify_today()
        console.print(f"\n[bold cyan]Verification Results (Today)[/bold cyan]")
        console.print(f"  [dim]Verified:[/dim] {results['verified']}")
        console.print(f"  [green]Completed:[/green] {results['completed']}")
        console.print(f"  [yellow]Partial:[/yellow] {results['partial']}")
        console.print(f"  [red]Missed:[/red] {results['missed']}")

        if results["partial"] > 0 or results["missed"] > 0:
            console.print(f"\n[dim]Run: trail reassign preview to see proposed changes[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@verify.command("date")
@click.option("--date", "target_date", required=True, help="Date to verify (YYYY-MM-DD).")
def verify_date_cmd(target_date: str):
    """Run verification for a specific date's planned tasks."""
    try:
        init_db()
        from src.services.verification.verifier import verify_date

        target = date.fromisoformat(target_date)
        results = verify_date(target)

        console.print(f"\n[bold cyan]Verification Results ({target})[/bold cyan]")
        console.print(f"  [dim]Verified:[/dim] {results['verified']}")
        console.print(f"  [green]Completed:[/green] {results['completed']}")
        console.print(f"  [yellow]Partial:[/yellow] {results['partial']}")
        console.print(f"  [red]Missed:[/red] {results['missed']}")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
