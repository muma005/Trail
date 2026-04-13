"""
CLI commands for the work planner.
Phase 6: trail plan today, trail plan week, trail project estimate, trail project constraints
"""
import sys
from datetime import date, datetime
from decimal import Decimal

import click
from rich.console import Console
from rich.table import Table

from src.models.database.session import init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def plan():
    """View and generate work plans."""
    pass


@plan.command("today")
@click.option("--detail", is_flag=True, default=False, help="Show detailed timeline with time blocks.")
@click.option("--with-deps", is_flag=True, default=False, help="Show dependency resolution details.")
@click.option("--calendar", is_flag=True, default=False, help="Include Google Calendar events.")
def plan_today(detail: bool, with_deps: bool, calendar: bool):
    """
    Generate today's work plan.

    Shows allocated hours per project. Use --detail for a full timeline.
    Use --with-deps to see dependency resolution. Use --calendar for meeting blocks.
    """
    try:
        init_db()

        from src.services.work_planner.daily_generator import generate_daily_plan

        # Fetch calendar events if requested
        busy_slots = []
        if calendar:
            try:
                from src.integrations.calendar.google_calendar import GoogleCalendarClient
                cal = GoogleCalendarClient()
                busy_slots = cal.get_busy_slots_for_date(date.today())
                if busy_slots:
                    console.print(f"[dim]Found {len(busy_slots)} meeting(s) today[/dim]")
            except Exception as e:
                console.print(f"[yellow]⚠ Calendar unavailable: {e}[/yellow]")

        plan_data = generate_daily_plan(
            target_date=date.today(),
            detailed=detail,
            busy_slots=busy_slots,
            with_deps=with_deps,
        )

        if not plan_data["allocations"]:
            if plan_data.get("time_off"):
                console.print(f"[yellow]🏖️ {plan_data['date']} is a time-off day: {plan_data.get('reason', 'N/A')}[/yellow]")
            else:
                console.print("[yellow]No plan generated — no projects with remaining hours.[/yellow]")
            return

        # Summary header
        console.print(f"\n[bold cyan]Today's Plan ({plan_data['date']})[/bold cyan]")
        total = plan_data["total_minutes"]
        available = plan_data.get("available_minutes", 0)
        console.print(f"  [dim]Allocated: {total} min / {available} min available[/dim]")

        # Allocation summary
        summary = Table.grid(padding=(0, 2))
        summary.add_column(style="cyan", width=10)
        summary.add_column(style="green", width=30)
        summary.add_column(style="yellow", justify="right")

        for alloc in plan_data["allocations"]:
            hours = alloc["allocated_minutes"] / 60
            label = f"{'⭐ ' if alloc.get('is_constant') else ''}{alloc['project_key']}"
            summary.add_row(
                label,
                alloc["name"],
                f"{hours:.1f}h",
            )

        console.print(summary)

        # Detailed timeline
        if detail and plan_data["timeline"]:
            console.print(f"\n[bold]Detailed Timeline:[/bold]")
            timeline_table = Table()
            timeline_table.add_column("Time", style="dim")
            timeline_table.add_column("Type", width=10)
            timeline_table.add_column("Project", style="cyan", width=10)
            timeline_table.add_column("Task")

            for slot in plan_data["timeline"]:
                type_style = {
                    "Deep": "green",
                    "Shallow": "yellow",
                    "Lunch": "dim",
                    "Buffer": "dim",
                }.get(slot["type"], "white")

                project_display = slot.get("project", "")
                if slot.get("is_constant"):
                    project_display = f"⭐ {project_display}"

                timeline_table.add_row(
                    f"{slot['start']} – {slot['end']}",
                    f"[{type_style}]{slot['type']}[/{type_style}]",
                    project_display,
                    slot["task"][:50],
                )

            console.print(timeline_table)

        console.print()

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
