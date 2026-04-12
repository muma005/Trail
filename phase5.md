# Prompt for Qwen to Implement Phase 5 of Trail (Notion AI Agent – Basic)

You are an expert software engineer. Your task is to implement **Phase 5: Notion AI Agent (Basic)** for the **Trail** project. This phase builds on all previous phases (0–4). It enables users to type `@ai` commands inside Notion pages and receive AI‑generated responses directly in Notion.

**No generic or lazy work.** Every component must be robust, handle errors gracefully, and work in real conditions. You will produce code, configuration, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- Notion API integration (read database pages, tasks, etc.).
- OpenRouter API integration (LLM calls) with tiered routing (Phase 5.5 will enhance; for now, use a simple default model like `openrouter/anthropic/claude-3.5-sonnet` or a cheaper one).
- Redis for caching and queues (optional for this phase).
- Celery Beat for scheduled jobs (used for sync and escalation).
- CLI commands: `trail sync`, `trail report`, `trail progress`, etc.
- `projects` table with `notion_database_id` and `notion_page_id` (for the project’s main page).

Phase 5 adds:
- A polling script that listens for `@ai` commands in Notion pages.
- A simple AI Brain wrapper (will be replaced by the full AI Brain in Phase 9, but for now a basic request‑response).
- Ability to write responses back to Notion as callout blocks.

---

## Phase 5: Notion AI Agent – Basic (2 weeks)

### Week 1 – Trigger Detection (Polling)

#### Tasks

1. **Create a new scheduled job** (Celery Beat) that runs every minute.
   - File: `trail/notion_agent/poller.py`
   - The job queries **all tracked Notion databases** (from `projects` where `notion_database_id` is not null) for pages that contain the trigger string `@ai`.
   - Use Notion API’s search or filter by database and then scan page content? Notion API does not support searching within block content efficiently. Alternative approach:
     - For each project, query the database pages (via `query a database`) and then, for each page, fetch its **blocks** (children) and look for a paragraph block containing `@ai`.
     - This is expensive but acceptable for a small number of projects (≤20). For better performance, store a `last_checked` timestamp per page and only check pages modified since then.
   - Extract the command: everything after `@ai` until the end of the block (or until a newline). Trim whitespace.

2. **Store pending commands** to avoid duplicate processing:
   - Create a table `notion_commands`:
     - `id` UUID, `project_id` UUID, `page_id` VARCHAR(100), `block_id` VARCHAR(100), `command` TEXT, `status` VARCHAR(20) (pending/processing/completed/failed), `response_block_id` VARCHAR(100), `created_at`, `processed_at`.
   - When a new `@ai` command is found, insert a row with `status='pending'`. Use a unique constraint on `(page_id, block_id)` to prevent duplicates.

3. **Modify the poller** to only process commands that are not already pending or completed.

4. **Add a simple CLI command** for testing: `trail notion poll` – runs the poller once manually.

**Week 1 Success Criteria**:
- When you type `@ai hello` in a Notion page (in a tracked database), a record appears in `notion_commands` with status `pending` within 1 minute.
- The same command is not inserted again on subsequent polls.

---

### Week 2 – Response Writing

#### Tasks

1. **Create a response worker** (another Celery task or a separate process) that processes pending commands:
   - File: `trail/notion_agent/responder.py`
   - For each `pending` command, extract the command text.
   - Call a simple **AI Brain wrapper** (we'll call it `basic_brain.py` for now). This wrapper:
     - Parses the command (e.g., “summarize this page”, “what is the status of Project A?”, “update status to Done”).
     - For “summarize this page”: fetch the page’s content (blocks), send to OpenRouter with prompt “Summarize the following Notion page content: …”. Return summary.
     - For “what is the status of X?”: find project by name or key, call `trail progress --json` internally, format answer.
     - For “update status to Done”: find the current page (the one where the command was issued) – that page is a task? Update its `Status` property to “Done” using Notion API.
     - For unknown commands: return “I don’t understand. Try: summarize this page, what is the status of [project], or update status to Done.”
   - Use OpenRouter (default model) for summarization.

2. **Write the response back to Notion**:
   - Use Notion API to append a **callout block** (type `callout`) below the command block. The callout should contain the AI’s answer.
   - Store the `response_block_id` in `notion_commands`.
   - Update status to `completed` or `failed`.

3. **Handle errors**:
   - If the command cannot be parsed or the API fails, write an error callout: “❌ Could not process command. Reason: …”
   - Log all errors.

4. **Add a CLI command** to manually process a specific command: `trail notion process --command-id <uuid>`.

5. **Integration with existing sync**:
   - The responder should run continuously (or as a periodic job every few seconds). For simplicity, use a separate Celery worker that consumes a queue.

**Week 2 Success Criteria**:
- Typing `@ai summarize this page` in a Notion page produces a summary callout within 2 minutes (poller every minute + processing time).
- Typing `@ai what is the status of Project A?` returns the correct progress (matching `trail progress`).
- Typing `@ai update status to Done` on a task page changes that task’s Status property to “Done” in Notion.
- If the project name is ambiguous, the agent responds with a list of matching projects.

---

## Additional Quality Requirements

- **Idempotent processing**: The same command block should never be processed twice (use `status` column and check `block_id`).
- **Rate limiting**: Notion API has limits. Do not fetch all blocks every minute; use incremental checks (only pages modified since last check). For MVP, you can scan all pages every minute – acceptable for up to 10 projects.
- **Error recovery**: If Notion API returns a 429 (rate limit), wait and retry. Use `tenacity` with exponential backoff.
- **Logging**: Log each command detection, processing start, success, and failure.
- **Configuration**: The poller interval, OpenRouter model, and Notion API credentials from `.env`.

---

## Deliverables

You will produce the following files/extensions:

1. **Migration script** `009_add_notion_commands_table.sql`.
2. **`trail/notion_agent/poller.py`** – scheduled job to detect `@ai` commands.
3. **`trail/notion_agent/responder.py`** – processes commands and writes responses.
4. **`trail/notion_agent/basic_brain.py`** – command parser and action dispatcher.
5. **Updates to `trail/cli.py`** – add `trail notion poll` and `trail notion process`.
6. **Updates to `trail/celery_app.py`** (or wherever Celery tasks are defined) – add periodic task for poller and a task for responder.
7. **Updated `requirements.txt`** – ensure `notion-client`, `openrouter`, `celery`, `tenacity` are present.
8. **Test instructions** (`test_phase5.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration script.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 5.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded Notion block types** – use the official API constants.
- **No infinite polling** – the poller must eventually stop if no commands are found (but it should sleep between runs).
- **No missing error handling** – if Notion page content cannot be fetched, fail gracefully.
- **No ambiguous command parsing** – use regex or simple string matching; for MVP, a few explicit patterns are enough.
- **No writing responses without preserving formatting** – use `callout` blocks with appropriate emoji.

Now, implement Phase 5 with excellence. **Trail is counting on you.**