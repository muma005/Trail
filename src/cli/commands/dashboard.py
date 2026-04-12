"""
CLI command for launching the Streamlit dashboard.
Phase 4: `trail dashboard` launches http://localhost:8501.
"""
import os
import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.command()
@click.option("--port", default=8501, help="Port to run Streamlit on.")
def dashboard(port: int):
    """
    Launch the Trail web dashboard (Streamlit).

    Opens http://localhost:<port> in your browser.
    Requires: pip install streamlit plotly pandas
    """
    dashboard_path = Path(__file__).parent.parent / "dashboard.py"

    if not dashboard_path.exists():
        console.print(f"[bold red]Error:[/bold red] Dashboard file not found: {dashboard_path}")
        sys.exit(1)

    console.print(f"[cyan]Launching Trail Dashboard at http://localhost:{port}...[/cyan]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]")

    try:
        subprocess.run(
            [
                sys.executable, "-m", "streamlit", "run", str(dashboard_path),
                f"--server.port={port}",
                "--server.headless=true",
                "--browser.gatherUsageStats=false",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard stopped.[/yellow]")
    except FileNotFoundError:
        console.print(
            "[bold red]Error:[/bold red] Streamlit not installed.\n"
            "Install with: pip install streamlit plotly pandas"
        )
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
