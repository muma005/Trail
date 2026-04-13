# Prompt for Qwen to Implement Phase 9 of Trail (AI Brain – Conversation & Memory)

You are an expert software engineer. Your task is to implement **Phase 9: AI Brain – Conversation & Memory** for the **Trail** project. This phase builds on all previous phases (0–8) and creates a unified conversational AI that can answer questions, execute actions via tools, remember past interactions, and proactively send briefings and celebrations.

**No generic or lazy work.** This is the central brain of Trail. Every component must be robust, secure, and deeply integrated with existing systems (planner, verification, Notion, GitHub, etc.). You will produce code, database migrations, CLI extensions, and verification steps.

---

## Context (What Already Exists)

From previous phases:
- **Planner** – `trail plan today`, `trail plan week`, task breakdown, scheduling with dependencies and switch costs.
- **Verification & reassignment** – `planned_task_verification`, auto‑reassignment, untracked work detection.
- **Notion AI Agent** – basic `@ai` command handling (Phase 5).
- **Progress tracker** – reports, snapshots, progress calculation.
- **Learning** – `learned_patterns` for duration multipliers, focus peaks, empty promise detection.
- **CLI** – many commands (`trail sync`, `trail report`, `trail progress`, `trail plan`, `trail verify`, etc.).
- **OpenRouter integration** – tiered LLM access with caching and cost tracking.
- **Redis** – for caching and message queues.

Phase 9 adds:
- **Conversation manager** – stores chat history with vector embeddings for semantic memory.
- **Tool registry** – wraps all existing CLI/internal functions as callable tools.
- **ReAct loop** – LLM decides which tool to call, executes it, observes result, and iterates.
- **Deterministic ID guard** – ensures every tool call includes a project ID; if ambiguous, the LLM asks the user.
- **Proactive intelligence** – morning briefing scheduler, celebration messages.

---

## Phase 9: AI Brain – Conversation & Memory (3 weeks)

### Week 1 – Conversation Manager

#### Tasks

1. **Create `conversations` table** (migration `018_create_conversations.sql`):
   - Columns:
     - `id` UUID PRIMARY KEY
     - `user_id` UUID (fixed for now, for future multi‑user)
     - `session_id` UUID (to group messages from a single conversation session)
     - `role` VARCHAR(20) – 'user' or 'assistant'
     - `content` TEXT
     - `tool_calls` JSONB (optional, stores tool name and arguments)
     - `tool_call_id` VARCHAR(100) (to match tool responses)
     - `timestamp` TIMESTAMP DEFAULT NOW()
     - `embedding` VECTOR(1536) (for semantic search; requires PgVector enabled)
   - Index on `(user_id, session_id, timestamp)`.
   - Index on `embedding` using `ivfflat` (or `hnsw`).

2. **Implement conversation manager** (`trail/brain/conversation.py`):
   - `start_session(user_id) -> session_id` – creates a new session.
   - `add_message(session_id, role, content, tool_calls=None)` – inserts a message.
   - `get_conversation_history(session_id, limit=10)` – returns last N messages.
   - `get_similar_messages(session_id, query, limit=3)` – uses vector similarity to retrieve past relevant messages (semantic memory). Generate embedding for `query` using sentence‑transformers, then perform cosine similarity search on the `conversations` table.

3. **Create CLI entry point** `trail brain "query"`:
   - File: `trail/cli_brain.py` (integrate into `cli.py` as a new command group).
   - Maintain a session per user (store session_id in a local file or Redis). For simplicity, use a file `.trail_session` in the user’s home directory.
   - On each query, call the AI Brain (orchestrator) with the current session.
   - Print the assistant’s response.

**Week 1 Success Criteria**:
- `trail brain "hello"` creates a session and stores the user message and assistant response in `conversations`.
- A second query `trail brain "what did I just say?"` retrieves the previous message (using conversation history) and answers correctly.
- Vector similarity works: after several messages, a query semantically related to an old message retrieves that message.

---

### Week 2 – Tool Registry & ReAct Loop

#### Tasks

1. **Tool registry** (`trail/brain/tools.py`):
   - Define a `Tool` class: `name`, `description`, `parameters` (JSON schema), `function` (callable).
   - Wrap existing functions as tools. You need at least 40 tools. Examples:
     - `get_project_report(project_key) -> str`
     - `get_today_plan() -> str`
     - `update_task_status(task_id, status) -> str`
     - `reschedule_task(task_id, new_date) -> str`
     - `get_project_progress(project_key) -> str`
     - `get_missed_tasks(project_key, days) -> str`
     - `add_task(project_key, title, estimate_minutes) -> str`
     - `get_untracked_sessions() -> str`
     - `assign_untracked_time(session_id, project_key) -> str`
     - `get_focus_peaks() -> str`
     - `get_learned_multiplier(task_type) -> str`
     - ... and many more. You don't have to implement all 40 in Week 2; provide a clear framework and implement the most critical ones (e.g., 10–15). Document that the rest can be added later.
   - The tool registry should be easily extensible.

2. **Deterministic ID guard**:
   - Before calling any tool that requires a `project_id` or `project_key`, the ReAct loop must ensure that the project is unambiguous.
   - If the user query does not specify a project, the LLM should ask: “Which project do you mean? You have projects: A, B, C.”
   - If the session already has a default project (e.g., from previous messages), use that.
   - Store `current_project` in session state.

3. **ReAct loop** (`trail/brain/react.py`):
   - Input: user query, conversation history, session state.
   - Loop:
     - Call LLM (OpenRouter) with a system prompt that lists available tools and instructs the LLM to output either a final answer or a tool call in JSON format.
     - If tool call: parse tool name and arguments; validate that required parameters (like project_key) are present; if missing, ask user.
     - Execute tool function, get result.
     - Add observation to conversation history.
     - Continue loop.
     - If final answer: return to user.
   - Limit iterations to 5 to prevent infinite loops.

4. **Integrate with existing Notion AI Agent**:
   - The Notion AI Agent (Phase 5) already listens for `@ai` commands. It should be refactored to use the same AI Brain (i.e., forward the command to the ReAct loop). This unifies the interface.

**Week 2 Success Criteria**:
- `trail brain "what is the status of Project A?"` correctly calls `get_project_report` and returns the answer.
- If you ask `trail brain "update the status to Done"` without specifying a project, the Brain asks “Which project?”
- After you answer “Project A”, it updates the task status (if the current page context is available; for CLI, you may need to specify task ID – but the Brain can ask for clarification).
- The ReAct loop handles tool call failures gracefully.

---

### Week 3 – Memory & Proactive Intelligence

#### Tasks

1. **Semantic memory retrieval**:
   - In the ReAct loop, before calling the LLM, retrieve up to 3 similar past messages from the `conversations` table using vector similarity on the user’s query.
   - Add those messages as context (with a note “From previous conversation: …”).
   - This allows the Brain to remember things like “last week you said you were waiting for an API key for Project B.”

2. **Morning briefing scheduler**:
   - Create a Celery Beat task that runs at 8 AM (configurable via `user_preferences.briefing_time`).
   - The task fetches:
     - Today’s plan (from `daily_plans`).
     - Stale projects (no commits for > `warning_days`).
     - Blockers (tasks with status ‘Blocked’ and no update for >2 days).
     - Untracked work sessions from yesterday that are still unresolved.
   - Compose a natural language briefing using a simple template (or call the LLM with a system prompt to generate a concise summary).
   - Send the briefing to the user’s preferred channel(s):
     - CLI (if the user is logged in, but typically they are not). Better: send to Notion (create a new page or callout block in the user’s “Trail Inbox” page).
     - Slack (if webhook configured).
     - Email (optional, if SMTP configured).
   - For MVP, implement **Notion** delivery (reuse Notion AI Agent’s response writer).

3. **Celebration messages**:
   - Detect when a project reaches 100% completion (all tasks done, remaining hours = 0).
   - Also detect when a milestone is achieved (e.g., a large task completed, or a project finished before deadline).
   - Send a congratulatory message via Notion (or Slack): “🎉 Congratulations! You finished Project X 2 days early. Great job!”
   - Store celebration events in a `celebrations` table (optional, for analytics).

4. **Add CLI command**:
   - `trail brain --session` – show current session info.
   - `trail brain --reset` – clear session state.

**Week 3 Success Criteria**:
- After a conversation about Project A, you ask “and what about Project B?” The Brain retrieves the previous context (that you were comparing projects) and answers correctly without asking for project again.
- At 8 AM, you receive a Notion callout with the morning briefing (today’s plan, stale projects, blockers).
- When a project reaches 100% completion, you receive a celebration message.

---

## Additional Quality Requirements

- **Idempotency**: Running the same query twice should produce similar results (caching may help, but conversational memory should not repeat the same tool calls unnecessarily).
- **Error handling**: If a tool call fails (e.g., GitHub API down), the Brain should explain the error and suggest alternatives.
- **Performance**: The ReAct loop should complete within 10 seconds for typical queries.
- **Security**: The tool registry must never expose dangerous operations (e.g., deleting projects) without explicit confirmation. Implement a confirmation step for destructive actions.
- **Configuration**: LLM model, max iterations, session timeout, briefing time, and delivery channels should be configurable via `.env` and `user_preferences`.

---

##
10. **Test instructions** (`test_phase9.md`).

---

## Output Format

Provide a **single, self‑contained response** with:
- File tree of new/modified files.
- Content of each file in code blocks.
- SQL migration script.
- Verification steps for each success criterion.
- A final checklist.

Do not skip any file. Do not write placeholders. Deliver a complete, runnable Phase 9.

---

## Cardinal Sins (What Not to Do)

- **No hardcoded tool names** – use a registry that can be extended without code changes.
- **No missing project guard** – every project‑related tool call must verify project existence and unambiguity.
- **No infinite ReAct loop** – enforce a maximum iteration limit.
- **No ignoring vector search** – semantic memory is a core feature; ensure embeddings are generated and stored correctly.
- **No silent failures in proactive tasks** – if morning briefing fails, log and retry.

Now, implement Phase 9 with excellence. **Trail is counting on you.**