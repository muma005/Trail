# Prompt for Qwen to Implement Phase 2 & 2.5 of Trail (Notion Sync, Linking, Dependencies, Sub‑tasks, Size Tags)

You are an expert software engineer. Your task is to implement **Phase 2 (Notion Sync & Enrichment)** and **Phase 2.5 (Enhanced Enrichment – Dependencies, Sub‑tasks, Size Tags)** for the **Trail** project (formerly Ariadne). This builds on Phase 0, 1, and 1.5.

**No generic or lazy work.** Every function must be robust, handle edge cases, and be production‑ready. You will produce code, database migrations, CLI extensions, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- `projects` table with `id`, `github_repo_url`, `notion_database_id`, `last_synced_at`.
- `commits` table with `parsed_task_id`, `needs_classification`.
- `project_scopes`, `sync_logs`.
- GitHub sync works: `trail sync --project X` fetches commits.
- CLI commands: `trail project add`, `trail orphans`, etc.

Phase 2 adds Notion sync and linking. Phase 2.5 adds dependencies, sub‑tasks, and size tags.

---

## Phase 2: Notion Sync & Linking (2 weeks)

### Week 1 – Notion Connector

**Tasks:**

1. **Install dependencies**: `notion-client`, `sentence-transformers` (for embeddings later), `numpy`.
2. **Authentication**: Use `NOTION_TOKEN` from `.env` (integration token). Ensure the token has access to shared databases.
3. **Write `trail/notion_client.py`** with function `fetch_database_pages(database_id: str) -> list[dict]`:
   - Use `notion_client.Client` to query a database.
   - Handle pagination (Notion API returns up to 100 items per request).
   - Return a list of pages, each containing `id`, `properties` (all fields), `created_time`, `last_edited_time`.
   - Extract commonly used properties: `Title`, `Status`, `Priority`, `Due date`, `Completed`, `Progress %`, `Estimate (hours)`, `Tags`, `Parent task` (relation), `Blocks` (relation).
   - Convert Notion property types to simple Python types (e.g., `title` → string, `select` → string, `date` → ISO string, `number` → float, `relation` → list of page IDs).

4. **Store tasks in database**:
   - Add to `trail/db.py` function `store_notion_tasks(project_id, tasks_list)` using `execute_values` for bulk upsert (conflict on `notion_page_id`).
   - Table `notion_tasks` should have columns: `id` (UUID), `project_id`, `notion_page_id` (unique), `title`, `status`, `priority`, `due_date`, `completed_at`, `progress_percentage`, `estimated_minutes`, `actual_minutes`, `tags` (text[]), `parent_task_id` (UUID, self‑reference), `size_tag`, `created_at`, `updated_at`.
   - Create migration `003_add_notion_tables.sql`.

5. **Integrate into sync command**:
   - Extend `trail sync --project X` to also fetch Notion tasks for that project.
   - Update `last_synced_at` after successful Notion sync.
   - Log each sync in `sync_logs` with `sync_type = 'notion'`.

**Week 1 Success Criteria**:
- `trail sync --project X` fetches all pages from the project's Notion database and stores them in `notion_tasks`.
- Running it again updates existing tasks (if changed) and inserts new ones.
- `SELECT * FROM notion_tasks WHERE project_id = X` returns correct data.

---

### Week 2 – Linking Commits to Tasks

**Tasks:**

1. **Create `commit_task_links` table**:
   - Columns: `commit_id` (references `commits.id`), `task_id` (references `notion_tasks.id`), `confidence` DECIMAL(3,2), `created_at`.
   - Primary key on `(commit_id, task_id)`.

2. **Exact matching (confidence = 1.0)**:
   - For each commit with `parsed_task_id` (e.g., `TASK-123`), try to match to a Notion task where:
     - `notion_page_id` equals the parsed ID, **or**
     - A custom property (e.g., `Task ID`) equals the parsed ID.
   - If found, create link with confidence 1.0.

3. **Embedding‑based suggestions (confidence < 1.0)**:
   - For commits with `needs_classification = True` (no parsed ID) or those not yet linked:
     - Generate embedding for commit message using `sentence-transformers/all-MiniLM-L6-v2` (lightweight).
     - Generate embeddings for each unlinked task title + description (concatenate).
     - Compute cosine similarity. Suggest links with similarity > 0.7, store with confidence = similarity score.
   - Store these suggestions in `commit_task_links` with confidence < 1.0, but mark them as `is_suggestion = TRUE` (add column) or use a separate table `commit_task_suggestions`. Simpler: use `confidence < 1.0` to indicate a suggestion.

4. **CLI command: `trail link-suggestions`**:
   - Lists suggested links (confidence between 0.7 and 1.0) for review.
   - Output format: `Commit SHA | Commit message | Suggested Task | Confidence | Accept? (y/n)`
   - Allow user to accept a suggestion, which updates `confidence` to 1.0 (or creates a permanent link).
   - Also allow ignoring a suggestion (delete from suggestions).

5. **Performance considerations**:
   - Generate embeddings in batches; store them in a separate table `embeddings` (or use a vector DB like PgVector – but for Phase 2, simple approach: compute on‑the‑fly and cache in memory for the session).
   - Since the number of tasks per project is small (<1000), on‑the‑fly is acceptable.

**Week 2 Success Criteria**:
- Commit with `[TASK-42]` in its message creates a link with confidence 1.0 to the Notion task whose ID is `TASK-42`.
- `trail link-suggestions` shows at least one suggestion for an unlinked commit (test by committing without a task ID).
- Accepting a suggestion sets confidence to 1.0.

---

## Phase 2.5: Enhanced Enrichment – Dependencies, Sub‑tasks, Size Tags (1 week)

**Goal:** Extract task dependencies, sub‑tasks, and automatic size classification from Notion.

### Tasks

1. **Create `task_dependencies` table**:
   - Columns: `id`, `task_id` (UUID, references `notion_tasks.id`), `depends_on_task_id` (UUID), `depends_on_project_id` (UUID, for cross‑project), `dependency_type` VARCHAR(50) default 'blocks', `created_at`.
   - Constraint: at least one of `depends_on_task_id` or `depends_on_project_id` is not null.

2. **Extend Notion parser to read relation properties**:
   - In `notion_client.py`, when fetching a task page, also fetch any relation properties named "Blocks", "Blocked by", "Depends on", or a configurable list.
   - For each related page ID, create a dependency entry in `task_dependencies` (after storing the task).
   - Handle self‑references (ignore).

3. **Create `sub_tasks` table**:
   - Columns: `id`, `parent_task_id` (UUID, references `notion_tasks.id`), `title` TEXT, `is_completed` BOOLEAN, `estimated_minutes` INT, `order_index` INT, `created_at`.
   - Parse Notion checklists: a page may contain a `to_do` block with children. Extract each checkbox as a sub‑task. Also support child pages that are marked as sub‑task (e.g., via a property “Is sub‑task”).
   - Store sub‑tasks and link to parent task.

4. **Automatic size tagging**:
   - Add column `size_tag` to `notion_tasks` (values: 'quick', 'medium', 'large').
   - Rules:
     - If `estimated_minutes` exists and < 15 → 'quick'
     - If `estimated_minutes` between 15 and 240 → 'medium'
     - If `estimated_minutes` > 240 → 'large'
     - If no estimate, use keywords in title: 'quick', 'fast', 'tiny' → 'quick'; 'large', 'big', 'refactor' → 'large'; else 'medium'.
   - Run this classification during sync and update `size_tag`.

5. **CLI command: `trail task show <task_id>`**:
   - Display task details: title, status, priority, due date, progress %, estimated minutes.
   - List sub‑tasks (with completion checkboxes).
   - List dependencies: “Blocks: Task X”, “Blocked by: Task Y”.
   - Output in human‑readable format (table or bullet points).

### Success Criteria

- A Notion task that has a relation to another task (e.g., “Blocked by”) creates an entry in `task_dependencies`.
- A Notion page containing a checklist (to_do blocks) creates sub‑tasks in `sub_tasks` table.
- A task with estimated 10 minutes is automatically tagged `quick`.
- `trail task show <id>` displays all the above information correctly.

---

## Additional Quality Requirements (All Phases)

- **Idempotency**: Running sync twice should not duplicate data.
- **Error handling**: If Notion API fails, log error and continue (don’t break GitHub sync). If relation property doesn’t exist, skip gracefully.
- **Logging**: Use Python `logging` with INFO level for normal operation, DEBUG for verbose output.
- **Testing**: Provide manual test instructions (e.g., create a Notion database with sample tasks, checklists, relations; run sync; verify database).
- **Documentation**: Update `README.md` with new commands and configuration.

---

## Deliverables

You will produce the following files/extensions:

1. **Migration scripts**:
   - `004_add_notion_tables.sql` (creates `notion_tasks`, `commit_task_links`)
   - `005_add_dependencies_and_subtasks.sql` (creates `task_dependencies`, `sub_tasks`, adds `size_tag` to `notion_tasks`)
2. **`trail/notion_client.py`** – all Notion API interactions.
3. **`trail/linker.py`** – logic for exact matching and embedding‑based suggestions.
4. **`trail/dependencies.py`** – parsing relations and sub‑tasks.
5. **Updated `trail/sync.py`** – integrate Notion sync, linking, dependency extraction, size tagging.
6. **Updated `trail/cli.py`** – add `trail link-suggestions` and `trail task show`.
7. **`trail/embeddings.py`** – helper for generating and comparing embeddings.
8. **Updated requirements.txt** – add `notion-client`, `sentence-transformers`, `torch` (or use `onnxruntime` to reduce size).
9. **Test instructions** (as a separate `.md` file).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration scripts.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholder comments. Deliver a complete, runnable Phase 2 and 2.5.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded Notion property names** – use configuration or auto‑detection (but for MVP, assume standard names; document how to adapt).
- **No infinite loops** – pagination must end.
- **No missing indexes** – index `notion_page_id`, `project_id` in `notion_tasks`.
- **No embedding explosion** – compute embeddings only when needed; cache results in a table (optional but recommended).
- **No broken CLI** – ensure `trail sync` still works without Notion token (skip Notion sync gracefully).

Now, implement Phase 2 and 2.5 with the same excellence as previous phases. **Trail is counting on you.**