"""
CLI commands for managing Trail projects.
Implements `trail project add` and `trail project list`.
"""
import sys

import click
from rich.console import Console
from rich.table import Table

from src.config.settings import settings
from src.core.connectors.github_connector import GitHubConnector
from src.core.connectors.notion_connector import NotionConnector
from src.models.database.session import (
    create_project,
    get_all_projects,
    init_db,
    log_sync_event,
    save_project_scopes,
    upsert_user_preferences,
)
from src.utils.exceptions.base import (
    DatabaseError,
    DuplicateProjectError,
    GitHubError,
    NotionError,
    TrailError,
    ValidationError,
)
from src.utils.helpers.validators import (
    validate_github_url,
    validate_notion_database_id,
    validate_project_key,
    validate_project_name,
)

console = Console()


@click.group()
def project():
    """Manage Trail projects (add, list, remove)."""
    pass


@project.command("add")
@click.option("--name", required=True, help="Human-readable project name.")
@click.option("--key", required=True, help="Unique project identifier (e.g., AUTH-01).")
@click.option("--github", required=True, help="GitHub repository URL (https://github.com/owner/repo).")
@click.option("--notion-db", required=True, help="Notion database ID (32-char hex string).")
@click.option("--branch", multiple=True, help="Allowed branch(es). Can be repeated.")
@click.option("--path", "paths", multiple=True, help="Allowed path prefix(es). Can be repeated.")
@click.option("--work-start", default="09:00", help="Work start time (default: 09:00).")
@click.option("--work-end", default="17:00", help="Work end time (default: 17:00).")
@click.option("--timezone", default="UTC", help="Timezone (default: UTC).")
def add_project(name, key, github, notion_db, branch, paths, work_start, work_end, timezone):
    """
    Register a new project with GitHub repo and Notion database.

    Optional --branch and --path flags can filter which commits are tracked.
    If no scopes provided, all branches and paths are accepted.

    Validates that both the GitHub repository and Notion database exist
    and are accessible before storing them.
    """
    try:
        # Ensure environment is properly configured
        settings.validate_required()

        # Validate all inputs BEFORE making any API or DB calls
        console.print("[cyan]Validating inputs...[/cyan]")
        validated_name = validate_project_name(name)
        validated_key = validate_project_key(key)
        validated_github = validate_github_url(github)
        validated_notion = validate_notion_database_id(notion_db)

        # Validate GitHub repository exists
        console.print(f"[cyan]Verifying GitHub repository: {validated_github}...[/cyan]")
        gh_connector = GitHubConnector(settings.github_token)
        gh_info = gh_connector.validate_access(validated_github)
        console.print(f"  [green]✓[/green] Found: {gh_info['full_name']} ({'private' if gh_info['private'] else 'public'})")

        # Validate Notion database exists
        console.print(f"[cyan]Verifying Notion database: {validated_notion}...[/cyan]")
        notion_connector = NotionConnector(settings.notion_token)
        notion_info = notion_connector.validate_access(validated_notion)
        console.print(f"  [green]✓[/green] Found: {notion_info['title']}")

        # Initialize database and store project (only after all validations pass)
        init_db()
        console.print("[cyan]Storing project in database...[/cyan]")
        project_id = create_project(
            project_key=validated_key,
            name=validated_name,
            github_repo_url=validated_github,
            notion_database_id=validated_notion,
        )

        # Store branch/path scopes if provided
        branch_list = list(branch)
        path_list = list(paths)
        if branch_list or path_list:
            save_project_scopes(project_id, branch_list, path_list)
            scope_msg = []
            if branch_list:
                scope_msg.append(f"branches: {', '.join(branch_list)}")
            if path_list:
                scope_msg.append(f"paths: {', '.join(path_list)}")
            console.print(f"  [dim]Scopes:[/dim] {'; '.join(scope_msg)}")

        # Save user preferences (work hours, timezone)
        upsert_user_preferences(work_start, work_end, timezone)

        # Log the creation event
        log_sync_event(
            project_id=project_id,
            sync_type="project_creation",
            status="success",
            message=f"Project '{validated_name}' created successfully",
        )

        console.print(f"\n[bold green]✓ Project added successfully![/bold green]")
        console.print(f"  [dim]ID:[/dim] {project_id}")
        console.print(f"  [dim]Key:[/dim] {validated_key}")
        console.print(f"  [dim]GitHub:[/dim] {gh_info['full_name']}")
        console.print(f"  [dim]Notion:[/dim] {notion_info['title']}")

    except ValidationError as e:
        console.print(f"[bold red]Validation Error:[/bold red] {e}")
        sys.exit(1)
    except DuplicateProjectError as e:
        console.print(f"[bold red]Duplicate Project Error:[/bold red] {e}")
        sys.exit(1)
    except GitHubError as e:
        console.print(f"[bold red]GitHub Error:[/bold red] {e}")
        sys.exit(1)
    except NotionError as e:
        console.print(f"[bold red]Notion Error:[/bold red] {e}")
        sys.exit(1)
    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except EnvironmentError as e:
        console.print(f"[bold red]Configuration Error:[/bold red] {e}")
        sys.exit(1)
    except TrailError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)


@project.command("list")
def list_projects():
    """
    List all registered projects in a formatted table.
    """
    try:
        init_db()
        projects = get_all_projects()

        if not projects:
            console.print("[yellow]No projects registered yet.[/yellow]")
            console.print("Use [bold]trail project add[/bold] to register your first project.")
            return

        table = Table(title="Registered Projects")
        table.add_column("Key", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("GitHub", style="dim")
        table.add_column("Notion DB", style="dim")
        table.add_column("Created", style="dim")

        for p in projects:
            # Shorten GitHub URL for display
            gh_display = p.github_repo_url.replace("https://github.com/", "")
            notion_display = p.notion_database_id[:8] + "..."

            table.add_row(
                p.project_key,
                p.name,
                gh_display,
                notion_display,
                p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "N/A",
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(projects)} project(s)[/dim]")

    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
