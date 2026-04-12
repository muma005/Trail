# Prompt for Qwen to Implement Phase 1.5: Enhanced GitHub – Branch/Path Filters & Commit Parsing

You are an expert software engineer. Your task is to implement **Phase 1.5** of the Ariadne project, building on Phase 0 (foundation) and Phase 1 (GitHub sync). This phase adds **scope filtering** (branches/paths) and **commit message parsing** for task IDs, plus orphan detection.

**No generic or lazy work.** Every function must be robust, well‑tested, and handle edge cases. You will produce the code, database migrations, CLI updates, and verification steps.

---

## Context (What Already Exists)

From Phases 0 and 1:
- `projects` table with `id`, `github_repo_url`, `last_synced_at`.
- `commits` table with `project_id`, `commit_sha`, `message`, `files_changed` JSON, etc.
- GitHub connector: `fetch_commits(repo_full_name, since=None)` returns a list of commit dicts.
- Sync command: `ariadne sync --project <key>` fetches and stores commits.
- CLI skeleton with `ariadne project add` (Phase 0) and `ariadne orphans` (placeholder).

Your Phase 1.5 must extend these components without breaking existing functionality.

---

## Your Deliverables

You will produce the following files/extensions:

1. **Migration script** (e.g., `migrations/002_add_project_scopes_and_commit_parsing.sql`) to create:
   - `project_scopes` table (columns: `project_id`, `scope_type` ('branch' or 'path'), `scope_value`).
   - Add columns to `commits`: `parsed_task_id VARCHAR(100)`, `needs_classification BOOLEAN DEFAULT FALSE`.
2. **Updated `ariadne/cli.py`** – Extend `project add` with `--branch` and `--path` flags (multiple allowed? specify: can be used multiple times; each creates a row in `project_scopes`). Also implement `ariadne orphans` command.
3. **Updated `ariadne/github_client.py`** – Modify `fetch_commits` (or a new function) to accept a list of allowed branches and paths, and filter commits accordingly. Alternatively, filter after fetching but before storing.
4. **Commit message parser module** – `ariadne/commit_parser.py` with function `parse_task_id(message: str) -> str | None` using regex patterns.
5. **Updated sync logic** – After fetching commits, for each commit:
   - Check scope: if `project_scopes` exist for the project, filter by branch name and changed files. Ignore commits that don’t match.
   - Parse message for task IDs; set `parsed_task_id`.
   - If no task ID found, set `needs_classification = True`.
   - Store commit (with new fields).
6. **CLI command `ariadne orphans`** – Lists commits where `needs_classification = True` (i.e., unlinked). Output format: table with commit SHA, date, message, project name.
7. **Updated tests or verification script** to prove success criteria.

---

## Detailed Technical Requirements

### 1. Database Changes

**`project_scopes` table**:
- `id` UUID primary key.
- `project_id` UUID references `projects(id)` ON DELETE CASCADE.
- `scope_type` VARCHAR(20) CHECK (scope_type IN ('branch', 'path')).
- `scope_value` TEXT (e.g., 'main', 'develop', 'src/auth/').
- Unique constraint on `(project_id, scope_type, scope_value)`.

**`commits` table additions**:
- `parsed_task_id VARCHAR(100)` (nullable).
- `needs_classification BOOLEAN DEFAULT FALSE`.

### 2. CLI Extensions

**`ariadne project add`**:
- New optional flags: `--branch` (can be repeated) and `--path` (can be repeated).
- Example: `ariadne project add --name "Auth" --key "AUTH-01" --github "https://github.com/..." --notion-db "..." --branch main --branch develop --path src/auth/`
- Store each branch/path as a row in `project_scopes`. If no scopes provided, default to no filtering (i.e., all branches and all paths allowed).

**`ariadne orphans`**:
- Command: `ariadne orphans [--project KEY]`
- If `--project` given, show only unlinked commits for that project; else for all projects.
- Output as a formatted table: `SHA | Date | Message (truncated) | Project`.

### 3. Commit Filtering Logic

After fetching commits from GitHub (using PyGithub), you have access to:
- Commit's branch? Not directly from the commit object; you need to know which branches contain that commit. Simpler approach: **filter by branch at the time of fetching**? PyGithub's `repo.get_commits()` can filter by `sha` (branch name). For each allowed branch, fetch commits from that branch and combine. Or fetch all commits and then check if the commit is reachable from any allowed branch (expensive). Recommended approach:
  - For each allowed branch, call `repo.get_commits(sha=branch_name, since=since)` and aggregate.
  - Remove duplicates by SHA.
- For path filtering: check if any file in `commit.files` matches any allowed path prefix (e.g., `file.filename.startswith(path)`). If no path scopes, accept all.

Implementation steps in `github_client.py`:
- New function `fetch_filtered_commits(repo_full_name, allowed_branches, allowed_paths, since=None)`.
- If `allowed_branches` empty → treat as all branches.
- Use set to deduplicate commits by SHA.

### 4. Commit Message Parser

Regex patterns to match (order matters, capture first match):
- `r'\[([A-Z]+-\d+)\]'` → `TASK-123`
- `r'#(\d+)'` → `#456` (issue number)
- `r'fixes #(\d+)'` → captures `456`
- `r'closes #(\d+)'` → captures `456`

Function returns the matched string (e.g., `"TASK-123"` or `"#456"`). If multiple matches, return the first one. If none, return `None`.

### 5. Sync Integration

In `sync.py`, after fetching commits (using `fetch_filtered_commits` with project's scopes):
- For each commit dict, call `parse_task_id(commit['message'])`.
- Set `parsed_task_id` and `needs_classification = (parsed_task_id is None)`.
- Store using existing `store_commits` (update its SQL to include new columns).

### 6. Orphans Command

Query `commits` JOIN `projects` WHERE `needs_classification = True`. Print results. Optionally allow user to manually set `parsed_task_id` via another command (future phase, but not required now).

---

## Success Criteria (Must Verify)

You must provide verification instructions (manual or script) to prove:

1. **Branch filtering**: 
   - Add project with `--branch main`.
   - Push a commit to `main` and another to `develop`.
   - Run `ariadne sync`. Only the `main` commit is stored.
2. **Path filtering**:
   - Add project with `--path src/auth/`.
   - Push a commit that changes `src/auth/login.py` and another that changes `README.md`.
   - Only the `src/auth/` commit is stored.
3. **Commit parsing**:
   - Commit message `"Add login [TASK-42]"` → `parsed_task_id = "TASK-42"`.
   - Commit message `"Fix bug #123"` → `parsed_task_id = "#123"`.
   - Commit message `"Update docs"` → `parsed_task_id = NULL`, `needs_classification = True`.
4. **`ariadne orphans`** lists the unlinked commit from above.
5. No regression: existing sync without scopes still works.

---

## Quality Rules (Cardinal Sins)

- **No silent ignoring of commits** – log a warning when a commit is filtered out (maybe at debug level).
- **No ambiguous regex** – ensure patterns don’t capture random numbers.
- **No missing indexes** – index `parsed_task_id` and `needs_classification` if queries become slow.
- **No hardcoded paths** – use configuration.
- **No broken `project add`** – existing flags must still work; new flags are optional.
- **No duplication of commits** – handle branch overlap correctly.

---

## Output Format

Provide your answer as a **single, self‑contained response** with:

- A **file tree** showing new/modified files.
- The **content of each file** in code blocks.
- **Migration SQL** (idempotent).
- **Verification instructions** (step‑by‑step commands).
- A **success criteria checklist**.

Do not skip any file. Do not write “implementation is straightforward”. Deliver a complete, runnable Phase 1.5.

Now, implement Phase 1.5 with excellence. No shortcuts.