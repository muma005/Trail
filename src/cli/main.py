"""
Trail CLI - Main entry point using Click.
Registers command groups and subcommands.

Usage:
    trail project add --name "Auth Service" --key "AUTH-01" --github "..." --notion-db "..."
    trail project list
"""
import click

from src.cli.commands.project import project


@click.group()
@click.version_option(version="0.1.0", prog_name="Trail")
def cli():
    """
    Trail - AI-Enabled Progress Tracker

    Track progress across GitHub and Notion, generate resumption reports,
    plan your work, and let an AI brain help you stay on track.
    """
    pass


# Register command groups
cli.add_command(project)


if __name__ == "__main__":
    cli()
