"""
Streamlit Web Dashboard for Trail.
Phase 4: Visualises projects, progress, snapshots, and reports.
Run with: streamlit run src/dashboard.py
"""
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st

# Ensure project root is in path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import settings
from src.core.enrichment.progress_calculator import (
    calculate_simple_progress,
    get_commit_stats,
)
from src.models.database.base import SessionLocal
from src.models.database.models import Project, ProjectSnapshot, NotionTask, Commit

st.set_page_config(page_title="Trail Dashboard", page_icon="🔥", layout="wide")

st.title("🔥 Trail Dashboard")
st.caption("AI-Enabled Progress Tracker")


@st.cache_data(ttl=60)
def load_projects():
    """Load all active projects."""
    db = SessionLocal()
    try:
        return db.query(Project).filter(Project.status == "active").all()
    finally:
        db.close()


@st.cache_data(ttl=60)
def load_snapshots(project_id: str):
    """Load snapshots for a project."""
    db = SessionLocal()
    try:
        return (
            db.query(ProjectSnapshot)
            .filter(ProjectSnapshot.project_id == project_id)
            .order_by(ProjectSnapshot.snapshot_date)
            .all()
        )
    finally:
        db.close()


@st.cache_data(ttl=60)
def load_tasks(project_id: str):
    """Load tasks for a project."""
    db = SessionLocal()
    try:
        return db.query(NotionTask).filter(NotionTask.project_id == project_id).all()
    finally:
        db.close()


@st.cache_data(ttl=60)
def load_commits(project_id: str):
    """Load commits for a project."""
    db = SessionLocal()
    try:
        return (
            db.query(Commit)
            .filter(Commit.project_id == project_id)
            .order_by(Commit.commit_date.desc())
            .limit(20)
            .all()
        )
    finally:
        db.close()


# Sidebar
st.sidebar.title("Navigation")
projects = load_projects()
project_options = [f"{p.project_key}: {p.name}" for p in projects]
selected = st.sidebar.selectbox("Select Project", ["— Overview —"] + project_options)

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

# Main content
if selected == "— Overview —":
    # Overview table
    if not projects:
        st.info("No active projects. Use `trail project add` to register one.")
    else:
        st.header("Active Projects")
        overview_data = []
        for p in projects:
            progress = calculate_simple_progress(p.id)
            days_idle = 0
            if p.last_commit_date:
                days_idle = (datetime.utcnow() - p.last_commit_date).days
            overview_data.append({
                "Key": p.project_key,
                "Name": p.name,
                "Completion %": progress["completion_percentage"],
                "Tasks": progress["total_tasks"],
                "Completed": progress["completed_tasks"],
                "Days Idle": days_idle,
                "Last Sync": str(p.last_synced_at or "Never"),
            })

        st.dataframe(overview_data, use_container_width=True)

else:
    # Project detail view
    project_key = selected.split(":")[0].strip()
    project = next((p for p in projects if p.project_key == project_key), None)

    if not project:
        st.error("Project not found")
        st.stop()

    st.header(f"{project.name} ({project.project_key})")

    col1, col2, col3 = st.columns(3)
    progress = calculate_simple_progress(project.id)
    commits = load_commits(project.id)
    tasks = load_tasks(project.id)

    col1.metric("Completion", f"{progress['completion_percentage']:.1f}%")
    col2.metric("Tasks", f"{progress['completed_tasks']}/{progress['total_tasks']}")
    col3.metric("Commits", len(commits))

    # Tabs
    tab_progress, tab_commits, tab_tasks = st.tabs(["📊 Progress", "💻 Commits", "📋 Tasks"])

    with tab_progress:
        st.subheader("Progress Over Time")
        snapshots = load_snapshots(project.id)
        if snapshots:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Date": s.snapshot_date,
                    "Simple %": float(s.completion_percentage_simple or 0),
                    "Weighted %": float(s.completion_percentage_weighted or 0),
                }
                for s in snapshots
            ])
            st.line_chart(df.set_index("Date"))
        else:
            st.info("No snapshots yet. Run daily snapshots or wait for scheduled job.")

    with tab_commits:
        st.subheader(f"Recent Commits ({len(commits)})")
        if commits:
            for c in commits[:10]:
                st.markdown(
                    f"`{c.commit_sha[:8]}` **{c.message[:80]}** — "
                    f"*{c.commit_date.strftime('%Y-%m-%d %H:%M') if c.commit_date else 'N/A'}*"
                )
        else:
            st.info("No commits found. Run `trail sync github --project {project_key}`")

    with tab_tasks:
        st.subheader(f"Notion Tasks ({len(tasks)})")
        if tasks:
            task_df = []
            for t in tasks:
                task_df.append({
                    "Title": t.title or "Untitled",
                    "Status": t.status,
                    "Priority": t.priority,
                    "Size": t.size_tag,
                    "Estimate": f"{t.estimated_minutes} min" if t.estimated_minutes else "—",
                })
            st.dataframe(task_df, use_container_width=True)
        else:
            st.info("No tasks synced. Run `trail sync github --project {project_key}`")
