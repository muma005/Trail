# Prompt for Qwen to Implement Phase 7.5 of Trail (Enhanced Verification – Untracked Work & Prompts)

You are an expert software engineer. Your task is to implement **Phase 7.5: Enhanced Verification – Untracked Work & Prompts** for the **Trail** project. This phase builds on Phase 7 (Verification & Auto‑Reassignment) and adds the ability to detect work that was done but not captured by commits or task updates, then prompt the user to log it.

**No generic or lazy work.** The solution must be robust, respect user privacy, and integrate with existing verification and planning systems. You will produce code, database migrations, CLI extensions, and verification steps.

---

## Context (What Already Exists)

From Phase 7 and earlier:
- **Verification worker** – compares planned tasks against GitHub commits and Notion status changes.
- **Time logs** – `time_logs` table (created in earlier phases) stores manual or auto‑detected work sessions.
- **Daily plans** – `daily_plans` table with planned tasks and time slots.
- **Notion AI Agent** – can send prompts to Notion (callout blocks) and receive responses (via polling).
- **CLI** – interactive prompts using `click`.
- **System activity monitoring** – not yet implemented; you will add optional hooks.

Phase 7.5 adds:
- A lightweight activity monitor (keyboard/mouse, IDE usage, or simply a “last activity timestamp” from local git or file system changes).
- A heuristic to detect periods of work without corresponding commits or task updates.
- End‑of‑day prompts (CLI or Notion) asking the user to assign untracked time.
- Storage of responses in `time_logs` with `source = 'prompted'`.
- Adjustment of future plans (reduce remaining hours for the assigned project).

---

## Phase 7.5: Enhanced Verification – Untracked Work & Prompts (1 week)

### Tasks

#### 1. Activity Monitoring (Optional but Recommended)

You will implement **two modes** – a simple mode and an enhanced mode. Start with the simple mode; the enhanced mode can be added later or as an option.

**Simple Mode (File‑system based)**:
- Monitor the last modification time of files in the user’s projects (e.g., `git ls-files` or scan directories).
- Every hour, record the timestamp of the most recent file change.
- If file changes occur but no commits were made to GitHub (check `commits` table for new entries since the last check), consider that as “activity without commits”.

**Enhanced Mode (Optional, cross‑platform)**:
- Use a library like `pynput` to listen for keyboard and mouse events.
- Aggregate activity every 15 minutes; if total activity > threshold (e.g., 5 minutes of typing/mouse movement), mark that period as “active”.
- This is more accurate but requires additional dependencies and may raise privacy concerns. Make it optional and disabled by default.

**For MVP, implement the simple mode** (file‑modification timestamps). It’s sufficient to detect that the user was working, even if they didn’t commit.

Implementation:
- Create `trail/verification/activity_monitor.py` with functions:
  - `get_last_activity_timestamp(project_path) -> datetime` (uses `os.path.getmtime` on project directory).
  - `has_uncommitted_changes(project_id) -> bool` (optional: check local git status; but for simplicity, rely on lack of new commits in the `commits` table).
- The verification worker (from Phase 7) will call this for each project that had planned tasks.

#### 2. Detect Untracked Work Sessions

During the end‑of‑day verification (or a separate job), for each project:

- Retrieve the planned tasks for the day.
- Get the actual commits from GitHub (already fetched).
- Calculate “expected activity” – the sum of planned task durations (or the number of commits expected based on history).
- If the actual commits are **zero** but the file‑modification activity shows recent changes (e.g., files modified within the last 2 hours), then there is “untracked work”.

Define a threshold: if **>2 hours of activity** (file modifications spread over time) without any commits or task status updates, trigger a prompt.

Store detected untracked sessions in a new table `untracked_sessions`:
- `id`, `project_id`, `start_time`, `end_time`, `duration_minutes`, `resolved` (boolean), `assigned_task_id` (nullable), `created_at`.

#### 3. End‑of‑Day Prompt

After the verification worker finishes, if any untracked sessions exist, generate a prompt for the user.

**Prompt content**:
```
⚠️ I noticed you worked on Project B for 2.5 hours today, but I didn't see any commits or task updates.
Which project(s) should this time be assigned to?
  1. Project B (same project)
  2. Project A
  3. Project C
  4. A different project (type name)
  5. Ignore (this was research/meeting)
```

**Delivery channels**:
- **CLI**: If the user is actively using the terminal (e.g., they ran `trail verify` manually), print the prompt and wait for input.
- **Notion**: Send a callout block to the project’s main Notion page (or a dedicated “Trail Inbox” page). The user can reply by typing a command in the same block, e.g., `@ai assign to Project B`.
- **Slack** (optional, if webhook configured).

For Phase 7.5, implement **CLI prompt** first. Notion integration can reuse the Notion AI Agent responder (Phase 5) but extended to handle this specific prompt format.

#### 4. Store User Response

When the user responds, parse the answer:
- If they choose a project, create a new entry in `time_logs`:
  - `project_id` = selected project
  - `task_id` = NULL (or if they mention a specific task, try to match)
  - `start_time` = start of untracked session
  - `end_time` = end of untracked session
  - `duration_minutes` = calculated
  - `task_type` = 'untracked'
  - `source` = 'prompted'
  - `notes` = "Auto-detected untracked work"
- If they choose “Ignore”, mark the `untracked_sessions.resolved = True` and do nothing else.

#### 5. Adjust Future Plans

After logging the untracked time, update the project’s remaining hours:
- Decrease `estimated_remaining_hours` in `project_constraints` by the logged duration (since the work was actually done, even if not committed).
- Optionally, if the user assigned the time to a specific task, reduce that task’s `estimated_minutes` as well.

This ensures that the planner does not over‑schedule work that was already done (but not committed).

#### 6. Add CLI Commands

- `trail untracked list` – show unresolved untracked sessions.
- `trail untracked assign --session-id <id> --project <key>` – manually assign a session.
- `trail untracked ignore --session-id <id>` – mark as resolved without logging.

---

## Success Criteria (Must Verify)

Provide verification steps to confirm:

1. **Detection**: You work on a project for 2 hours (edit files, no commits). At end‑of‑day verification, the system detects an untracked session of ~2 hours.
2. **Prompt**: You receive a CLI prompt (or Notion message) asking to assign the time.
3. **Response**: You assign the time to the same project. A `time_logs` entry is created with `source='prompted'`.
4. **Plan adjustment**: The project’s `estimated_remaining_hours` decreases by 2 hours.
5. **No false positives**: Normal work with commits does not trigger a prompt.

---

## Additional Quality Requirements

- **Privacy**: The activity monitor must not record keystrokes or content, only timestamps and durations. Document this clearly.
- **Configurable thresholds**: The “>2 hours” threshold and the activity sampling interval should be configurable via `user_preferences`.
- **Idempotency**: The same untracked session should not be prompted twice.
- **Graceful degradation**: If the activity monitor cannot determine file modification times (e.g., project path not set), skip detection and log a warning.

---

## Deliverables

You will produce the following files/extensions:

1. **Migration script** `016_add_untracked_sessions.sql` (create `untracked_sessions` table; add `source` column to `time_logs` if not present).
2. **`trail/verification/activity_monitor.py`** – file‑based activity detection.
3. **Updates to `trail/verification/worker.py`** – integrate untracked detection and prompt triggering.
4. **`trail/verification/prompts.py`** – functions to deliver prompts (CLI and Notion) and parse responses.
5. **`trail/verification/plan_adjuster.py`** – update remaining hours and task estimates.
6. **Updated `trail/cli.py`** – add `untracked` command group.
7. **Updated `trail/notion_agent/responder.py`** – extend to handle prompt responses (if using Notion).
8. **Test instructions** (`test_phase7.5.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration script.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 7.5.

---

## Cardinal Sins (What Not to Do)

- **No keylogging or invasive monitoring** – only file modification times, no content.
- **No false positives** – ensure the detection heuristic is conservative (e.g., only trigger if no commits *and* file changes > threshold).
- **No infinite prompts** – once a session is resolved, never prompt again.
- **No broken plan adjustment** – do not reduce remaining hours below zero.
- **No hardcoded thresholds** – make them configurable.

Now, implement Phase 7.5 with excellence. **Trail is counting on you.**