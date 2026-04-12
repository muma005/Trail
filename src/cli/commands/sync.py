"""
CLI commands for syncing GitHub commits.
Phase 1: Implements `trail sync --project <key>` with incremental sync and caching.
"""
import sys
from datetime import datetime

import click
from rich.console import Console

from src.config.settings import settings
from src.core.connectors.github_connector import GitHubConnector
from src.core.enrichment.commit_parser import classify_commit, parse_task_id
from src.models.database.session import (
    get_commit_count,
    get_project_by_key,
    get_project_scopes,
    init_db,
    log_sync_event,
    store_commits,
    update_last_synced,
)
from src.utils.exceptions.base import (
    DatabaseError,
    GitHubError,
    TrailError,
)
from src.utils.helpers.cache import cache

console = Console()


@click.group()
def sync():
    """Sync data from external sources (GitHub, Notion)."""
    pass


@sync.command()
@click.option("--project", "project_key", required=True, help="Project key to sync (e.g., AUTH-01).")
@click.option("--full", is_flag=True, default=False, help="Force full sync (ignore last_synced_at).")
def github(project_key: str, full: bool):
    """
    Fetch commits from GitHub for a project.

    Incremental sync by default — only fetches new commits since last sync.
    Use --full to fetch all commits regardless of last_synced_at.
    """
    try:
        # Validate environment
        settings.validate_required()
        init_db()

        # Look up project
        console.print(f"[cyan]Looking up project: {project_key}...[/cyan]")
        project = get_project_by_key(project_key)
        if not project:
            console.print(f"[bold red]Error:[/bold red] Project '{project_key}' not found.")
            console.print("Use [bold]trail project add[/bold] to register it first.")
            sys.exit(1)

        console.print(f"[green]✓[/green] Found project: {project['name']}")
        console.print(f"  [dim]GitHub:[/dim] {project['github_repo_url']}")

        # Determine sync mode
        since_dt = None
        if not full and project.get("last_synced_at"):
            since_dt = project["last_synced_at"]
            console.print(f"[cyan]Incremental sync since: {since_dt.strftime('%Y-%m-%d %H:%M:%S')}[/cyan]")
        else:
            sync_mode = "Full" if full else "Initial"
            console.print(f"[cyan]{sync_mode} sync — fetching all commits[/cyan]")

        # Get project scopes for filtering
        scopes = get_project_scopes(project["id"])
        allowed_branches = scopes.get("branches", [])
        allowed_paths = scopes.get("paths", [])

        if allowed_branches:
            console.print(f"  [dim]Branch filter: {', '.join(allowed_branches)}[/dim]")
        if allowed_paths:
            console.print(f"  [dim]Path filter: {', '.join(allowed_paths)}[/dim]")

        # Build cache key
        cache_key = cache.build_commits_cache_key(
            repo_full_name=project["github_repo_url"].replace("https://github.com/", ""),
            since_timestamp=since_dt.isoformat() if since_dt else None,
        )

        # Try cache first
        cached_commits = cache.get(cache_key)
        if cached_commits is not None:
            console.print(f"[yellow]⚡ Cache hit — using cached commit data[/yellow]")
            commits = cached_commits
        else:
            # Fetch from GitHub API with scope filtering
            console.print(f"[cyan]Fetching commits from GitHub...[/cyan]")
            gh_connector = GitHubConnector(settings.github_token)

            if allowed_branches or allowed_paths:
                # Use filtered fetch
                commits = gh_connector.fetch_filtered_commits(
                    project["github_repo_url"],
                    allowed_branches=allowed_branches,
                    allowed_paths=allowed_paths,
                    since=since_dt,
                )
            else:
                # No scopes — fetch all
                commits = gh_connector.fetch_commits(project["github_repo_url"], since=since_dt)

            # Cache the results
            if commits:
                cache.set(cache_key, commits)

        if not commits:
            console.print("[yellow]No new commits found.[/yellow]")
            log_sync_event(
                project_id=project["id"],
                sync_type="github",
                status="success",
                message="No new commits",
            )
            return

        console.print(f"  [dim]Fetched {len(commits)} commit(s) from GitHub[/dim]")

        # Phase 1.5: Parse task IDs and classify commits
        orphan_count = 0
        for commit in commits:
            task_id = parse_task_id(commit.get("message", ""))
            commit["parsed_task_id"] = task_id
            commit["needs_classification"] = 1 if classify_commit(commit.get("message", "")) else 0
            if commit["needs_classification"]:
                orphan_count += 1

        if orphan_count > 0:
            console.print(f"  [yellow]⚠ {orphan_count} commit(s) need classification (run 'trail orphans list')[/yellow]")

        # Store new commits in database
        console.print(f"[cyan]Storing commits in database...[/cyan]")
        new_count = store_commits(project["id"], commits)

        # Update last_synced_at to the latest commit date
        latest_commit_date = None
        if commits:
            # Commits are returned newest-first from PyGithub
            latest_date_str = commits[0].get("date")
            if latest_date_str:
                try:
                    latest_commit_date = datetime.fromisoformat(latest_date_str)
                except (ValueError, TypeError):
                    pass

        update_last_synced(project["id"], latest_commit_date)

        # Log success
        log_sync_event(
            project_id=project["id"],
            sync_type="github",
            status="success",
            message=f"Stored {new_count} new commit(s), total: {get_commit_count(project['id'])}",
        )

        # Print summary
        total_commits = get_commit_count(project["id"])
        console.print(f"\n[bold green]✓ Sync complete![/bold green]")
        console.print(f"  [dim]New commits:[/dim] {new_count}")
        console.print(f"  [dim]Total commits:[/dim] {total_commits}")
        if latest_commit_date:
            console.print(f"  [dim]Last synced:[/dim] {latest_commit_date.strftime('%Y-%m-%d %H:%M:%S')}")

    except GitHubError as e:
        console.print(f"[bold red]GitHub Error:[/bold red] {e}")
        # Log failure
        if project:
            log_sync_event(
                project_id=project["id"],
                sync_type="github",
                status="failed",
                message=str(e),
            )
        sys.exit(1)
    except DatabaseError as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}")
        sys.exit(1)
    except TrailError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected Error:[/bold red] {e}")
        sys.exit(1)
