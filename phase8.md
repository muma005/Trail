# Prompt for Qwen to Implement Phase 8 of Trail (Learning & Personalization)

You are an expert software engineer. Your task is to implement **Phase 8: Learning & Personalization** for the **Trail** project. This phase builds on all previous phases (0–7.5) and adds the ability to learn from past task completions, focus patterns, and estimate accuracy to improve future planning.

**No generic or lazy work.** Every component must be robust, data‑driven, and seamlessly integrated with the existing planner and verification systems. You will produce code, database migrations, CLI extensions, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- `notion_tasks` table with `estimated_minutes`, `actual_minutes`, `task_type` (or tags), `size_tag`, `priority`.
- `time_logs` table with `start_time`, `end_time`, `duration_minutes`, `task_type`, `focus_score` (optional).
- `commits` table with `commit_date` (hour of day).
- `project_velocity` table (if created) or similar historical data.
- `daily_plans` and `planned_task_verification` – actual vs. planned task completion.
- Planner (`scheduler.py`, `timeline.py`) – uses estimates and preferences.
- CLI commands: `trail plan today`, `trail progress`, etc.

Phase 8 adds:
- `learned_patterns` table to store multipliers, peak focus hours, and other derived patterns.
- Duration learning: adjust estimate multipliers per task type based on historical variance.
- Focus peak learning: detect which hours of the day you commit most often (or log highest focus scores) and adjust scheduling.
- Empty promise detector: compare initial project estimate vs. actual first‑week velocity; flag over‑optimism and apply automatic multiplier.
- Integration with planner: use learned patterns to adjust future task estimates and preferred deep‑work hours.

---

## Phase 8: Learning & Personalization (1 week)

### Tasks

#### 1. Create `learned_patterns` Table

**Migration script** `017_create_learned_patterns.sql`:

- Columns:
  - `id` UUID PRIMARY KEY
  - `user_id` UUID (for future multi‑user; use a fixed placeholder for now)
  - `pattern_type` VARCHAR(50) – e.g., `duration_multiplier`, `focus_peak_hour`, `empty_promise_multiplier`
  - `context` JSONB – stores parameters such as:
    - For `duration_multiplier`: `{"task_type": "unit_test", "size_tag": "medium"}`
    - For `focus_peak_hour`: `{"hour": 10}`
    - For `empty_promise_multiplier`: `{"project_id": "..."}`
  - `value` DECIMAL(10,4) – the multiplier (e.g., 1.2 means tasks take 20% longer) or the hour (0‑23).
  - `confidence` DECIMAL(5,4) – based on sample count (0‑1).
  - `sample_count` INT – number of data points used.
  - `updated_at` TIMESTAMP
- Index on `(user_id, pattern_type, context)`.

#### 2. Duration Learning

**Goal**: After each completed task, compare `estimated_minutes` vs. `actual_minutes` and update a multiplier for that task type (and size tag).

**Implementation**:

- Create `trail/learning/duration.py` with functions:
  - `update_duration_multiplier(task_id, project_id)`:
    - Fetch the task from `notion_tasks` (estimated_minutes, actual_minutes, size_tag, and any task_type derived from title or tags).
    - Compute ratio = actual / estimated (if estimated > 0).
    - Retrieve existing multiplier from `learned_patterns` where `pattern_type='duration_multiplier'` and context matches `{"task_type": X, "size_tag": Y}`.
    - Update multiplier using exponential moving average: new_multiplier = (old_multiplier * old_count + ratio) / (old_count + 1).
    - Increment sample_count, update confidence = min(1.0, sample_count / 20) (after 20 samples, confidence=1).
    - Store back.
  - `get_duration_multiplier(task_type, size_tag) -> float`:
    - Return the multiplier from `learned_patterns` (default 1.0 if not found).

**Integration**:
- When a task is marked `completed` (e.g., during verification or manual update), call `update_duration_multiplier`.
- Modify the planner (Phase 6) to apply multiplier when fetching task estimates: `adjusted_estimate = original_estimate * multiplier`.

#### 3. Focus Peak Learning

**Goal**: Determine which hour(s) of the day you are most productive (based on commit timestamps or focus scores from `time_logs`), then schedule deep work during those hours.

**Implementation**:

- Create `trail/learning/focus.py` with functions:
  - `update_focus_peaks(user_id)`:
    - Query `commits` for the last 30 days, group by hour of day (0‑23). Count commits per hour.
    - Alternatively, if `time_logs` has `focus_score`, weight by score.
    - Find the hour(s) with highest activity (top 2 hours).
    - Store in `learned_patterns` with `pattern_type='focus_peak_hour'`, context `{"hour": 10}`, `value=1.0` (or rank). Keep multiple rows.
  - `get_focus_peaks() -> list[int]`: returns hours (e.g., [10, 15]).
- Schedule this job to run weekly (Celery Beat) or manually via CLI.

**Integration with planner**:
- In `timeline.py`, when placing deep work units, prefer the focus peak hours. If a deep work unit cannot fit exactly, try to shift it as close as possible.
- If no focus peaks learned yet, fall back to default (e.g., 9‑11 AM).

**CLI command**:
- `trail learning focus` – show current focus peaks.

#### 4. Empty Promise Detector

**Goal**: Detect when a project’s initial estimate is far from reality (actual first‑week velocity > 2× estimate), and apply a multiplier to future tasks for that project.

**Implementation**:

- Create `trail/learning/empty_promise.py` with functions:
  - `check_empty_promise(project_id)`:
    - For the first week after a project is added (or after estimate is set), compare total `estimated_remaining_hours` initially vs. actual hours logged in `time_logs` or `commits` (inferred from activity).
    - If actual > 2 × estimated, compute multiplier = actual / estimated.
    - Store in `learned_patterns` with `pattern_type='empty_promise_multiplier'`, context `{"project_id": project_id}`, value = multiplier.
  - `get_project_multiplier(project_id) -> float`:
    - Return multiplier from `learned_patterns` if exists, else 1.0.
- Run this check weekly or after the first week of a project (via Celery Beat or manually).

**Integration with planner**:
- When fetching project constraints, multiply `estimated_remaining_hours` by the project‑specific multiplier (if any). Also apply to individual task estimates if they belong to that project.

**CLI command**:
- `trail learning empty-promise --project X` – manually check and apply.

#### 5. General CLI for Learning

Add a command group `trail learning` with subcommands:
- `trail learning update-duration` – manually trigger duration learning (usually automatic).
- `trail learning update-focus` – recompute focus peaks.
- `trail learning show` – display all learned patterns (multipliers, focus peaks).
- `trail learning reset --pattern-type duration_multiplier` – reset learning for a specific pattern.

#### 6. Integration Summary

- **Planner** (`scheduler.py`, `task_breaker.py`): use `get_duration_multiplier` for each task’s estimate, and `get_project_multiplier` for remaining hours.
- **Verification** (`verification/worker.py`): after a task is marked complete, call `update_duration_multiplier`.
- **Scheduled jobs**: Weekly job to update focus peaks and check empty promise.

---

## Success Criteria (Must Verify)

Provide verification steps to confirm:

1. **Duration learning**:
   - Create 5 “unit test” tasks, each estimated 60 minutes. Actual times: 70, 65, 75, 68, 72 minutes.
   - After each completion, the multiplier updates. After 5, multiplier ≈ 1.18 (error < 20% from true average).
   - Next unit test task estimate is adjusted to ~70 minutes.

2. **Focus peak learning**:
   - Make commits at 10 AM and 3 PM over several days (more than other hours).
   - Run `trail learning update-focus`. The focus peaks should include 10 and 15.
   - Generate a daily plan with deep work tasks – they should be scheduled around 10 AM and 3 PM if possible.

3. **Empty promise detector**:
   - Create a new project with estimate 10 hours. During first week, log 25 hours of actual work.
   - Run `trail learning empty-promise --project X`. Multiplier = 2.5.
   - Planner now shows remaining hours multiplied by 2.5.

4. All learned patterns are stored in `learned_patterns` table with proper context and confidence.

---

## Additional Quality Requirements

- **Idempotency**: Running learning functions multiple times should produce stable results (no double‑counting).
- **Configurable thresholds**: The “>2×” threshold for empty promise, the number of top focus peaks (default 2), and the moving average decay should be configurable via `user_preferences`.
- **Graceful degradation**: If there is insufficient data (e.g., no tasks completed yet), return default multiplier 1.0 and log a warning.
- **Performance**: Learning jobs should run in <1 second for typical data sizes (<1000 tasks).

---

## Deliverables

You will produce the following files/extensions:

1. 

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration script.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 8.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded learning rates** – use exponential moving average with configurable alpha.
- **No ignoring confidence** – low‑confidence multipliers should not dominate planning; use a fallback to default 1.0 until confidence >0.5.
- **No mixing of pattern types** – keep context JSON clean and well‑documented.
- **No infinite storage** – limit the number of patterns per user (e.g., keep only top 5 focus peaks).
- **No silent failures** – if learning function fails, log error and continue without updating.

Now, implement Phase 8 with excellence. **Trail is counting on you.**