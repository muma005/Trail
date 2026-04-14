# Prompt for Qwen to Implement Phase 9.5 of Trail (Brain Hardening – Cost, Cache & Single Interface)

You are an expert software engineer. Your task is to implement **Phase 9.5: Brain Hardening – Cost, Cache & Single Interface** for the **Trail** project. This phase builds on Phase 9 (AI Brain – Conversation & Memory) and adds cost control, a unified interface (all commands go through `trail brain`), and gamification.

**No generic or lazy work.** Every component must be robust, user‑friendly, and integrate seamlessly with the existing AI Brain, planner, and verification systems. You will produce code, database migrations, CLI changes, and verification steps.

---

## Context (What Already Exists)

From Phase 9 and earlier:
- **AI Brain** – conversational interface with ReAct loop, tool registry, conversation memory (vector embeddings).
- **CLI** – many direct commands: `trail report`, `trail plan`, `trail sync`, `trail verify`, `trail progress`, etc.
- **OpenRouter integration** – tiered LLM routing, budget tracking via `budget_tracking` table (created in Phase 5.5 or earlier).
- **User preferences** – `user_preferences` table with `llm_budget_monthly_usd` (default $10).
- **Notion AI Agent** – `@ai` commands already use the Brain.
- **Verification & reassignment** – daily plans, adherence scores (from `daily_plans.adherence_score`).

Phase 9.5 adds:
- **Single interface enforcement** – deprecate all direct commands; everything must go through `trail brain`.
- **Budget alerts** – when monthly LLM spend reaches 80% of limit, send a warning to the user (via Notion or CLI).
- **Gamification** – points for plan adherence, streaks, badges; store in `user_achievements` table.
- **Slack integration placeholder** – `trail brain --channel slack` for future extension.

---

## Phase 9.5: Brain Hardening – Cost, Cache & Single Interface (1 week)

### Tasks

#### 1. Enforce Single Interface (Deprecate Direct Commands)

**Goal**: All user interaction must go through `trail brain`. Direct commands like `trail report`, `trail plan today`, `trail sync`, etc., should either be removed or show a deprecation warning and redirect to the Brain.

**Implementation**:

- In `trail/cli.py`, for each existing command (except `brain` itself and maybe `init`, `config`), modify the function to:
  - Print a deprecation warning: “⚠️ This command is deprecated. Please use `trail brain "your request"` instead.”
  - Then automatically call the AI Brain with a generated natural language query that mimics the original command.
  - Example: `trail report --project X` → internally calls `trail brain "generate a resumption report for project X"`.
- For commands that have no direct natural language equivalent, map them to appropriate Brain queries.
- Keep `trail brain` as the primary entry point. Also keep `trail config` and `trail init` (setup) as exceptions.
- Document the change in the README and CLI help.

**Alternatively** (simpler for MVP): remove all command groups except `brain`, `config`, and `init`. But the requirement says “deprecate” not necessarily remove. Provide deprecation warnings and forward.

#### 2. Budget Alert System

**Goal**: Monitor monthly LLM spend (from `budget_tracking` table) and send an alert when it reaches 80% of `llm_budget_monthly_usd`.

**Implementation**:

- Create `trail/brain/budget.py` with functions:
  - `get_current_month_spend() -> float` – sums `cost` from `budget_tracking` where `timestamp` is within current month.
  - `check_budget_alert()` – retrieves `llm_budget_monthly_usd` from `user_preferences`, compares current spend. If spend >= 0.8 * budget, trigger alert.
  - `send_budget_alert()` – send a message via the user’s preferred channel (Notion or CLI). Use the same delivery mechanism as morning briefing (Phase 9).
- Schedule a daily check (Celery Beat) to run `check_budget_alert()`.
- Also check after each LLM call (in `react.py` or `llm_analyzer.py`) – if the threshold is crossed, send an immediate alert.

**Alert message example**:
```
⚠️ Budget Alert: You have spent $8.00 of your $10.00 monthly LLM budget (80%).
Consider switching to cheaper models or reducing usage.
```

#### 3. Gamification – Points, Streaks, Badges

**Goal**: Encourage plan adherence by awarding points, tracking streaks, and issuing badges.

**Database**:
- Create `user_achievements` table (migration `019_create_user_achievements.sql`):
  - `id` UUID PRIMARY KEY
  - `user_id` UUID (fixed for now)
  - `achievement_type` VARCHAR(50) – 'streak', 'badge', 'points'
  - `achievement_name` VARCHAR(100) – e.g., '7_day_streak', 'plan_adherence_master'
  - `value` INT (e.g., points count, streak length)
  - `earned_at` TIMESTAMP
  - `metadata` JSONB (optional)

**Implementation** (`trail/gamification.py`):

- **Points**:
  - Each day, compute `adherence_score` from `daily_plans` (if stored). Award points:
    - 100% adherence → 10 points
    - 80‑99% → 5 points
    - 50‑79% → 2 points
    - <50% → 0 points
  - Also award 1 point per completed task (from verification).
  - Store total points in `user_preferences` (new column `total_points`), or keep running total in `user_achievements` with `achievement_type='points'`.

- **Streaks**:
  - Track consecutive days with adherence_score >= 80% (or any completed plan).
  - Store current streak length and longest streak in `user_preferences`.
  - When a streak reaches 7, 14, 30, 60 days, award a badge.

- **Badges**:
  - Predefined badges: `First_Week_Streak` (7 days), `Perfect_Week` (5 days 100% adherence), `Early_Bird` (completed plan before 2 PM – optional), `Project_Finisher` (completed a project ahead of schedule), etc.
  - When a badge condition is met, insert a record into `user_achievements`.

**Integration**:
- After end‑of‑day verification (Phase 7), compute adherence and update points/streaks.
- After a project is marked complete (all tasks done), award `Project_Finisher` badge.

**CLI commands**:
- `trail brain "show my stats"` – the Brain can query `user_achievements` and `user_preferences` to display points, streak, badges.
- `trail brain "leaderboard"` (optional, for future multi‑user) – not needed for MVP.

#### 4. Slack Integration Placeholder

**Goal**: Prepare for future Slack integration without fully implementing it.

**Implementation**:

- Add a `--channel` flag to `trail brain`:
  - `trail brain "query" --channel slack` – currently, just print a message: “Slack integration not yet implemented. Set SLACK_WEBHOOK_URL to enable.”
- In `trail/brain/briefing.py` and `trail/brain/budget.py`, add a conditional: if `SLACK_WEBHOOK_URL` is set in `.env`, send messages to Slack as well as Notion. For now, only implement the placeholder (log a warning that Slack is not configured).
- Update `.env.example` with `SLACK_WEBHOOK_URL=` commented out.

#### 5. Deprecate Direct Commands – Updated CLI

Modify `cli.py` to:

- Keep `trail brain` as the main command.
- For other commands (`report`, `plan`, `sync`, `verify`, `progress`, etc.), either:
  - Remove them entirely (and update documentation), or
  - Implement a forwarding mechanism as described in Task 1.

**Choose the forwarding approach** for backward compatibility. This is less disruptive.

---

## Success Criteria (Must Verify)

1. **Single interface**:
   - Running `trail report --project X` prints a deprecation warning and then (via forwarding) produces the same report as `trail brain "generate report for X"`.
   - `trail brain "generate report for X"` works directly.

2. **Budget alert**:
   - Set `llm_budget_monthly_usd = 10` and manually insert $8 of costs into `budget_tracking` (or simulate LLM calls until threshold reached). The alert triggers and sends a message (check Notion or CLI output).

3. **Gamification**:
   - After 7 consecutive days of plan adherence >=80%, a badge `7_day_streak` appears in `user_achievements`.
   - Running `trail brain "show my stats"` returns current points, streak, and badges.

4. **Slack placeholder**:
   - `trail brain "hello" --channel slack` prints the placeholder message.

---

## Additional Quality Requirements

- **Idempotency**: Points and badges should be awarded only once per condition (e.g., a streak badge only when first achieved, not every day).
- **Configurable thresholds**: Adherence score thresholds for points and streak definition should be in `user_preferences`.
- **No spam**: Budget alerts should be sent at most once per day (or once per threshold crossing).
- **Graceful degradation**: If the `user_achievements` table is missing, gamification should be skipped without crashing.

---

## Deliverables

You will produce the following files/extensions:

1. *

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration script.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 9.5.

---

## Cardinal Sins (What Not to Do)

- **No breaking existing workflows** – forwarding must preserve functionality.
- **No duplicate badge awards** – check if already earned.
- **No hardcoded budget thresholds** – read from `user_preferences`.
- **No ignoring the fact that `trail brain` may already have its own flags** – add `--channel` without breaking existing usage.
- **No incomplete deprecation warnings** – every direct command must warn.

Now, implement Phase 9.5 with excellence. **Trail is counting on you.**