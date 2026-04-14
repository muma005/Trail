# Prompt for Qwen to Implement Phase 10 of Trail (Cross‑Project Orchestration & Scaling)

You are an expert software engineer. Your task is to implement **Phase 10: Cross‑Project Orchestration & Scaling** for the **Trail** project. This phase builds on all previous phases (0–9.5) and adds the ability to handle dependencies and resource leveling across many projects simultaneously, plus performance testing for up to 50 projects.

**No generic or lazy work.** This is the final major engineering phase before deployment. Every component must be robust, scalable, and deeply integrated with the existing scheduler, dependency system, and AI Brain. You will produce code, CLI extensions, performance tests, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- **Planner** – `scheduler.py` allocates hours per project (time‑weighted round robin) but processes projects sequentially.
- **Dependencies** – `task_dependencies` table with cross‑project support; `scheduler` respects topological order within a project but not globally across all projects.
- **Daily plans** – `daily_plans` table stores tasks per day per project.
- **User preferences** – `max_parallel_projects`, `work_start`, `work_end`, etc.
- **AI Brain** – conversational interface; tools like `get_global_backlog` will be added.
- **Verification & reassignment** – updates remaining hours and reschedules.

Phase 10 adds:
- **Global dependency graph** – builds a single graph of all tasks across all active projects.
- **Critical path method (CPM)** – identifies the longest chain of dependent tasks, which determines the minimum project completion time.
- **Resource leveling** – ensures that total planned hours per day never exceed the user’s available hours (you are the only resource).
- **Global priority queue** – mixes tasks from all projects based on urgency (deadline, remaining hours, dependency depth) rather than per‑project quotas.
- **Performance testing** – with 50 simulated projects, sync and planning must finish within 5 minutes.
- **CLI command** – `trail brain "show my global backlog"` returns the next 10 tasks regardless of project.

---

## Phase 10: Cross‑Project Orchestration & Scaling (2 weeks)

### Week 1 – Global Dependency Resolution

#### Tasks

1. **Extend the scheduler to consider all projects simultaneously**:
   - Currently, `scheduler.py` processes projects one by one, allocating hours per project independently. This does not allow cross‑project dependencies to influence the order of tasks across projects.
   - Create a new module `trail/planner/global_scheduler.py` with function `build_global_task_graph(project_ids: list) -> nx.DiGraph` (using `networkx` – add to requirements).
   - Nodes: each task (from `notion_tasks`) that is not yet completed.
   - Edges: from a task to its dependents (`task_dependencies`). For cross‑project dependencies, the graph already includes tasks from different projects.
   - Also include “milestone” nodes for project deadlines? Not necessary for MVP.

2. **Implement topological sort and critical path method (CPM)**:
   - Use `networkx.topological_sort` to get a feasible order of tasks.
   - Compute earliest start time (EST) and latest start time (LST) for each task, assuming each task has an estimated duration (from `estimated_minutes` or adjusted by learned multiplier).
   - Identify the critical path: the longest path from any start task to any end task (or project deadline). Tasks on the critical path have zero slack; they determine the overall timeline.
   - Output the critical path as a list of tasks (for debugging/insights).

3. **Modify the daily plan generation to respect global order**:
   - Instead of allocating hours per project first, the scheduler now iterates over tasks in topological order, assigning them to the earliest available time slots in the user’s calendar (respecting working hours, meetings, breaks, max parallel projects – but note: “max parallel projects” becomes less relevant because tasks are interleaved globally; you can still limit the number of different projects active in a day to avoid context switching. Keep `max_parallel_projects` as a soft constraint.)
   - For each task, find the earliest time slot where:
     - The user is not already scheduled for another task (no overlapping).
     - The project’s “parallel limit” (if enforced) is not exceeded for that day.
   - Insert the task into the daily plan(s). If a task is longer than a day, split it into daily chunks (as already done in Phase 6).

4. **Add CLI command to show critical path**:
   - `trail plan critical-path` – prints the critical path tasks with their estimated dates.
   - Also integrate with AI Brain: `trail brain "what is the critical path?"` calls the same function.

**Week 1 Success Criteria**:
- Given two projects: Project A has Task A1 (3 days), Task A2 depends on A1. Project B has Task B1 (2 days) that depends on A2. The global scheduler schedules A1, then A2, then B1 in order, respecting estimated durations.
- `trail plan critical-path` correctly identifies the longest chain.
- The scheduler never schedules a task before its dependencies are completed (based on estimated completion dates).

---

### Week 2 – Resource Leveling & Global Queue

#### Tasks

1. **Resource leveling (ensure total planned hours per day ≤ available hours)**:
   - In the global scheduling algorithm, after assigning tasks to days, compute total planned hours per day across all projects.
   - If a day exceeds the user’s available work hours (from `user_preferences.work_end - work_start` minus breaks), shift tasks to the next available day (or earlier if there is slack).
   - Use a simple leveling algorithm: for each day that is overloaded, move the lowest‑priority (or highest slack) task to the next day, then re‑check.
   - Log adjustments and include them in the morning briefing: “Today’s plan was adjusted because of resource overload; moved Task X to tomorrow.”

2. **Global priority queue**:
   - Create a function `get_global_backlog(limit=10)` that returns the next `limit` tasks to work on, ordered by:
     - Critical path tasks first (slack = 0).
     - Then tasks with earliest deadline (from `notion_tasks.due_date` or project deadline).
     - Then tasks with highest priority (Critical > High > Medium > Low).
     - Then tasks with largest remaining estimate (to surface large items early).
   - This queue is not a strict schedule but a recommendation for the user when they ask “what should I work on next?”.

3. **Add CLI command**:
   - `trail brain "show my global backlog"` – calls `get_global_backlog()` and prints the list in a human‑friendly format (Markdown or table).
   - Example output:
     ```
     Global Backlog (next 10 tasks):
     1. [Critical] Project A: Implement JWT refresh (2h, due 2026-05-01) – on critical path
     2. [High] Project B: Write API tests (1.5h, due 2026-05-03)
     3. [Medium] Project C: Update docs (1h, due 2026-05-10)
     ...
     ```

4. **Performance testing with 50 projects**:
   - Create a script `tests/performance/test_50_projects.py` that:
     - Creates 50 fake projects, each with 10–20 tasks, random dependencies (including cross‑project), random estimates.
     - Simulates GitHub and Notion data (or uses in‑memory objects).
     - Measures time for:
       - Full sync (fetching commits/tasks – mock these to avoid real API calls).
       - Building the global dependency graph.
       - Running the global scheduler (generating daily plans for 30 days).
     - Asserts that each operation finishes within 5 minutes (300 seconds) on a typical development machine (8 cores, 16GB RAM).
   - Optimize database queries: ensure proper indexes, batch inserts, and avoid N+1 queries.
   - If performance is not met, add caching (e.g., pre‑compute topological order and reuse until task states change).

5. **Integrate with AI Brain**:
   - Add a new tool `get_global_backlog_tool` to the tool registry (Phase 9.2). This allows users to ask `trail brain "what should I work on next?"` and get the global backlog.

**Week 2 Success Criteria**:
- Daily plan never exceeds available hours (after leveling).
- `trail brain "show my global backlog"` returns a meaningful list ordered by the defined criteria.
- Performance test with 50 projects completes within 5 minutes for each major operation (graph building, scheduling). If it fails, you must optimize.

---

## Final Integration & Testing (1 week after Phase 10)

Although not part of the code implementation prompt, you should provide a **testing plan** as part of your deliverables. The user expects the system to be run on real projects for 2 weeks. You must document how to do that.

Include in your response a section **Final Integration Steps** that describes:
- How to migrate existing data (if any) to the new global scheduler.
- How to run the system for 2 weeks with 3 projects, then 10, then 50 (simulated).
- A checklist of all success criteria from all phases to verify before deployment.
- Optional: Docker Compose configuration for easy startup.

---

## Additional Quality Requirements

- **Idempotency**: Running the global scheduler multiple times with the same data should produce identical plans (unless random tie‑breaking is used – avoid randomness).
- **Graceful degradation**: If the dependency graph has a cycle (e.g., A → B → A), detect it and break the cycle by ignoring the edge that would close the loop. Log a warning.
- **Scalability**: The scheduler should use efficient data structures (e.g., heap for priority queue, adjacency list for graph). Avoid O(N²) algorithms where N = number of tasks.
- **Logging**: Log critical path length, number of tasks, and scheduling time for performance monitoring.

---

## Deliverables

You will produce the following files/extensions:

1. **`trail/planner/global_scheduler.py`** – global dependency graph, topological sort, critical path, resource leveling.
2. **`trail/planner/global_backlog.py`** – global priority queue.
3. **Updates to `trail/planner/scheduler.py`** – delegate to global scheduler (or replace entirely).
4. **Updates to `trail/cli.py`** – add `plan critical-path` command; ensure `plan today` uses global scheduler.
5. **Updates to `trail/brain/tools.py`** – add `get_global_backlog` tool.
6. **Performance test script** `tests/performance/test_50_projects.py`.
7. **Updated `requirements.txt`** – add `networkx`.
8. **Final integration documentation** (`FINAL_INTEGRATION.md`) – includes migration steps, testing plan, Docker Compose example.
9. **Test instructions** (`test_phase10.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- Final integration steps and Docker Compose example (as markdown).
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 10.

---

## Cardinal Sins (What Not to Do)

- **No ignoring cross‑project dependencies** – must be handled globally.
- **No resource overload** – daily plan must not exceed available hours.
- **No slow performance** – 50 projects must finish within 5 minutes; if not, you must optimize.
- **No missing critical path** – the critical path is essential for understanding project delays.
- **No incomplete global backlog** – the backlog must consider all projects, not just one.

Now, implement Phase 10 with excellence. **Trail is counting on you.** This is the final stretch. After this, you will have a complete, production‑ready system.