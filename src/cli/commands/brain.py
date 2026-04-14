"""
CLI commands for the AI Brain.
Phase 9: trail brain "query", trail brain --session, trail brain --reset
Phase 9.5: --channel flag, gamification stats, deprecation forwarding
"""
import json
import os
import sys
from pathlib import Path

import click
from rich.console import Console

from src.ai.brain.context_manager import get_conversation_manager
from src.ai.brain.gamification import get_gamification_engine
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


def deliver_message(message: str, channel: str) -> None:
    """Deliver a message to the specified channel."""
    if channel == "slack":
        slack_url = os.getenv("SLACK_WEBHOOK_URL")
        if not slack_url:
            console.print("[yellow]⚠️ Slack integration not yet implemented. Set SLACK_WEBHOOK_URL to enable.[/yellow]")
            console.print(f"\n{message}")
        else:
            import requests
            try:
                requests.post(slack_url, json={"text": message}, timeout=10)
                console.print("[bold green]✓[/bold green] Message sent to Slack")
            except Exception as e:
                console.print(f"[bold red]Failed to send to Slack:[/bold red] {e}")
                console.print(f"\n{message}")
    else:
        console.print(f"\n[bold green]Trail:[/bold green] {message}\n")


@click.group()
def brain():
    """Interact with the Trail AI Brain."""
    pass


@brain.command()
@click.argument("query", required=True)
@click.option("--channel", default="cli", type=click.Choice(["cli", "slack", "notion"]),
              help="Delivery channel (default: cli)")
def ask(query: str, channel: str):
    """
    Ask the AI Brain a question.

    Example: trail brain ask "what is the status of AUTH-01?"
    """
    try:
        init_db()
        session_id = get_or_create_session()

        # Handle gamification stats query
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["my stats", "my points", "my badges", "my streak", "show stats"]):
            engine = get_gamification_engine()
            stats = engine.get_user_stats()
            response = (
                f"📊 **Your Stats**\n\n"
                f"• Total Points: {stats['total_points']}\n"
                f"• Current Streak: {stats['current_streak']} days\n"
                f"• Longest Streak: {stats['longest_streak']} days\n"
            )
            if stats['badges']:
                response += f"• Badges: {', '.join(b['name'] for b in stats['badges'])}"
            else:
                response += "• Badges: None yet"
            deliver_message(response, channel)
            return

        engine = get_react_engine()
        response = engine.process_query(query, session_id)
        deliver_message(response, channel)

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

        new_session = get_or_create_session()
        console.print(f"[dim]New session started: {new_session[:12]}...[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
