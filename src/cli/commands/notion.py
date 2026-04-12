"""
CLI commands for Notion AI Agent.
Phase 5: trail notion poll, trail notion process
"""
import sys

import click
from rich.console import Console

from src.config.settings import settings
from src.models.database.session import init_db
from src.utils.exceptions.base import DatabaseError

console = Console()


@click.group()
def notion():
    """Manage the Notion AI Agent."""
    pass


@notion.command("poll")
def poll():
    """
    Scan tracked Notion databases for new @ai commands.

    Checks all active projects with Notion databases.
    New commands are stored with status='pending' for processing.
    """
    try:
        if not settings.notion_token:
            console.print("[bold red]Error:[/bold red] NOTION_TOKEN not set in .env")
            sys.exit(1)

        init_db()
        console.print("[cyan]Polling Notion for @ai commands...[/cyan]")

        from src.services.notion_agent.agent import poll_notion_commands
        count = poll_notion_commands()

        if count > 0:
            console.print(f"[bold green]✓[/bold green] Detected [yellow]{count}[/yellow] new command(s)")
            console.print("[dim]Run: trail notion process --all[/dim]")
        else:
            console.print("[green]No new commands found.[/green]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@notion.command("process")
@click.option("--command-id", default=None, help="Process a specific command by UUID.")
@click.option("--all", "process_all", is_flag=True, default=False, help="Process all pending commands.")
def process(command_id: str, process_all: bool):
    """
    Process pending @ai commands and write AI responses to Notion.

    Use --command-id to process a specific command.
    Use --all to process all pending commands.
    """
    try:
        if not settings.notion_token:
            console.print("[bold red]Error:[/bold red] NOTION_TOKEN not set in .env")
            sys.exit(1)

        init_db()

        from src.services.notion_agent.responder import NotionResponder
        responder = NotionResponder()

        if command_id:
            console.print(f"[cyan]Processing command {command_id}...[/cyan]")
            success = responder.process_single(command_id)
            if success:
                console.print("[bold green]✓[/bold green] Command processed successfully")
            else:
                console.print("[bold red]✗[/bold red] Failed to process command")
                sys.exit(1)
        elif process_all:
            console.print("[cyan]Processing all pending commands...[/cyan]")
            results = responder.process_all_pending()
            console.print(f"[bold green]✓[/bold green] Processed: {results['processed']}, Failed: {results['failed']}")
        else:
            console.print("[yellow]No action specified. Use --command-id <uuid> or --all[/yellow]")
            console.print("Run: trail notion process --help")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
