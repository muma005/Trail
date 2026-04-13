"""
CLI commands for managing untracked work sessions.
Phase 7.5: trail untracked list/assign/ignore
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def untracked():
    """Manage untracked work sessions."""
    pass


@untracked.command("list")
def list_sessions():
    """Show unresolved untracked sessions."""
    try:
        init_db()
        from src.models.database.base import SessionLocal
        from src.models.database.models import UntrackedSession, Project

        db = SessionLocal()
        try:
            sessions = (
                db.query(UntrackedSession, Project.project_key, Project.name)
                .join(Project, UntrackedSession.project_id == Project.id)
                .filter(UntrackedSession.resolved == False)
                .order_by(UntrackedSession.created_at.desc())
                .all()
            )

            if not sessions:
                console.print("[green]No unresolved untracked sessions.[/green]")
                return

            table = Table(title="Untracked Sessions")
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("Project", style="cyan")
            table.add_column("Duration", justify="right")
            table.add_column("Detected", style="dim")
            table.add_column("Action", style="dim")

            for session, key, name in sessions:
                table.add_row(
                    str(session.id)[:8],
                    f"{key}: {name}",
                    f"{session.duration_minutes} min",
                    session.created_at.strftime("%Y-%m-%d %H:%M"),
                    "assign/ignore",
                )

            console.print(table)
            console.print(f"\n[dim]Total: {len(sessions)} unresolved session(s)[/dim]")
            console.print("[dim]Run: trail untracked assign --session-id ID --project KEY[/dim]")
            console.print("[dim]Run: trail untracked ignore --session-id ID[/dim]")

        finally:
            db.close()

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@untracked.command("assign")
@click.option("--session-id", required=True, help="Untracked session UUID.")
@click.option("--project", "project_key", required=True, help="Project key to assign to.")
def assign_session(session_id: str, project_key: str):
    """Assign an untracked session to a project."""
    try:
        init_db()
        from src.services.verification.plan_adjuster import resolve_session

        result = resolve_session(session_id, "assign", project_key)
        if result:
            console.print(
                f"[bold green]✓[/bold green] Session assigned to {project_key}"
            )
        else:
            console.print(f"[bold red]✗[/bold red] Failed to assign session")
            sys.exit(1)

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@untracked.command("ignore")
@click.option("--session-id", required=True, help="Untracked session UUID.")
def ignore_session(session_id: str):
    """Mark an untracked session as resolved without logging."""
    try:
        init_db()
        from src.services.verification.plan_adjuster import resolve_session

        result = resolve_session(session_id, "ignore")
        if result:
            console.print(f"[bold green]✓[/bold green] Session ignored")
        else:
            console.print(f"[bold red]✗[/bold red] Failed to ignore session")
            sys.exit(1)

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
