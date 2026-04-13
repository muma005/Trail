# Prompt for Qwen to Implement Phase 7 of Trail (Verification & Auto‑Reassignment)

You are an expert software engineer. Your task is to implement **Phase 7: Verification & Auto‑Reassignment** for the **Trail** project. This phase builds on all previous phases (0–6.5). It adds the ability to compare planned work against actual activity (commits, task status) and automatically reschedule incomplete or partially completed tasks.

**No generic or lazy work.** Every component must be robust, handle real‑world data, and integrate seamlessly with existing systems (GitHub API, Notion API, planner, scheduler). You will produce code, database migrations, CLI extensions, background jobs, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- **Daily plans** – `daily_plans` table (or in‑memory generation) stores tasks planned for each day with start/end times.
- **GitHub sync** – `commits` table with project links, SHAs, timestamps.
- **Notion sync** – `notion_tasks` table with status, progress, sub‑tasks.
- **Planner** – `scheduler.py`, `task_breaker.py`, `timeline.py` (Phase 6 & 6.5).
- **Celery Beat** – used for scheduled syncs and other background jobs.
- **Notion AI Agent** (Phase 5) – can send messages to Notion (callout blocks). Used for user proposals.
- **CLI** – `trail plan today`, `trail sync`, etc.

Phase 7 adds:
- `planned_task_verification` table to track what was planned vs. what actually happened.
- An end‑of‑day verification worker that checks each planned task against GitHub commits and Notion status.
- Partial progress detection (e.g., 1 commit out of expected 3 → 30% done).
- Auto‑reassignment engine that updates remaining hours and reschedules leftover work.
- User notification (CLI and/or Notion) with proposal to accept/reject changes.

---

## Phase 7: Verification & Auto‑Reassignment (1.5 weeks)

### Week 1 – Verification Worker

#### Tasks

1. **Create `planned_task_verification` table** (migration `015_create_planned_task_verification.sql`):
   - Columns (as defined in master schema):
     - `id` UUID PRIMARY KEY
     - `daily_plan_id` UUID REFERENCES `daily_plans(id)`
     - `task_id` UUID REFERENCES `notion_tasks(id)`
     - `expected_commit_sha` VARCHAR(40) NULL (if task expected to produce a specific commit – optional)
     - `expected_status_change` VARCHAR(50) (e.g., 'Done', 'In Progress')
     - `actual_commit_sha` VARCHAR(40) NULL
     - `actual_status` VARCHAR(50) NULL
     - `verified_at` TIMESTAMP
     - `was_completed` BOOLEAN DEFAULT FALSE
     - `partial_progress_percentage` DECIMAL(5,2) NULL
     - `remaining_estimate_minutes` INT NULL
     - `detection_method` VARCHAR(50) ('commits', 'status', 'subtasks', 'llm')
     - `missed_reason` TEXT
     - `reassigned_to_plan_id` UUID REFERENCES `daily_plans(id)` NULL
     - `created_at` TIMESTAMP DEFAULT NOW()
   - Index on `daily_plan_id`, `task_id`, `verified_at`.

2. **Create end‑of‑day verification worker**:
   - File: `trail/verification/worker.py`
   - This worker should be triggered daily (e.g., via Celery Beat at 23:59) or can be run manually via CLI.
   - For each active project, fetch the `daily_plan` for **today** (if exists).
   - For each planned task in that plan:
     - **Query GitHub**: Get all commits in the project since the task’s planned start time (use `commits` table). Filter by commit timestamp >= planned_start. Count commits and collect SHAs.
     - **Query Notion**: Fetch the current status of the task (from `notion_tasks`). Also check if `progress_percentage` field changed.
     - **Determine completion status**:
       - **Complete** if:
         - Notion status = 'Done', OR
         - A commit message contains `closes #task-id` or similar, OR
         - All sub‑tasks are completed (from `sub_tasks` table).
       - **Partial** if:
         - At least one commit exists but status not 'Done', OR
         - Sub‑tasks progress > 0% but < 100%, OR
         - Notion progress percentage > 0 and < 100.
       - **No progress** otherwise.
     - Compute `partial_progress_percentage`:
       - If Notion has a `progress_percentage` field, use that.
       - Else if sub‑tasks exist: (completed_subtasks / total_subtasks) * 100.
       - Else if commits exist: heuristic based on typical commit count for similar tasks (from `learned_patterns`). For MVP, use a simple rule: 1 commit → 30%, 2 commits → 50%, 3+ commits → 70% (configurable).
       - If no data, set to 0% (no progress).
     - Store verification result in `planned_task_verification`.

3. **Add CLI command for manual verification**:
   - `trail verify today` – runs the verification worker for today’s plan.
   - `trail verify --date YYYY-MM-DD` – for any past date.

**Week 1 Success Criteria**:
- After running `trail verify today`, the `planned_task_verification` table contains rows for each planned task.
- A task with no commits and status 'Not Started' → `was_completed=FALSE`, `partial_progress_percentage=0`.
- A task with 1 commit and status 'In Progress' → `was_completed=FALSE`, `partial_progress_percentage=30` (or heuristic value).
- A task with status 'Done' → `was_completed=TRUE`.

---

### Week 2 (0.5) – Auto‑Reassignment

#### Tasks

1. **Estimate remaining hours after partial progress**:
   - Function `estimate_remaining(original_estimate_minutes, partial_percentage, task_metadata)` in `trail/verification/remaining.py`.
   - If partial_percentage > 0: remaining = original_estimate * (1 - partial_percentage/100).
   - If partial_percentage = 0: remaining = original_estimate (full task).
   - If task is completed: remaining = 0.
   - For tasks with no original estimate, use default 60 minutes per task or fetch from `learned_patterns`.

2. **Update project backlog**:
   - For each partially completed or missed task, add `remaining` minutes back to the project’s `estimated_remaining_hours` in `project_constraints`.
   - Also mark the task as still pending (do not change its Notion status unless the user accepts the reassignment).

3. **Re‑run scheduler for remaining days**:
   - Call the scheduler (from Phase 6) to generate new plans for the next N days (e.g., tomorrow and the day after, or for the rest of the week).
   - Insert the leftover tasks into the earliest available slots, respecting:
     - Max parallel projects
     - Constant project
     - Dependencies (including cross‑project)
     - Switch costs
     - Meetings and time‑off (already handled by scheduler)
   - Generate updated `daily_plans` rows for the affected days.

4. **Send proposal to user**:
   - Create a summary of changes: “Task X was partially completed (40% done). Remaining 1.2 hours moved to tomorrow at 10:00 AM. Accept? (y/n/edit)”
   - Deliver proposal via:
     - **CLI** (if user is active): print to stdout and wait for input (use `click.confirm`).
     - **Notion** (if user prefers): send a callout block to the project’s main Notion page (or a dedicated “Trail Proposals” page). Use the Notion AI Agent’s response writer.
     - **Slack** (optional, if webhook configured).
   - User can accept (apply changes), reject (keep original plan), or edit (e.g., change the reassigned time).

5. **If accepted**:
   - Update `daily_plans` with new assignments.
   - Update `planned_task_verification.reassigned_to_plan_id`.
   - Optionally, send a confirmation: “Plan updated. Tomorrow’s plan now includes the remaining work.”
   - If rejected, keep the original plan (the task remains in its original day as missed; user will handle manually).

6. **Add CLI command**:
   - `trail reassign --dry-run` to preview changes without applying.
   - `trail reassign --accept` to apply all pending proposals automatically (for non‑interactive use).

**Week 2 Success Criteria**:
- A task with 1 commit and 0% progress in Notion → partial_percentage=30% → remaining = 70% of original estimate → backlog updated.
- The scheduler places the remaining task into tomorrow’s plan at an available time slot.
- User receives a proposal (CLI or Notion) and can accept.
- After acceptance, `daily_plans` for tomorrow includes the task.

---

## Additional Quality Requirements

- **Idempotency**: Running verification twice on the same day should not duplicate rows (use `ON CONFLICT` or check existence).
- **Accuracy of partial progress**: For MVP, the simple commit‑count heuristic is acceptable, but the system must be ready to replace it with ML later (Phase 8). Document the heuristic.
- **Graceful failure**: If GitHub or Notion API fails during verification, log the error and skip that task (do not mark as no progress). Allow manual retry.
- **User control**: The auto‑reassignment must be **opt‑in** (user must accept) unless a `--force` flag is used.
- **Logging**: Log each verification and reassignment action with sufficient detail for debugging.

---

## Deliverables

You will produce the following files/extensions:

1. **Migration script** `015_create_planned_task_verification.sql`.
2. **`trail/verification/worker.py`** – verification logic.
3. **`trail/verification/remaining.py`** – remaining hours estimation.
4. **`trail/verification/reassign.py`** – auto‑reassignment and proposal logic.
5. **Updates to `trail/planner/scheduler.py`** – ensure it can accept a list of forced tasks (the leftover ones) to insert into future plans.
6. **Updated `trail/cli.py`** – add `verify`, `reassign` commands.
7. **Updated Celery tasks** – add periodic end‑of‑day verification job.
8. **Test instructions** (`test_phase7.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration script.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 7.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded partial progress heuristic** – make it configurable (e.g., via `user_preferences.partial_commit_weight`).
- **No silent overwriting of user’s plan** – always ask for confirmation unless `--force`.
- **No missing edge cases** – handle tasks with zero original estimate, tasks that were completed before the planned start time, etc.
- **No broken daily plan retrieval** – ensure `daily_plans` table is populated by Phase 6; if not, generate plans on‑the‑fly for verification purposes (but better to have stored plans).
- **No ignoring cross‑project dependencies during reassignment** – the scheduler must respect them.

Now, implement Phase 7 with excellence. **Trail is counting on you.**