-- Trail Phase 2: Notion Sync & Linking
-- Creates notion_tasks table and commit_task_links table

-- Notion tasks: stores pages from a project's Notion database
CREATE TABLE IF NOT EXISTS notion_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    notion_page_id VARCHAR(100) UNIQUE NOT NULL,
    title TEXT,
    status VARCHAR(50),
    priority VARCHAR(20),
    mooscow VARCHAR(20),
    due_date DATE,
    completed_at TIMESTAMP,
    progress_percentage INT,
    estimated_minutes INT,
    actual_minutes INT,
    tags TEXT[],
    parent_task_id UUID REFERENCES notion_tasks(id),
    size_tag VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Links between commits and tasks (exact matches and suggestions)
CREATE TABLE IF NOT EXISTS commit_task_links (
    commit_id UUID NOT NULL REFERENCES commits(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES notion_tasks(id) ON DELETE CASCADE,
    confidence DECIMAL(3,2),
    is_suggestion BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (commit_id, task_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_notion_tasks_project_id ON notion_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_notion_tasks_parent_id ON notion_tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_notion_tasks_status ON notion_tasks(status);
CREATE INDEX IF NOT EXISTS idx_commit_task_links_task_id ON commit_task_links(task_id);
CREATE INDEX IF NOT EXISTS idx_commit_task_links_commit_id ON commit_task_links(commit_id);
