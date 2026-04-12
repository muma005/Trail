-- Trail Phase 2.5: Dependencies, Sub-tasks, Size Tags
-- Adds task_dependencies, sub_tasks tables, and size_tag to notion_tasks

-- Task dependencies (including cross-project)
CREATE TABLE IF NOT EXISTS task_dependencies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES notion_tasks(id) ON DELETE CASCADE,
    depends_on_task_id UUID REFERENCES notion_tasks(id),
    depends_on_project_id UUID REFERENCES projects(id),
    dependency_type VARCHAR(50) DEFAULT 'blocks',
    created_at TIMESTAMP DEFAULT NOW(),
    CHECK (depends_on_task_id IS NOT NULL OR depends_on_project_id IS NOT NULL)
);

-- Sub-tasks parsed from Notion checklists/child pages
CREATE TABLE IF NOT EXISTS sub_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_task_id UUID NOT NULL REFERENCES notion_tasks(id) ON DELETE CASCADE,
    title TEXT,
    is_completed BOOLEAN DEFAULT FALSE,
    estimated_minutes INT,
    order_index INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Ensure size_tag column exists on notion_tasks (may already be in Phase 2 migration)
ALTER TABLE notion_tasks ADD COLUMN IF NOT EXISTS size_tag VARCHAR(10);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_task_dependencies_task_id ON task_dependencies(task_id);
CREATE INDEX IF NOT EXISTS idx_task_dependencies_depends_on_id ON task_dependencies(depends_on_task_id);
CREATE INDEX IF NOT EXISTS idx_sub_tasks_parent_id ON sub_tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_notion_tasks_size_tag ON notion_tasks(size_tag);
