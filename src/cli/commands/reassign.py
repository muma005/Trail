"""
CLI commands for verification and reassignment.
Phase 7: trail verify today/--date, trail reassign --dry-run/--accept
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
            console.print(f"\n[dim]Run: trail reassign --dry-run to see proposed changes[/dim]")

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


@click.group()
def reassign():
    """Reassign incomplete tasks to future plans."""
    pass


@reassign.command("preview")
@click.option("--date", "target_date", default=None, help="Date to reassign from (YYYY-MM-DD).")
def reassign_preview(target_date: str):
    """Preview proposed reassignments without applying."""
    try:
        init_db()
        from src.services.verification.auto_reassignment import run_reassignment

        target = date.fromisoformat(target_date) if target_date else date.today()
        result = run_reassignment(target_date=target, dry_run=True)

        if result["status"] == "no_tasks":
            console.print(f"[green]{result['message']}[/green]")
            return

        console.print(f"\n[bold cyan]Reassignment Preview ({target})[/bold cyan]")
        console.print(f"  [dim]Tasks to reassign:[/dim] {len(result['tasks'])}")
        console.print(f"  [dim]Total remaining:[/dim] {result['total_remaining_minutes']} min")

        if result["tasks"]:
            table = Table()
            table.add_column("Task", style="green")
            table.add_column("Progress", justify="right")
            table.add_column("Remaining", justify="right")

            for t in result["tasks"]:
                table.add_row(
                    t["task_title"][:40],
                    f"{t['progress']:.0f}%",
                    f"{t['remaining_minutes']} min",
                )

            console.print(table)
            console.print(f"\n[dim]Run: trail reassign apply --date {target}[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@reassign.command("apply")
@click.option("--date", "target_date", default=None, help="Date to reassign from (YYYY-MM-DD).")
@click.option("--force", is_flag=True, default=False, help="Apply without confirmation.")
def reassign_apply(target_date: str, force: bool):
    """Apply proposed reassignments."""
    try:
        init_db()
        from src.services.verification.auto_reassignment import run_reassignment

        target = date.fromisoformat(target_date) if target_date else date.today()

        if not force:
            if not click.confirm(f"Apply reassignments for {target}?"):
                console.print("[yellow]Cancelled.[/yellow]")
                return

        result = run_reassignment(target_date=target, dry_run=False, force=force)

        if result["status"] == "no_tasks":
            console.print(f"[green]{result['message']}[/green]")
            return

        console.print(f"\n[bold green]✓ Reassignment applied[/bold green]")
        console.print(f"  [dim]Tasks reassigned:[/dim] {len(result['tasks'])}")
        console.print(f"  [dim]Total remaining:[/dim] {result['total_remaining_minutes']} min")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
