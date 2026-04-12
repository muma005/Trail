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
from src.core.connectors.notion_connector import NotionConnector
from src.core.enrichment.commit_parser import classify_commit, parse_task_id
from src.core.enrichment.enricher import CommitLinker
from src.core.enrichment.normalizer import classify_size, extract_dependencies, extract_subtasks_from_blocks
from src.models.database.session import (
    get_commit_count,
    get_project_by_key,
    get_project_scopes,
    init_db,
    log_sync_event,
    store_commits,
    store_dependencies,
    store_notion_tasks,
    store_subtasks,
    update_last_synced,
    update_task_size_tags,
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
        console.print(f"\n[bold green]✓ GitHub sync complete![/bold green]")
        console.print(f"  [dim]New commits:[/dim] {new_count}")
        console.print(f"  [dim]Total commits:[/dim] {total_commits}")
        if latest_commit_date:
            console.print(f"  [dim]Last synced:[/dim] {latest_commit_date.strftime('%Y-%m-%d %H:%M:%S')}")

        # ------------------------------------------------------------------
        # Phase 2: Notion sync
        # ------------------------------------------------------------------
        console.print(f"\n[cyan]Syncing Notion tasks...[/cyan]")
        notion_tasks_synced = 0
        try:
            notion_connector = NotionConnector(settings.notion_token)
            notion_pages = notion_connector.fetch_database_pages(project["notion_database_id"])
            console.print(f"  [dim]Fetched {len(notion_pages)} page(s) from Notion[/dim]")

            if notion_pages:
                # Fetch blocks for sub-task extraction
                page_id_to_task_id = {}
                all_dependencies = []
                all_subtasks = {}
                task_sizes = {}

                for page in notion_pages:
                    page_id = page["notion_page_id"]
                    page_id_to_task_id[page_id.replace("-", "")] = page_id

                # Store tasks first (needed for dependency linking)
                notion_tasks_synced = store_notion_tasks(project["id"], notion_pages)

                # Get stored tasks to build page_id → local_id mapping
                from src.models.database.session import get_notion_tasks
                stored_tasks = get_notion_tasks(project["id"])
                page_to_local = {t["notion_page_id"].replace("-", ""): t["id"] for t in stored_tasks}
                page_to_local_full = {t["notion_page_id"]: t["id"] for t in stored_tasks}
                page_to_local.update(page_to_local_full)

                # Process each task for dependencies, sub-tasks, and size
                for page in notion_pages:
                    local_id = page_to_local.get(page["notion_page_id"].replace("-", ""))
                    if not local_id:
                        continue

                    # Phase 2.5: Dependencies from relations
                    page["id"] = local_id  # Add local ID for dependency extraction
                    deps = extract_dependencies(page, page_to_local)
                    if deps:
                        all_dependencies.extend(deps)

                    # Phase 2.5: Sub-tasks from to_do blocks
                    blocks = notion_connector.fetch_page_blocks(page["notion_page_id"])
                    if blocks:
                        subtasks = extract_subtasks_from_blocks(blocks)
                        if subtasks:
                            all_subtasks[local_id] = subtasks

                    # Phase 2.5: Size tagging
                    size_tag = classify_size(page)
                    if size_tag:
                        task_sizes[local_id] = size_tag

                # Store dependencies
                if all_dependencies:
                    dep_count = store_dependencies(all_dependencies)
                    console.print(f"  [dim]Dependencies stored:[/dim] {dep_count}")

                # Store sub-tasks
                total_subtasks = 0
                for parent_id, subtasks in all_subtasks.items():
                    total_subtasks += store_subtasks(parent_id, subtasks)
                if total_subtasks:
                    console.print(f"  [dim]Sub-tasks stored:[/dim] {total_subtasks}")

                # Update size tags
                if task_sizes:
                    tag_count = update_task_size_tags(task_sizes)
                    console.print(f"  [dim]Size tags updated:[/dim] {tag_count}")

                # Phase 2: Link commits to tasks
                console.print(f"[cyan]Linking commits to tasks...[/cyan]")
                linker = CommitLinker()

                # Get all commits for this project with commit_id
                from src.models.database.session import get_existing_commit_shas
                existing_shas = get_existing_commit_shas(project["id"])

                # Build commit list with commit_id for linking
                commit_list = []
                from src.models.database.models import Commit
                from src.models.database.base import SessionLocal
                db = SessionLocal()
                try:
                    commits_db = db.query(Commit).filter(Commit.project_id == project["id"]).all()
                    commit_list = [
                        {
                            "commit_id": c.id,
                            "sha": c.commit_sha,
                            "message": c.message,
                            "parsed_task_id": c.parsed_task_id,
                        }
                        for c in commits_db
                    ]
                finally:
                    db.close()

                # Exact matching
                exact_links = linker.exact_match_links(
                    project["id"],
                    commit_list,
                    stored_tasks,
                )
                if exact_links:
                    console.print(f"  [dim]Exact links created:[/dim] {exact_links}")

                # Embedding suggestions
                unlinked_commits = [c for c in commit_list if not c.get("parsed_task_id")]
                suggestion_count = linker.generate_embedding_suggestions(
                    project["id"],
                    unlinked_commits,
                    stored_tasks,
                )
                if suggestion_count:
                    console.print(f"  [yellow]⚡ Suggestions created:[/yellow] {suggestion_count}")
                    console.print(f"  [dim]Run: trail link suggestions[/dim]")

            log_sync_event(
                project_id=project["id"],
                sync_type="notion",
                status="success",
                message=f"Stored {notion_tasks_synced} task(s)",
            )

        except Exception as e:
            console.print(f"  [yellow]⚠ Notion sync skipped:[/yellow] {e}")
            log_sync_event(
                project_id=project["id"],
                sync_type="notion",
                status="failed",
                message=str(e),
            )

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
