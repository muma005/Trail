# Prompt for Qwen to Implement Phase 3 of Trail (Progress Calculator & Multi‑Agent Report Generator)

You are an expert software engineer. Your task is to implement **Phase 3: Progress Calculator & Report Generator (Multi‑Agent)** for the **Trail** project. This phase builds on Phases 0, 1, 1.5, 2, and 2.5.

**No generic or lazy work.** Every function must be robust, production‑ready, and thoroughly tested. You will produce code, database migrations, CLI extensions, agent workers, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- `projects`, `commits`, `notion_tasks`, `commit_task_links`, `task_dependencies`, `sub_tasks`.
- GitHub sync, Notion sync, commit parsing, linking, dependencies, sub‑tasks, size tags.
- Redis already used for caching (Phase 1). Now you will use Redis also as a message broker for agent queues.
- CLI commands: `trail sync`, `trail orphans`, `trail link-suggestions`, `trail task show`, etc.
- OpenRouter API key in `.env` (assumed; if not, add instructions).

Phase 3 adds:
- Daily progress snapshots (scheduled).
- Progress calculation (simple and weighted).
- Multi‑agent report generation using Redis queues and OpenRouter.

---

## Phase 3: Progress Calculator & Report Generator (2 weeks)

### Week 1 – Progress Metrics

#### Tasks

1. **Create `project_snapshots` table** (migration script `006_add_project_snapshots.sql`):
   - Columns: `id` UUID, `project_id` UUID (references `projects.id`), `snapshot_date` DATE, `total_tasks` INT, `completed_tasks` INT, `in_progress_tasks` INT, `blocked_tasks` INT, `total_commits` INT (since last snapshot or total?), `lines_of_code_added` INT (optional, from commits), `completion_percentage_simple` DECIMAL(5,2), `completion_percentage_weighted` DECIMAL(5,2), `metadata` JSONB, `created_at` TIMESTAMP.
   - Index on `(project_id, snapshot_date)`.

2. **Write progress calculation function** in `trail/progress.py`:
   - `calculate_simple_progress(project_id) -> float`:
     - Query `notion_tasks` for the project.
     - Count tasks with status = 'Done' (or equivalent) divided by total tasks (excluding archived).
   - `calculate_weighted_progress(project_id) -> float`:
     - Define priority weights: Critical=3, High=2, Medium=1, Low=0.5 (or read from config).
     - Sum weights of completed tasks divided by sum of all weights.
   - Also compute counts: `in_progress_tasks` (status = 'In Progress'), `blocked_tasks` (status = 'Blocked').
   - For commits: count commits in `commits` table since the last snapshot (or all time). For daily snapshot, count commits since previous day.

3. **Store daily snapshot** via scheduled job:
   - Use **Celery Beat** (already used for sync scheduling? If not, install `celery` and `redis` as broker).
   - Create a periodic task that runs daily at 23:59 (or 00:00) for all active projects.
   - For each project, call `calculate_*` functions and insert a row into `project_snapshots`.
   - Handle projects with no data (skip or store zero).

4. **CLI command: `trail progress <project>`**:
   - Show current progress (simple and weighted) using live data (not snapshot).
   - Also show breakdown: total tasks, completed, in progress, blocked.
   - Output format: human‑readable table.

**Week 1 Success Criteria**:
- `trail progress` displays correct numbers that match manual count from Notion.
- After running the scheduled job (or manually triggering), a snapshot row is inserted.
- Snapshot data matches the state at that moment.

---

### Week 2 – Report Agents (Redis Queue)

#### Overview
Build a multi‑agent system where each agent is a separate Python process (or thread) that communicates via Redis queues. For simplicity, you can implement them as functions called sequentially but decoupled via queues (simulate with `rq` or plain Redis lists). The goal is to demonstrate the architecture, not necessarily horizontal scaling.

#### Tasks

1. **Set up Redis as message broker**:
   - Ensure Redis is running.
   - Install `rq` (Redis Queue) or use simple Redis lists with `lpush`/`brpop`. **Recommend `rq`** for simplicity.

2. **Define agent types** (each as a separate job/worker):

   - **Dispatcher**:
     - Receives user request (via CLI `trail report`).
     - Fetches project configuration from `projects` table.
     - Creates a job for **Context Retriever** with `project_id` and `user_query` (optional).
     - Waits for final response (or uses callback queue).

   - **Context Retriever**:
     - Queries PostgreSQL for:
       - Last 30 commits (or all since last snapshot).
       - Notion tasks (status, priority, due date).
       - Latest snapshot (for progress %).
       - Dependencies (blocked/blocking).
     - Also queries vector embeddings? Not needed for Phase 3, but can add.
     - Returns a structured JSON object with all context.

   - **LLM Analyzer**:
     - Takes the context JSON and calls **OpenRouter** API.
     - Uses a **structured prompt** (see below) that asks for a 6‑section report.
     - **Citation rule**: The LLM must reference commit SHAs and task IDs. The prompt must enforce: “For every claim about a commit, include the SHA. For every task, include its ID or title.”
     - Returns the generated report (Markdown).

   - **Validator**:
     - Receives the report and the original context.
     - Extracts all cited commit SHAs (regex `[a-f0-9]{40}`) and task IDs.
     - Checks each SHA exists in `commits` table for that project.
     - Checks each task ID exists in `notion_tasks`.
     - If any citation is invalid, flags as hallucination and either:
       - Rejects the report and asks LLM Analyzer to regenerate (with warning), or
       - Adds a “⚠️ Unverified citation” note in the report.
     - Returns the final report (with confidence score).

3. **Implement the workflow**:
   - CLI `trail report <project>` pushes a job to the Dispatcher queue.
   - Dispatcher pushes to Context Retriever queue → LLM Analyzer → Validator.
   - Use `rq` dependencies or simple chaining: after each job completes, enqueue the next.
   - For simplicity, you can run all agents sequentially within the same process but still use queues to demonstrate separation. However, for production, use separate worker processes.

4. **Structured prompt for LLM Analyzer** (include in code as a constant):
   ```
   You are a project management analyst. Generate a resumption report for the project described below.

   The report must have exactly these 6 sections:
   1. Header: Project name, days since last activity, status emoji (🟢 active / 🟡 stale / 🔴 abandoned)
   2. Progress Summary: overall completion percentage (simple and weighted), task breakdown (Done/In Progress/Blocked/Not Started), commit activity (last 4 weeks)
   3. What Was Done: last 10 commits with SHAs and messages, completed tasks, merged PRs
   4. What Needs To Be Done: priority-ordered pending tasks, immediate next action (file/function if available), blocked tasks with reason
   5. Context & Where to Pick Up: last commit details (branch, SHA, message), last task status, suggested starting command (e.g., `git checkout branch && code file`)
   6. AI Confidence Score: how confident you are (0-100%) and any missing data warnings.

   CRITICAL: For every commit you mention, you MUST include its SHA. For every task, include its ID or title. If you are unsure about something, state "Unknown" and do not invent.

   Here is the project context:
   {context_json}
   ```

5. **Validator logic**:
   - Parse report for SHAs (40‑char hex) and task IDs (e.g., `TASK-123` or Notion page ID pattern).
   - Query database to verify existence.
   - If any SHA not found, set `confidence -= 20` and append a warning.
   - Return final report with a “Validation note” section.

6. **CLI command `trail report <project>`**:
   - Triggers the workflow.
   - Waits for completion (polling or synchronous).
   - Prints the final validated report to stdout (Markdown format).
   - Optionally save to file with `--output report.md`.

**Week 2 Success Criteria**:
- `trail report` produces a report with 6 sections.
- The report contains real commit SHAs and task IDs (not hallucinated).
- If you manually modify the LLM output to include a fake SHA, the Validator detects it and adds a warning.
- The whole workflow completes within 30 seconds (for a typical project).

---

## Additional Quality Requirements

- **Idempotency**: Running `trail report` multiple times should not duplicate data (no side effects).
- **Error handling**: If OpenRouter API fails, retry up to 3 times with exponential backoff. If still fails, return a fallback report (e.g., “LLM unavailable, here are raw commits…”).
- **Logging**: Log each step (Dispatcher start, Context Retriever done, LLM call, Validator result).
- **Configuration**: OpenRouter API key, model (default `openrouter/anthropic/claude-3.5-sonnet`), and timeout should be in `.env`.
- **Testing**: Provide manual test instructions (e.g., create a project with known commits and tasks, run report, verify citations).

---

## Deliverables

You will produce the following files/extensions:

1. **Migration script** `006_add_project_snapshots.sql`.
2. **`trail/progress.py`** – calculation functions.
3. **`trail/snapshot_job.py`** – Celery Beat task for daily snapshots.
4. **`trail/agents/`** directory with:
   - `dispatcher.py`
   - `context_retriever.py`
   - `llm_analyzer.py`
   - `validator.py`
   - `workflow.py` (orchestrator)
5. **Updated `trail/cli.py`** – add `progress` and `report` commands.
6. **Updated `requirements.txt`** – add `celery`, `rq`, `openrouter` (or `requests` for direct API), `tenacity` (already), `markdown` (optional).
7. **Updated `.env.example`** – add `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_TIMEOUT`.
8. **Test instructions** (e.g., `test_phase3.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration script.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 3.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded OpenRouter model** – use environment variable.
- **No missing validation** – the Validator must be strict; hallucinated commits are a cardinal sin.
- **No blocking CLI** – the CLI should show progress (e.g., “Generating report…”) and not freeze.
- **No unstructured prompts** – the prompt must enforce the 6‑section output and citation rule.
- **No ignored errors** – if LLM fails, inform the user and suggest retry.

Now, implement Phase 3 with excellence. **Trail is counting on you.**