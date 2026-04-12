# Prompt for Qwen to Implement Phase 0 of Trail

You are an expert software engineer. Your task is to implement **Phase 0 (Foundation & Identity Lock)** of the Ariadne project – an AI‑enabled progress tracker that links GitHub repos and Notion databases.

**This is not a generic or lazy implementation. Every detail must be accurate, production‑ready, and thoroughly tested.** You will produce working code, configuration files, and a clear verification report.

---

## Project Context

Ariadne is a CLI tool that helps developers track multiple projects across GitHub and Notion. Phase 0 establishes the core identity rule: **one project = one GitHub repo + one Notion database**. No exceptions.

The technology stack for Phase 0:
- Python 3.11+
- PostgreSQL 15 (via Docker or native)
- Redis 7 (via Docker or native)
- Libraries: `psycopg2`, `redis`, `python-dotenv`, `click`
- Git for version control

---

## Your Deliverables

You must produce a complete, runnable implementation of Phase 0 that meets all success criteria. This includes:

1. A Python project skeleton with virtual environment instructions.
2. A `requirements.txt` file.
3. A `.env.example` file with placeholders for secrets.
4. A `docker-compose.yml` file to run PostgreSQL and Redis (optional but recommended).
5. SQL schema creation script (`.sql` or Python migration).
6. A CLI module using `click` with commands: `project add` and `project list`.
7. Implementation of project addition logic with GitHub and Notion API validation.
8. A short test script or manual test steps to verify success criteria.
9. A `README.md` for Phase 0 that explains how to set up and run.

All code must be clean, commented, and error‑handled. No lazy shortcuts (e.g., no hardcoded credentials, no ignoring edge cases).

---

## Detailed Task Breakdown

### 1. Development Environment Setup

- Write instructions to create a Python virtual environment (`.venv`).
- Provide `requirements.txt` with exact versions: `psycopg2-binary==2.9.9`, `redis==5.0.1`, `python-dotenv==1.0.0`, `click==8.1.7`, `PyGithub==2.1.1` (for GitHub validation), `notion-client==2.2.1` (for Notion validation).
- Initialize a Git repository with a `.gitignore` for Python, `.env`, and `__pycache__`.

### 2. Database & Cache Configuration

- Write a `docker-compose.yml` that starts:
  - PostgreSQL 15 with database `ariadne`, user `ariadne`, password from `.env`.
  - Redis 7 with default port.
- Provide SQL script `schema.sql` that creates:
  - `projects` table:
    - `id` UUID primary key
    - `project_key` VARCHAR(50) UNIQUE NOT NULL
    - `name` VARCHAR(255) NOT NULL
    - `github_repo_url` TEXT NOT NULL UNIQUE
    - `notion_database_id` VARCHAR(100) NOT NULL UNIQUE
    - `created_at` TIMESTAMP DEFAULT NOW()
  - `user_preferences` table:
    - `user_id` UUID primary key (for future multi‑user, but now single user with fixed ID)
    - `work_start` TIME, `work_end` TIME, `timezone` VARCHAR(50)
    - `created_at`, `updated_at`
  - `sync_logs` table:
    - `id` UUID, `project_id` UUID (foreign key to projects), `sync_type` VARCHAR(20), `status` VARCHAR(20), `message` TEXT, `created_at`
- Include indexes on foreign keys and unique constraints.

### 3. CLI Skeleton with `click`

- Create `ariadne/cli.py` with a main group.
- Implement `ariadne project add` that takes:
  - `--name` (required)
  - `--key` (required, unique project identifier)
  - `--github` (required, full GitHub repo URL)
  - `--notion-db` (required, Notion database ID)
  - `--work-start` (optional, default 09:00)
  - `--work-end` (optional, default 17:00)
  - `--timezone` (optional, default UTC)
- Implement `ariadne project list` that prints all projects in a table.

### 4. Project Addition Logic

- **Load environment variables** from `.env`:
  - `GITHUB_TOKEN` (classic or fine‑grained PAT)
  - `NOTION_TOKEN` (integration token)
  - `DATABASE_URL` (PostgreSQL connection string)
  - `REDIS_URL`
- **Validate GitHub repo**:
  - Use `PyGithub` to authenticate.
  - Call `repo = github.get_repo(full_name)` – extract `full_name` from URL.
  - If repo does not exist, raise a user‑friendly error.
- **Validate Notion database**:
  - Use `notion_client` to query the database by ID.
  - If database not found or token lacks access, raise an error.
- **Insert into PostgreSQL**:
  - Use `psycopg2` (or SQLAlchemy if you prefer, but keep it simple).
  - Catch `UniqueViolation` errors and re‑raise as “Project with this GitHub repo or Notion DB already exists.”
- **Store user preferences**:
  - After first project addition, insert a default record into `user_preferences` (or update if exists).
- **Log the sync** (even though no sync yet, log the project creation event).

### 5. Error Handling & Edge Cases

- Invalid GitHub URL format → show correct format.
- Network errors (GitHub/Notion API down) → retry with exponential backoff? For Phase 0, just fail with clear message.
- Duplicate project → show which constraint was violated.
- Missing environment variables → exit with helpful message.

### 6. Testing & Success Criteria Verification

After writing the code, you must **simulate running the commands** and confirm:

1. `ariadne project add --name "Auth Service" --key "AUTH-01" --github "https://github.com/octocat/Hello-World" --notion-db "abc123..."` works and creates a record.
2. Running the same command again fails (unique constraint on `github_repo_url`).
3. Changing the Notion DB to a different one but same GitHub repo fails (unique on `github_repo_url`).
4. `ariadne project list` shows the added project.

You do not need to implement full sync yet – that’s Phase 1. Only validation and storage.

---

## Output Format

Provide your answer as a **single, self‑contained response** that includes:

- A clear **file tree** of the generated project.
- The content of each file (code, config, SQL) in separate code blocks.
- A **verification section** that explains how to run the tests and what the expected output is.
- A **final note** that confirms all success criteria are met.

Do not skip any file. Do not write “left as an exercise”. This is a complete implementation.

---

## Quality Standards (Cardinal Sins to Avoid)

- **No hardcoded credentials** – always use `.env`.
- **No silent failures** – every exception must be caught and reported meaningfully.
- **No unvalidated input** – check that GitHub URL is a valid repo path, Notion DB ID is a valid UUID format.
- **No lazy comments** – explain *why* not just *what*.
- **No missing error handling** – network timeouts, API errors, database disconnects must be handled.
- **No incomplete testing** – you must actually verify the success criteria (simulate mentally or write a small test script).

You are building the foundation of a system that will scale to dozens of projects. Be meticulous.

---

## Deliverable Example (Stub)

Your final answer should look like this structure:

```
#
## File Contents
(Each file in a separate code block)

## Verification Instructions
(Step‑by‑step commands to run and expected outputs)

## Success Criteria Checklist
- [ ] `ariadne project add` creates record...
- [ ] Duplicate GitHub repo fails...
- [ ] Duplicate Notion DB fails...
- [ ] `ariadne project list` shows the project.
```

Now, implement Phase 0 with excellence. No laziness.