# Prompt for Qwen to Implement Phase 6.5 of Trail (Enhanced Planner – Dependencies, Calendar, Switch Costs)

You are an expert software engineer. Your task is to implement **Phase 6.5: Enhanced Planner** for the **Trail** project. This phase builds on Phase 6 (Smart Work Planner – Core) and adds calendar awareness, holiday support, dependency‑aware scheduling, context switch penalties, and quick task batching.

**No generic or lazy work.** Every feature must be robust, production‑ready, and well‑tested. You will produce code, database migrations, CLI extensions, and verification steps.

---

## Context (What Already Exists)

From Phase 6:
- `user_preferences` with `work_start`, `work_end`, `lunch_start`, `lunch_end`, `max_parallel_projects`, `constant_project_id`, `deep_work_minutes`.
- `project_constraints` table with `estimated_remaining_hours`, `deadline`, `priority`, `is_constant`.
- `task_dependencies` table (created in Phase 2.5) with `task_id`, `depends_on_task_id`, `depends_on_project_id`, `dependency_type`.
- `sub_tasks` table.
- `daily_plans` table (if implemented) or at least plan generation functions.
- CLI command `trail plan today` that produces a timeline.

Phase 6.5 adds:
- Google Calendar integration (read‑only) to block meeting times.
- `user_time_off` table for holidays and PTO.
- Dependency‑aware scheduling (respect `task_dependencies`, including cross‑project).
- `switch_costs` table to add buffers when switching between projects.
- Quick task batching (already partially in Phase 6; now formalised).

---

## Phase 6.5: Enhanced Planner (2 weeks)

### Week 1 – Calendar & Holidays

#### Tasks

1. **Integrate Google Calendar API (read‑only)**:
   - Use Google Calendar API v3 with OAuth 2.0.
   - Add instructions for setting up a Google Cloud project, enabling Calendar API, and creating OAuth credentials (stored in `.env`).
   - Implement `trail/planner/calendar.py` with functions:
     - `authenticate_google() -> service` (using `google-auth-oauthlib` and `googleapiclient`).
     - `fetch_events(calendar_id='primary', days_ahead=7) -> list[dict]`: returns events with `start`, `end`, `summary`.
   - Cache events in Redis for 1 hour to avoid repeated API calls.

2. **Block meeting times in the planner**:
   - Modify `generate_timeline` (from Phase 6) to accept a list of busy slots.
   - For each busy slot (meeting), ensure no work is scheduled during that time.
   - If a meeting overlaps with a planned work block, shift the work block to an adjacent free slot (or to the next day if no room).

3. **Add `user_time_off` table** (migration `013_add_user_time_off.sql`):
   - Columns: `id`, `user_id` (for future multi‑user; use a fixed UUID for now), `start_date` DATE, `end_date` DATE, `reason` VARCHAR(100), `is_working BOOLEAN DEFAULT FALSE`.
   - Add CLI command: `trail timeoff add --start YYYY-MM-DD --end YYYY-MM-DD --reason "Vacation"`.
   - Also `trail timeoff list` and `trail timeoff remove`.

4. **Planner integration**:
   - When generating a plan for a date, check if the date falls within any `user_time_off` range. If yes, skip the day entirely (no work scheduled).
   - If meetings occupy more than 50% of the available work hours (after excluding lunch and breaks), reduce the planned work by the excess and show a warning: “Meetings take 4 of 6 work hours today. Reduced plan from 6h to 2h.”

**Week 1 Success Criteria**:
- After authenticating with Google, `fetch_events` returns real calendar events.
- A meeting at 2 PM blocks that hour in the generated timeline.
- Marking a day as time‑off results in no tasks scheduled for that day.
- When meetings exceed 50% of work hours, the plan is reduced and a warning is shown.

---

### Week 2 – Dependencies & Switch Costs

#### Tasks

1. **Dependency‑aware scheduling**:
   - Modify the scheduling algorithm (from Phase 6) to respect `task_dependencies`.
   - Before allocating hours to projects, build a **task graph** for each project (and cross‑project).
   - Topologically sort tasks: a task can only be scheduled **after** all its dependencies are completed (or estimated to be completed).
   - For cross‑project dependencies (e.g., Task B in Project B depends on Task A in Project A), the planner must ensure that the dependent task is scheduled after the estimated completion date of the prerequisite task.
   - If a prerequisite has no estimated completion (e.g., no deadline, no remaining hours), show a warning and treat it as “unknown” (schedule the dependent task later in the week).

2. **Switch cost penalties**:
   - Create `switch_costs` table (already defined in master schema; ensure it exists).
   - Columns: `from_project_id`, `to_project_id`, `penalty_minutes` (default 10), `sample_count`, `updated_at`.
   - Add default row: any `from` to any `to` = 10 minutes (if no specific cost).
   - In the timeline generator, when switching from one project to another, insert a **context switch buffer** of `penalty_minutes` between the two blocks.
   - Example: Finish Project A at 11:00, then 10‑min buffer, then start Project B at 11:10.
   - Do not add buffer if the same project continues.

3. **Quick task batching (formalised)**:
   - Already partially done in Phase 6; now ensure it is robust.
   - Collect all tasks with `size_tag = 'quick'` from all projects scheduled for the day.
   - Batch them into 30‑minute slots (each slot can contain up to 6 quick tasks, assuming 5 minutes per task). Use a configurable `quick_batch_duration` (default 30 minutes).
   - Schedule these batch slots in the afternoon (or whenever shallow work is preferred).

4. **Update CLI commands**:
   - Add `trail plan today --with-deps` (optional flag to show dependency resolution details).
   - Add `trail switch-cost set --from A --to B --minutes 15` to manually adjust switch costs.

**Week 2 Success Criteria**:
- Task B that depends on Task A is scheduled after Task A’s estimated completion (same project or cross‑project).
- Switching from Project A to Project B inserts a 10‑minute buffer (default).
- Quick tasks from multiple projects are batched into 30‑minute slots.
- `trail plan today` output shows the buffer as “Context switch” or similar.

---

## Additional Quality Requirements

- **Idempotency**: Running the planner twice with the same data should produce identical timelines (except for random tie‑breaks).
- **Error handling**: If Google Calendar authentication fails, the planner should fall back to no calendar data (and log a warning). If a task dependency cycle is detected (e.g., A → B → A), break the cycle by ignoring the problematic dependency and log an error.
- **Performance**: Fetching calendar events and dependencies should add no more than 2 seconds to plan generation.
- **Configuration**: All thresholds (e.g., meeting occupancy threshold 50%, quick batch duration 30 min) should be in `user_preferences` or a `planner_config` table.
- **Testing**: Provide manual test instructions (e.g., create two tasks with dependencies, set a meeting via Google Calendar, run planner, verify output).

---

## Deliverables

You will produce the following files/extensions:

1. **Migration scripts**:
   - `013_add_user_time_off.sql`
   - `014_ensure_switch_costs.sql` (create `switch_costs` if not exists)
2. **`trail/planner/calendar.py`** – Google Calendar integration.
3. **Updates to `trail/planner/scheduler.py`** – dependency‑aware allocation.
4. **Updates to `trail/planner/timeline.py`** – insert switch buffers, batch quick tasks, respect meetings and time‑off.
5. **`trail/planner/deps.py`** – topological sort of tasks.
6. **Updated `trail/cli.py`** – add `timeoff` commands, `switch-cost` commands, and `plan today` enhancements.
7. **Updated `requirements.txt`** – add `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`.
8. **Test instructions** (`test_phase6.5.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration scripts.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 6.5.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded OAuth credentials** – must be read from `.env` or a secure file.
- **No ignoring dependency cycles** – detect and report them.
- **No adding switch buffers when no switch occurs** – only between different projects.
- **No scheduling work during meetings** – strictly block those slots.
- **No infinite loops in topological sort** – use Kahn’s algorithm with cycle detection.

Now, implement Phase 6.5 with excellence. **Trail is counting on you.**