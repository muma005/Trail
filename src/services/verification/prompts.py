"""
Prompt delivery and response parsing.
Phase 7.5: Delivers untracked work prompts to CLI and parses user responses.
"""
import logging
from typing import Any, Dict, List, Optional

from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)


def deliver_untracked_prompt(
    project_name: str,
    duration_minutes: int,
    available_projects: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Display a CLI prompt asking the user to assign untracked work.

    Args:
        project_name: Name of the project where activity was detected
        duration_minutes: Duration of untracked work session
        available_projects: List of dicts with 'key', 'name' for all active projects

    Returns:
        Dict with 'action' ('assign' or 'ignore') and optional 'project_key',
        or None if user cancels.
    """
    console.print(f"\n[bold yellow]⚠️ Untracked Work Detected[/bold yellow]")
    console.print(
        f"I noticed you worked on [cyan]{project_name}[/cyan] for "
        f"[bold]{duration_minutes} minutes[/bold], but didn't see any commits or task updates."
    )
    console.print("Which project should this time be assigned to?\n")

    # Show options
    for i, proj in enumerate(available_projects, 1):
        default = " (same project)" if proj["name"] == project_name else ""
        console.print(f"  {i}. {proj['key']}: {proj['name']}{default}")

    console.print(f"  {len(available_projects) + 1}. A different project (type project key)")
    console.print(f"  {len(available_projects) + 2}. Ignore (this was research/meeting)")
    console.print(f"  q. Cancel\n")

    while True:
        choice = console.input("[bold]Your choice:[/bold] ").strip()

        if choice.lower() == 'q':
            return None

        try:
            num = int(choice)
            if 1 <= num <= len(available_projects):
                return {
                    "action": "assign",
                    "project_key": available_projects[num - 1]["key"],
                }
            elif num == len(available_projects) + 1:
                # User types a different project key
                custom_key = console.input("  Enter project key: ").strip().upper()
                if custom_key:
                    return {"action": "assign", "project_key": custom_key}
                else:
                    console.print("[yellow]Invalid key. Try again.[/yellow]")
                    continue
            elif num == len(available_projects) + 2:
                return {"action": "ignore"}
            else:
                console.print("[yellow]Invalid choice. Try again.[/yellow]")
        except ValueError:
            console.print("[yellow]Please enter a number.[/yellow]")


def parse_notion_response(command_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse a Notion @ai response for untracked work assignment.
    Expected formats:
    - "assign to PROJ-01"
    - "assign PROJ-01"
    - "ignore"

    Args:
        command_text: User's reply text

    Returns:
        Dict with 'action' and optional 'project_key', or None.
    """
    text = command_text.lower().strip()

    if "ignore" in text:
        return {"action": "ignore"}

    # Look for project key pattern (e.g., PROJ-01, AUTH-01)
    import re
    match = re.search(r'([A-Z]+-\d+)', command_text.upper())
    if match:
        return {
            "action": "assign",
            "project_key": match.group(1),
        }

    return None
