"""
CLI commands for the AI Brain.
Phase 9: trail brain "query", trail brain --session, trail brain --reset
"""
import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console

from src.ai.brain.context_manager import get_conversation_manager
from src.ai.reasoning.react_engine import get_react_engine
from src.models.database.session import init_db
from src.utils.exceptions.base import DatabaseError

console = Console()

SESSION_FILE = Path.home() / ".trail_session"


def get_or_create_session() -> str:
    """Get session ID from file or create a new one."""
    if SESSION_FILE.exists():
        try:
            return SESSION_FILE.read_text().strip()
        except Exception:
            pass

    cm = get_conversation_manager()
    session_id = cm.start_session()
    SESSION_FILE.write_text(session_id)
    return session_id


@click.group()
def brain():
    """Interact with the Trail AI Brain."""
    pass


@brain.command()
@click.argument("query", required=True)
def ask(query: str):
    """
    Ask the AI Brain a question.

    Example: trail brain ask "what is the status of AUTH-01?"
    """
    try:
        init_db()
        session_id = get_or_create_session()

        engine = get_react_engine()
        response = engine.process_query(query, session_id)

        console.print(f"\n[bold green]Trail:[/bold green] {response}\n")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@brain.command("session")
def show_session():
    """Show current session info."""
    try:
        init_db()
        session_id = get_or_create_session()
        cm = get_conversation_manager()
        info = cm.get_session_info(session_id)

        if info:
            console.print(f"\n[bold]Session Info[/bold]")
            console.print(f"  [dim]Session ID:[/dim] {info['session_id'][:12]}...")
            console.print(f"  [dim]Started:[/dim] {info['started']}")
            console.print(f"  [dim]Last activity:[/dim] {info.get('last_activity', 'N/A')}")
            console.print(f"  [dim]Messages:[/dim] {info['message_count']}")
        else:
            console.print("[yellow]No active session.[/yellow]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@brain.command("reset")
def reset_session():
    """Clear current session and start fresh."""
    try:
        init_db()
        if SESSION_FILE.exists():
            session_id = SESSION_FILE.read_text().strip()
            cm = get_conversation_manager()
            count = cm.reset_session(session_id)
            console.print(f"[bold green]✓[/bold green] Session reset: {count} messages deleted.")
            SESSION_FILE.unlink()
        else:
            console.print("[yellow]No active session to reset.[/yellow]")

        # Create new session
        new_session = get_or_create_session()
        console.print(f"[dim]New session started: {new_session[:12]}...[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
