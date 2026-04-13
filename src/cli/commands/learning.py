"""
CLI commands for learning and personalization.
Phase 8: trail learning show/update/reset/focus/empty-promise
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import init_db
from src.services.learning.engine import get_learning_engine
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def learning():
    """View and manage learned patterns (duration multipliers, focus peaks, etc.)."""
    pass


@learning.command("show")
def show_patterns():
    """Display all learned patterns."""
    try:
        init_db()
        engine = get_learning_engine()
        patterns = engine.get_all_patterns()
        engine.close()

        if not patterns:
            console.print("[yellow]No learned patterns yet. Complete some tasks first![/yellow]")
            return

        table = Table(title="Learned Patterns")
        table.add_column("Type", style="cyan")
        table.add_column("Context", style="dim")
        table.add_column("Value", justify="right")
        table.add_column("Confidence", justify="right")
        table.add_column("Samples", justify="right")
        table.add_column("Updated", style="dim")

        for p in patterns:
            ctx_str = ", ".join(f"{k}={v}" for k, v in p["context"].items())
            conf_pct = f"{p['confidence']:.0%}"
            table.add_row(
                p["pattern_type"],
                ctx_str or "—",
                f"{p['value']:.2f}",
                conf_pct,
                str(p["sample_count"]),
                p["updated_at"][:10],
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(patterns)} pattern(s)[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@learning.command("update-duration")
@click.option("--task-id", default=None, help="Specific task ID to learn from.")
@click.option("--project-id", default=None, help="Project ID to learn from.")
def update_duration(task_id: str, project_id: str):
    """Manually trigger duration learning for completed tasks."""
    try:
        init_db()
        engine = get_learning_engine()

        if task_id and project_id:
            result = engine.update_duration_multiplier(task_id, project_id)
            if result:
                console.print(f"[bold green]✓[/bold green] Multiplier updated: {result:.2f}")
            else:
                console.print("[yellow]No data to learn from this task.[/yellow]")
        else:
            # Auto-update all completed tasks without existing multipliers
            from src.models.database.base import SessionLocal
            from src.models.database.models import NotionTask

            db = SessionLocal()
            try:
                completed = (
                    db.query(NotionTask)
                    .filter(NotionTask.status.in_(("Done", "Completed")))
                    .all()
                )
                count = 0
                for task in completed:
                    if task.actual_minutes and task.estimated_minutes:
                        engine.update_duration_multiplier(str(task.id), str(task.project_id))
                        count += 1
                console.print(f"[bold green]✓[/bold green] Updated {count} task(s)")
            finally:
                db.close()

        engine.close()

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@learning.command("update-focus")
@click.option("--days", default=30, help="Number of days to analyze.")
def update_focus(days: int):
    """Recompute focus peaks from commit history."""
    try:
        init_db()
        engine = get_learning_engine()
        peaks = engine.update_focus_peaks(days_lookback=days)
        engine.close()

        if peaks:
            console.print(f"[bold green]✓[/bold green] Focus peaks updated: {peaks}")
            console.print("[dim]Deep work will be scheduled during these hours[/dim]")
        else:
            console.print("[yellow]No commits found to analyze. Using default focus hours (9-10 AM).[/yellow]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@learning.command("empty-promise")
@click.option("--project", "project_key", required=True, help="Project key to check.")
def check_empty_promise(project_key: str):
    """Check if a project's estimate was overly optimistic."""
    try:
        init_db()
        from src.models.database.base import SessionLocal
        from src.models.database.models import Project

        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.project_key == project_key).first()
            if not project:
                console.print(f"[bold red]Error:[/bold red] Project '{project_key}' not found.")
                sys.exit(1)

            engine = get_learning_engine()
            multiplier = engine.check_empty_promise(str(project.id))
            engine.close()

            if multiplier:
                console.print(
                    f"[bold yellow]⚠️ Over-optimism detected![/bold yellow]"
                )
                console.print(
                    f"  Project '{project_key}' actual time is [bold]{multiplier:.1f}×[/bold] the estimate."
                )
                console.print(
                    f"  [dim]Future plans will apply a {multiplier:.1f}× multiplier.[/dim]"
                )
            else:
                console.print(
                    f"[green]✓[/green] Project '{project_key}' estimates are on track."
                )

        finally:
            db.close()

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@learning.command("focus")
def show_focus():
    """Show current focus peaks."""
    try:
        init_db()
        engine = get_learning_engine()
        peaks = engine.get_focus_peaks()
        engine.close()

        peak_strs = [f"{h:02d}:00" for h in peaks]
        console.print(f"[bold]Focus Peaks:[/bold] {', '.join(peak_strs)}")
        console.print("[dim]Deep work tasks will be scheduled during these hours[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@learning.command("reset")
@click.option("--pattern-type", required=True, help="Pattern type to reset (e.g., duration_multiplier).")
def reset_patterns(pattern_type: str):
    """Reset learned patterns for a specific type."""
    try:
        init_db()
        engine = get_learning_engine()
        count = engine.reset_pattern(pattern_type)
        engine.close()

        console.print(f"[bold green]✓[/bold green] Reset {count} pattern(s) of type '{pattern_type}'")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
