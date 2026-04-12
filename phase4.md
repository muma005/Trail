# Prompt for Qwen to Implement Phase 4 of Trail (Output Formats & Escalation Engine)

You are an expert software engineer. Your task is to implement **Phase 4: Output & Escalation Engine** for the **Trail** project. This phase builds on Phases 0‑3 (foundation, GitHub sync, Notion sync, progress calculation, multi‑agent reports).

**No generic or lazy work.** Every feature must be robust, user‑friendly, and production‑ready. You will produce code, configuration, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- `projects`, `commits`, `notion_tasks`, `project_snapshots`, `user_preferences`.
- CLI commands: `trail sync`, `trail progress`, `trail report` (generates a report to stdout).
- Multi‑agent report generator (Redis queues, OpenRouter).
- Notion API integration (for reading tasks; now you will also write comments).
- Slack/email sending capabilities? Not yet. You will add stubs or use simple webhooks.

Phase 4 adds:
- Multiple output formats for reports (markdown file, JSON).
- A web dashboard (Streamlit) to visualise projects and progress.
- An escalation engine that alerts when projects become stale and archives them.

---

## Phase 4: Output & Escalation Engine (1.5 weeks)

### Week 1 – Output Formats

#### Tasks

1. **Extend `trail report` command** with `--format` and `--output` flags:
   - `--format` can be `markdown` (default), `json`, or `text` (existing stdout).
   - `--output` specifies a file path (e.g., `--output reports/projectX.md`). If not provided, print to stdout.
   - For `markdown` format: save the report as a `.md` file (same content as printed to CLI).
   - For `json` format: output a structured JSON object containing all report sections, metadata (project name, date, confidence), and raw context (optional). Schema:
     ```json
     {
       "project": "Auth Service",
       "date": "2026-04-12",
       "sections": {
         "header": "...",
         "progress_summary": "...",
         "what_was_done": "...",
         "what_needs_done": "...",
         "context_and_pickup": "...",
         "ai_confidence": "..."
       },
       "metadata": {
         "days_idle": 3,
         "completion_percentage": 65.5,
         "confidence_score": 85
       }
     }
     ```

2. **Create a web dashboard using Streamlit**:
   - File: `trail/dashboard.py`.
   - When run with `trail dashboard`, launch a Streamlit app on `http://localhost:8501`.
   - Dashboard features:
     - List of all projects (active only, not archived).
     - For each project: name, last commit date, completion percentage (simple), days idle.
     - Click on a project to see:
       - Latest progress snapshot (chart of completion over time).
       - Last report (if saved as markdown, display rendered markdown).
       - List of recent commits and pending tasks.
     - Use `project_snapshots` table to plot a simple line chart (matplotlib or Plotly).
   - Add a refresh button to reload data from the database.

3. **Add CLI command `trail dashboard`**:
   - Starts the Streamlit server (subprocess or run directly). Ensure Streamlit is installed.

**Week 1 Success Criteria**:
- `trail report --format markdown --output test.md` creates a valid markdown file.
- `trail report --format json` outputs valid JSON to stdout.
- `trail dashboard` launches a web page that shows project data.

---

### Week 2 (0.5) – Escalation Engine

#### Tasks

1. **Add abandonment thresholds to `user_preferences`**:
   - New columns: `warning_days INT DEFAULT 7`, `critical_days INT DEFAULT 14`, `archive_days INT DEFAULT 21`.
   - Update migration script `007_add_abandonment_thresholds.sql`.
   - Allow user to change via CLI: `trail config set warning_days 5` (optional, but at least provide manual SQL update instructions).

2. **Create background job (Celery Beat) that runs daily**:
   - New task `check_stale_projects()` in `trail/escalation.py`.
   - For each active project (`status = 'active'`), find the latest commit date from `commits` table (or `last_synced_at` if no commits).
   - Calculate days since last commit.

3. **Send notifications**:
   - **Notion comment**: Use Notion API to append a comment to the project’s main page (store `notion_page_id` in `projects` table – you may need to add this column if not present). The comment should say: “⚠️ Project has been idle for X days. Please resume or archive.”
   - **Slack webhook**: If `SLACK_WEBHOOK_URL` is set in `.env`, send a message to a configured channel. Message format: “Project {name} idle for {days} days. <link to dashboard>”.
   - **Email**: (Optional – for simplicity, you can skip email or implement a stub using `smtplib` if `EMAIL_*` env vars are set.)
   - Notifications are sent only once per project per escalation level (i.e., when crossing warning_days, send warning; crossing critical_days, send critical; do not spam daily).

4. **Archive projects**:
   - When days idle > `archive_days`, move project to `archived_projects` table (same schema as `projects` but with an `archived_at` timestamp).
   - Remove from `projects` table (or just set `status = 'archived'`). The `archived_projects` table can be a separate table or a flag. Simpler: add `status` column to `projects` with values 'active', 'archived', 'paused'. Update the migration.
   - Archived projects are excluded from `trail progress`, `trail report`, and the dashboard (unless explicitly shown with `--include-archived`).

5. **Add CLI command to manually archive/resurrect**:
   - `trail project archive --key X` (sets status='archived')
   - `trail project resurrect --key X` (sets status='active')

**Week 2 Success Criteria**:
- After 7 days of no commits (simulate by updating `last_commit_date` in a test project), a Notion comment appears on the project page.
- After 14 days, a Slack message is sent (if webhook configured).
- After 21 days, the project status changes to 'archived' and disappears from the default dashboard.
- Manual archive and resurrect commands work.

---

## Additional Quality Requirements

- **Idempotent notifications**: Use a `last_notification_sent` table or store in `projects` columns (`last_warning_notified`, `last_critical_notified`). Avoid sending duplicate alerts.
- **Error handling**: If Notion API fails, log error and continue (don’t break other projects). If Slack webhook fails, retry once.
- **Configuration**: All thresholds, Slack webhook, email settings in `.env`.
- **Logging**: Log each escalation action (sent comment, sent Slack, archived).
- **Testing**: Provide manual test instructions (e.g., set warning_days=1, modify a project's last commit date to 8 days ago, run the job, verify comment).

---

## Deliverables

You will produce the following files/extensions:

1. **Migration scripts**:
   - `007_add_abandonment_thresholds.sql` (add columns to `user_preferences`)
   - `008_add_project_status_and_notification_log.sql` (add `status` to `projects`, `last_notification_*` columns, create `archived_projects` if using separate table)
2. **Updates to `trail/cli.py`**:
   - Extend `report` with `--format` and `--output`.
   - Add `dashboard` command.
   - Add `project archive` and `project resurrect`.
3. **`trail/dashboard.py`** – Streamlit app.
4. **`trail/escalation.py`** – background job, notification functions.
5. **Updated `trail/sync.py`** – maybe not needed, but ensure `last_commit_date` is updated after each GitHub sync (add a column `last_commit_date` to `projects` for quick lookup).
6. **Updated `requirements.txt`** – add `streamlit`, `plotly` (or `matplotlib`), `requests` (for Slack), `notion-client` (already).
7. **Test instructions** (`test_phase4.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration scripts.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 4.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded file paths** – use configuration or user‑provided output path.
- **No missing Streamlit dependencies** – ensure `streamlit` is in requirements.
- **No silent failures in escalation** – log all errors.
- **No duplicate notifications** – must implement state tracking.
- **No archive without confirmation** – can auto‑archive, but at least log it.

Now, implement Phase 4 with excellence. **Trail is counting on you.**