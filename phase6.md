# Prompt for Qwen to Implement Phase 6 of Trail (Smart Work Planner – Core)

You are an expert software engineer. Your task is to implement **Phase 6: Smart Work Planner – Core** for the **Trail** project. This phase builds on all previous phases (0–5). It adds the ability to generate daily and weekly work plans based on project constraints, user preferences, and task estimates.

**No generic or lazy work.** Every function must be robust, handle edge cases, and be production‑ready. You will produce code, database migrations, CLI extensions, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- `projects` table with `id`, `project_key`, `name`, `deadline`, `priority`, `is_constant` (add if missing).
- `notion_tasks` table with `estimated_minutes`, `size_tag`, `status`, `due_date`.
- `user_preferences` table with `work_start`, `work_end`, `lunch_start`, `lunch_end`, `timezone`.
- `project_snapshots` for progress history.
- CLI commands: `trail sync`, `trail progress`, `trail report`, etc.
- Notion integration to fetch tasks.

Phase 6 adds:
- Extended user preferences for planning (max parallel projects, constant project, deep work duration).
- `project_constraints` table to store per‑project planning data (deadline, estimated remaining hours, priority, is_constant).
- CLI to set project estimates.
- A scheduling algorithm (time‑weighted round robin).
- Task breaker to split tasks into daily work units.
- Daily plan generator with timeline.

---

## Phase 6: Smart Work Planner – Core (3 weeks)

### Week 1 – User Profile & Constraints

#### Tasks

1. **Extend `user_preferences` table** (migration `010_add_planner_preferences.sql`):
   - Add columns:
     - `max_parallel_projects INT DEFAULT 2`
     - `constant_project_id UUID REFERENCES projects(id)` (nullable)
     - `deep_work_minutes INT DEFAULT 120` (preferred length of deep work blocks)
   - Also ensure `work_start`, `work_end`, `lunch_start`, `lunch_end` exist (from Phase 0).

2. **Create `project_constraints` table**:
   - Columns:
     - `id` UUID PRIMARY KEY
     - `project_id` UUID UNIQUE REFERENCES projects(id) ON DELETE CASCADE
     - `estimated_remaining_hours DECIMAL(10,2) NOT NULL`
     - `deadline DATE` (nullable)
     - `priority` VARCHAR(20) DEFAULT 'Medium' (Critical, High, Medium, Low)
     - `is_constant BOOLEAN DEFAULT FALSE` (overrides project's own `is_constant` if needed)
     - `updated_at` TIMESTAMP
   - This table stores planning‑specific data that may differ from the project's static attributes (e.g., remaining hours change over time).

3. **Add CLI command `trail project estimate`**:
   - Usage: `trail project estimate --project <key> --hours <hours> [--deadline YYYY-MM-DD] [--priority High] [--constant]`
   - Updates or inserts into `project_constraints`.
   - If `--deadline` is not provided, keep existing or set NULL.
   - Show current estimate after update.

4. **Add CLI command `trail project constraints`**:
   - List all projects with their constraints (remaining hours, deadline, priority, constant flag).

**Week 1 Success Criteria**:
- `user_preferences` has new columns (can be set via SQL or a config CLI – for now, manual SQL update is acceptable, but provide instructions).
- `project_constraints` table exists.
- `trail project estimate` inserts/updates a constraint row.
- `trail project constraints` displays the data correctly.

---

### Week 2 – Scheduling Algorithm (Time‑Weighted Round Robin)

#### Overview
Implement a planner that generates a **daily plan** (list of tasks per project with allocated hours) for a given date, respecting:
- User's working hours and breaks.
- Maximum parallel projects per day.
- Constant project (if set) appears every day with a minimum allocation.
- Projects are allocated hours based on urgency (days until deadline) and remaining work.

#### Tasks

1. **Create `trail/planner/scheduler.py`** with functions:
   - `get_user_available_hours(date) -> int`: compute total work minutes for the day (excluding lunch, breaks). Use `user_preferences`.
   - `get_project_urgency(project_id, current_date) -> float`: urgency = 1 / (max(1, days_until_deadline)) or similar. Higher urgency = more hours.
   - `allocate_hours(projects, total_available_hours, constant_project_id, max_parallel) -> dict[project_id, hours]`:
     - Constant project gets 40% of total hours (or a fixed minimum, e.g., 2 hours, whichever is larger).
     - Remaining hours distributed among other active projects proportionally to their urgency.
     - Ensure no more than `max_parallel` projects are scheduled per day (if more projects exist, pick the top N by urgency).
   - Return a dictionary mapping project_id to allocated hours.

2. **Integrate with project constraints**:
   - Fetch all projects with `estimated_remaining_hours > 0` and not archived.
   - For each, get deadline, priority, and constant flag from `project_constraints` (fallback to `projects` table if not set).

3. **Create CLI command `trail plan today`**:
   - Calls `allocate_hours` for the current date.
   - Prints a summary: “Today’s plan: Project A (3h), Project B (2h), Project C (1h). Total 6h (within 8h workday).”

4. **Add a simple test** to verify that constant project always appears and that total hours ≤ available.

**Week 2 Success Criteria**:
- `trail plan today` outputs a feasible allocation (hours per project) that respects max parallel projects.
- If constant project is set, it always receives at least 2 hours (or 40% of available, whichever is greater).
- Total allocated hours do not exceed user’s available working hours (after lunch/breaks).

---

### Week 3 – Task Breaker & Daily Generator

#### Goal
Convert allocated hours into a **timeline** with specific tasks (from Notion) broken into work units, respecting deep work preferences.

#### Tasks

1. **Fetch incomplete tasks for each project**:
   - From `notion_tasks`, get tasks where `status != 'Done'` and `project_id` in the planned set.
   - Order by priority (Critical first, then High, etc.) and due date.

2. **Split tasks into work units**:
   - Function `break_into_work_units(project_id, allocated_hours, task_list) -> list[WorkUnit]`:
     - Each work unit has: `task_id`, `title`, `estimated_minutes`, `type` (deep/shallow based on task size: 'quick' tasks are shallow, 'large' tasks are deep).
     - Combine small tasks (`#quick`) into a single “batch” unit (max 30 minutes).
     - Split large tasks (>4 hours) into 2‑hour chunks (with note “Part 1/2”).
   - Store work units in memory (no database table needed for MVP, but you may create a `planned_work_units` table later for verification).

3. **Generate daily timeline**:
   - Function `generate_timeline(work_units, user_preferences, date)`:
     - Use `work_start`, `lunch_start`, `lunch_end`, `work_end`.
     - Schedule deep work units in the morning (before lunch) if possible.
     - Schedule shallow work units (including quick task batches) in the afternoon.
     - Add 5‑minute breaks between units (optional).
     - Ensure no unit exceeds `deep_work_minutes` (if a deep unit is longer, split it).
   - Return a list of time slots: `[ {start_time, end_time, task_title, project_name, type} ]`.

4. **Create CLI command `trail plan today --detail`**:
   - Shows the timeline with time blocks.
   - Example output:
     ```
     Today's detailed plan (2026-04-13):
     09:00 – 11:00  [Deep] Project A: Implement JWT refresh (2h)
     11:00 – 11:15  Break
     11:15 – 12:30  [Shallow] Project B: Write API tests (1.25h)
     12:30 – 13:30  Lunch
     13:30 – 14:30  [Shallow] Project A: Review PR #42 (1h)
     14:30 – 15:00  [Shallow] Project C: Quick tasks (docs, email)
     15:00 – 17:00  Buffer / Overflow
     ```

5. **Store the daily plan** (optional for now, but good for future verification):
   - Create a `daily_plans` table (as defined in the master schema) and insert the generated plan.

**Week 3 Success Criteria**:
- `trail plan today --detail` produces a realistic timeline with tasks.
- Deep work tasks appear before lunch.
- Total planned minutes match allocated hours.
- Quick tasks are batched together.
- If a project has no incomplete tasks, it is not scheduled (or a note is shown).

---

## Additional Quality Requirements

- **Idempotency**: Running `trail plan today` multiple times should produce the same plan (unless data changed).
- **Error handling**: If a project has no tasks but has remaining hours, show a warning.
- **Configuration**: All parameters (e.g., constant project share 40%, min constant hours 2) should be configurable in `user_preferences` or a separate `planner_config` table.
- **Logging**: Log plan generation for debugging.
- **Testing**: Provide manual test instructions (create a project with tasks, set estimates, run planner, verify output).

---

## Deliverables



---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration scripts.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 6.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded percentages** – make constant project share and min hours configurable.
- **No ignoring user preferences** – respect work hours, lunch, deep work duration.
- **No scheduling more than max_parallel projects** – enforce the limit.
- **No infinite loops** – task breaker must terminate.
- **No missing edge cases** – if no tasks, handle gracefully; if no remaining hours, skip.

Now, implement Phase 6 with excellence. **Trail is counting on you.**