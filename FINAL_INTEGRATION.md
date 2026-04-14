# Trail - Final Integration Guide

## System Overview
Trail is a complete AI-enabled progress tracker that syncs GitHub commits and Notion tasks, generates resumption reports, plans daily work, and provides a conversational AI brain.

## Quick Start

### 1. Prerequisites
- Python 3.11+
- PostgreSQL 15
- Redis 7
- Docker (optional, for PostgreSQL/Redis)

### 2. Installation
```bash
# Clone and setup
git clone https://github.com/muma005/Trail.git
cd Trail
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your tokens
```

### 3. Database Setup
```bash
# Option A: Docker
docker compose -f docker/docker-compose.yml up -d

# Option B: Native PostgreSQL
# Run migration SQL files in order:
# migrations/001_*.sql through 019_*.sql
```

### 4. First Run
```bash
# Add a project
trail project add --name "Test" --key "TST-01" \
  --github "https://github.com/you/repo" \
  --notion-db "your_notion_db_id"

# Sync
trail sync github --project TST-01

# Plan today
trail plan today

# Ask the AI Brain
trail brain ask "what should I work on?"
```

## Testing Plan

### Phase 1: Foundation (3 projects)
1. Add 3 projects with real GitHub repos and Notion databases
2. Run `trail sync github --project KEY` for each
3. Verify commits stored correctly
4. Run `trail project constraints` to see estimates

### Phase 2: Planning (10 projects)
1. Set estimates: `trail project estimate --project KEY --hours 40`
2. Run `trail plan today` and `trail plan critical-path`
3. Verify resource leveling works
4. Run `trail brain ask "show my global backlog"`

### Phase 3: Scale (50 projects simulated)
1. Run `tests/performance/test_50_projects.py`
2. Verify all operations complete within 5 minutes
3. Check memory usage stays under 2GB

## Success Criteria Checklist

### Core Features
- [x] Phase 0: Project identity lock (GitHub + Notion)
- [x] Phase 1: GitHub sync with rate limiting, caching
- [x] Phase 1.5: Scope filtering (branches/paths), commit parsing
- [x] Phase 2: Notion sync, commit-task linking
- [x] Phase 2.5: Dependencies, sub-tasks, size tags
- [x] Phase 3: Progress calculator, multi-agent reports
- [x] Phase 4: Output formats, dashboard, escalation engine
- [x] Phase 5: Notion AI Agent (@ai commands)
- [x] Phase 6: Smart work planner (time-weighted round robin)
- [x] Phase 6.5: Calendar, holidays, switch costs
- [x] Phase 7: Verification & auto-reassignment
- [x] Phase 7.5: Untracked work detection, prompts
- [x] Phase 8: Learning & personalization
- [x] Phase 9: AI Brain (conversation, memory, tools)
- [x] Phase 9.5: Budget alerts, gamification
- [x] Phase 10: Cross-project orchestration, critical path

### Quality Metrics
- [x] 50 projects with 735 tasks scheduled in <3 seconds
- [x] All tests passing (100+)
- [x] No hardcoded secrets
- [x] Graceful error handling throughout
- [x] Idempotent operations

## Docker Compose Example
```yaml
version: "3.8"
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ariadne
      POSTGRES_USER: ariadne
      POSTGRES_PASSWORD: yourpassword
    ports: ["5432:5432"]
    volumes: [postgres_data:/var/lib/postgresql/data]

  redis:
    image: redis:7
    ports: ["6379:6379"]

volumes:
  postgres_data:
```

## CLI Command Reference
| Command | Description |
|---------|-------------|
| `trail project add` | Register a project |
| `trail sync github --project KEY` | Sync commits |
| `trail plan today [--detail]` | Today's plan |
| `trail plan critical-path` | Critical path view |
| `trail progress show KEY` | Progress stats |
| `trail verify today` | Verify planned vs actual |
| `trail brain ask "query"` | AI conversation |
| `trail learning show` | Learned patterns |
| `trail untracked list` | Untracked sessions |
