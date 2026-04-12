# Prompt for Qwen to Implement Phase 1 of Ariadne (GitHub Sync)

You are an expert software engineer. Your task is to implement **Phase 1: Data Ingestion – GitHub Sync** for the trail project. This phase builds on Phase 0 (foundation). You will produce a complete, production‑ready implementation that fetches commits from a GitHub repository, stores them in PostgreSQL, and includes rate limiting, caching, incremental sync, and pagination.

**This is a high‑stakes component – lazy or generic code is unacceptable.** Every function must be robust, well‑tested, and handle edge cases (network failures, rate limits, missing repos, etc.). You will provide the code, configuration updates, and verification steps.

---

## Context from Phase 0

Phase 0 already created:
- `projects` table with `id`, `github_repo_url`, `last_synced_at` (add this column if missing).
- `sync_logs` table.
- CLI skeleton with `ariadne sync --project <key>` (placeholder).
- `.env` with `GITHUB_TOKEN`.

Your Phase 1 must integrate with the existing codebase. Do not rewrite Phase 0; extend it.

---

## Your Deliverables

You will produce the following files (extending the existing structure):

1. **`ariadne/github_client.py`** – Contains `fetch_commits` function with rate limiting, retries, and pagination.
2. **`ariadne/sync.py`** – Implements the `sync` command logic, including incremental sync and caching.
3. **`ariadne/cache.py`** – Redis cache wrapper for GitHub responses.
4. **Updates to `ariadne/db.py`** – Add functions to store commits, update `last_synced_at`, and log sync attempts.
5. **Migration script** (e.g., `migrations/001_add_last_synced_at.sql`) to add `last_synced_at` column to `projects` table if missing.
6. **Updated `ariadne/cli.py`** – Connect the `sync` command to the new logic.
7. **Updated `requirements.txt`** – Add `PyGithub`, `tenacity`.
8. **A short test script or manual test instructions** to verify success criteria.

All code must be clean, commented, and follow best practices. No hardcoded values; use environment variables and configuration.

---

## Detailed Technical Requirements

### 1. GitHub Connector (`github_client.py`)

- **Authentication**: Use `PyGithub` with token from `.env`.
- **Function signature**: `fetch_commits(repo_full_name: str, since: datetime | None = None) -> list[dict]`
- **Rate limiting**:
  - Use `tenacity.retry` with exponential backoff (wait `2^i` seconds, max 60s, retry up to 5 times) on `RateLimitExceededException`.
  - Before making the API call, check `github.get_rate_limit().core.remaining`. If below 100, print a warning and wait 60 seconds (or use `tenacity`).
- **Pagination**: Use `repo.get_commits(since=since).reversed` or iterate through pages. Do not hardcode a page limit – fetch all commits.
- **Commit dictionary structure**:
  ```python
  {
      "sha": str,
      "author": str | None,  # login if user exists
      "author_name": str,
      "author_email": str,
      "date": str (ISO format),
      "message": str,
      "files_changed": [{"filename": str, "additions": int, "deletions": int}],
      "lines_added": int,
      "lines_deleted": int
  }
  ```
- **Error handling**: If repo does not exist, raise `ValueError`. If network error, retry with `tenacity`.

### 2. Redis Caching (`cache.py`)

- Use `redis` library to cache raw commit lists for a given `(repo_full_name, since)` key.
- **Cache TTL**: 1 hour (3600 seconds).
- **Cache key format**: `github:commits:{repo_full_name}:{since_timestamp}`. Use `since_timestamp` as ISO string without microseconds.
- Functions: `get_cached_commits(key)` and `set_cached_commits(key, data)`.
- On a cache hit, return cached data; on miss, call GitHub API and store result.

### 3. Incremental Sync & Storage (`sync.py` and `db.py`)

- **`sync.py`**:
  - Retrieve project from database using `project_key`.
  - Get `last_synced_at` from `projects` table (if `None`, fetch all commits; else fetch commits since that timestamp).
  - Call `fetch_commits` with the repo full name and `since`.
  - For each commit, check if it already exists in `commits` table (by `sha`) – skip duplicates.
  - Insert new commits into `commits` table with `project_id`.
  - After successful sync, update `projects.last_synced_at` to the latest commit’s date (or current time if no new commits).
  - Log the sync attempt in `sync_logs` (status: success/failed, message, number of new commits).

- **`db.py` additions**:
  - `store_commits(project_id, commits_list)`: bulk insert using `psycopg2.extras.execute_values`.
  - `get_project_by_key(key)`: returns project row.
  - `update_last_synced(project_id, last_commit_date)`: updates `last_synced_at`.
  - `log_sync(project_id, sync_type, status, message)`: inserts into `sync_logs`.

### 4. CLI Integration (`cli.py`)

- Enhance `ariadne sync` command:
  - `--project` (required) – project key.
  - Optional `--full` – force full sync (ignore last_synced_at).
  - Print progress: “Fetching commits…”, “Stored 42 new commits”, “Last sync updated to 2025-03-15 10:00:00”.
  - On error, print user‑friendly message.

### 5. Database Migration

- Add `last_synced_at TIMESTAMP` to `projects` table (nullable). Also add `INDEX idx_projects_last_synced`.
- Ensure `commits` table exists (from Phase 0? If not, create it now with columns: `id`, `project_id`, `commit_sha` unique, `author_name`, `author_email`, `commit_date`, `message`, `files_changed` JSONB, `lines_added`, `lines_deleted`, `created_at`).
- Provide a migration script that checks if columns exist and adds them idempotently.

---

## Success Criteria (Must verify)

You must demonstrate (via instructions or a test script) that:

1. **First sync**: `ariadne sync --project X` fetches **all** commits from the repo and stores them in `commits` table.
2. **Second sync (incremental)**: After a new commit is pushed to GitHub, running `ariadne sync` again fetches **only the new commit** (or a few if multiple). The `last_synced_at` is updated.
3. **Rate limiting**: If rate limit is exceeded, the script waits and retries (exponential backoff). Simulate by temporarily exhausting the limit (optional; at least implement the logic).
4. **Caching**: A second call to `fetch_commits` with the same parameters within 1 hour uses Redis cache, not the GitHub API.
5. **Pagination**: Repositories with >100 commits are fully fetched (test with a repo that has many commits).
6. **Database query**: `SELECT COUNT(*) FROM commits WHERE project_id = X` matches the actual number of commits in the repo.

---

## Implementation Quality Rules (Cardinal Sins to Avoid)

- **No hardcoded secrets** – always use `.env`.
- **No silent failures** – catch exceptions, log them, and raise user‑friendly errors.
- **No unoptimized bulk inserts** – use `execute_values` for many commits.
- **No missing indexes** – add index on `commit_sha` and `project_id` in `commits`.
- **No race conditions** – use database transactions when updating `last_synced_at`.
- **No lazy pagination** – ensure all pages are fetched.
- **No incomplete error handling** – handle network timeouts, GitHub API errors (e.g., 404, 403), Redis connection failures.

---

## Output Format

Provide your answer as a **single, self‑contained response** with:

- A **file tree** showing the updated project structure.
- The **content of each new or modified file** in separate code blocks.
- A **migration SQL script** (if needed).
- **Verification instructions** – step‑by‑step commands to run (including setting up a test GitHub repo, pushing commits, running sync, checking database, etc.).
- A **success criteria checklist** that confirms each point.

Do not skip any file. Do not write “this part is trivial”. Deliver a complete, runnable Phase 1.

---

## Example of Expected Output Structure


## File Contents
... (code blocks)

## Verification Instructions
1. Create a test repo on GitHub.
2. Push 3 commits.
3. Run `ariadne sync --project test`.
4. Check database: `SELECT COUNT(*) FROM commits;` should be 3.
5. Push a 4th commit.
6. Run sync again – only 1 new commit inserted.
7. ...

## Success Criteria Checklist
- [ ] First sync fetches all commits.
- [ ] Second sync fetches only new commits.
- [ ] Rate limit handling implemented (test by reducing token limit?).
- [ ] Caching works (check Redis keys).
- [ ] Pagination works (test with a repo with 150 commits).
- [ ] `commits` table has correct data.
```

Now, implement Phase 1 with the same excellence as Phase 0. No shortcuts.