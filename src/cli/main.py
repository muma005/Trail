"""
Trail CLI - Main entry point using Click.
Registers command groups and subcommands.

Usage:
    trail project add --name "Auth Service" --key "AUTH-01" --github "..." --notion-db "..."
    trail project list
    trail sync github --project AUTH-01
    trail sync github --project AUTH-01 --full
"""
import click

from src.cli.commands.dashboard import dashboard
from src.cli.commands.link import link
from src.cli.commands.notion import notion
from src.cli.commands.orphans import orphans
from src.cli.commands.plan import plan
from src.cli.commands.progress import progress
from src.cli.commands.project import project
from src.cli.commands.report import report
from src.cli.commands.switch_cost import switch_cost
from src.cli.commands.sync import sync
from src.cli.commands.task import task
from src.cli.commands.timeoff import timeoff


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
cli.add_command(sync)
cli.add_command(orphans)
cli.add_command(link)
cli.add_command(task)
cli.add_command(progress)
cli.add_command(report)
cli.add_command(dashboard)
cli.add_command(notion)
cli.add_command(plan)
cli.add_command(timeoff)
cli.add_command(switch_cost)


if __name__ == "__main__":
    cli()
