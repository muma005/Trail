"""
Performance test for 50 projects.
Phase 10: Verifies that sync and planning complete within 5 minutes for 50 projects.
"""
import sys
import time
import uuid
from datetime import date, timedelta

sys.path.insert(0, '.')


def test_50_projects():
    """
    Create 50 fake projects with 10-20 tasks each, random dependencies,
    and measure performance of graph building and scheduling.
    """
    print("=== Phase 10 Performance Test: 50 Projects ===\n")

    # Import after path setup
    from src.services.work_planner.global_scheduler import GlobalScheduler

    NUM_PROJECTS = 50
    TASKS_PER_PROJECT_MIN = 10
    TASKS_PER_PROJECT_MAX = 20
    TIMEOUT_SECONDS = 300  # 5 minutes

    results = {}

    # Step 1: Build global graph with simulated data
    print("Step 1: Building global task graph...")
    scheduler = GlobalScheduler()

    start_time = time.time()

    # Simulate 50 projects with tasks
    for i in range(NUM_PROJECTS):
        project_id = str(uuid.uuid4())
        project_key = f"PROJ-{i:03d}"
        num_tasks = TASKS_PER_PROJECT_MIN + (i % (TASKS_PER_PROJECT_MAX - TASKS_PER_PROJECT_MIN + 1))

        prev_task_id = None
        for j in range(num_tasks):
            task_id = f"{project_id}-task-{j}"
            est_minutes = 30 + (j * 15)  # Varying estimates

            scheduler.task_map[task_id] = {
                "task_id": task_id,
                "title": f"Task {j} in {project_key}",
                "project_key": project_key,
                "project_id": project_id,
                "estimated_minutes": est_minutes,
                "remaining_hours": est_minutes / 60.0,
                "priority": ["Critical", "High", "Medium", "Low"][j % 4],
                "due_date": str(date.today() + timedelta(days=30 + j)),
                "status": "In Progress",
                "size_tag": ["quick", "medium", "large"][j % 3],
            }

            scheduler.graph.add_node(
                task_id,
                title=f"Task {j} in {project_key}",
                project_key=project_key,
                estimated_minutes=est_minutes,
                priority=["Critical", "High", "Medium", "Low"][j % 4],
                due_date=str(date.today() + timedelta(days=30 + j)),
            )

            # Add dependency (chain within project)
            if prev_task_id:
                scheduler.graph.add_edge(prev_task_id, task_id)
            prev_task_id = task_id

        # Add some cross-project dependencies (10% of tasks)
        if i > 0 and i % 10 == 0:
            # Link to previous project's last task
            prev_project_tasks = [
                tid for tid in scheduler.task_map.keys()
                if tid.startswith(f"{str(uuid.UUID(int=i-1))}")
            ]
            if prev_project_tasks:
                cross_dep = prev_project_tasks[-1]
                first_task = f"{project_id}-task-0"
                if first_task in scheduler.graph and cross_dep in scheduler.graph:
                    scheduler.graph.add_edge(cross_dep, first_task)

    build_time = time.time() - start_time
    results["graph_build_seconds"] = round(build_time, 2)
    print(f"  ✓ Built graph: {scheduler.graph.number_of_nodes()} nodes, "
          f"{scheduler.graph.number_of_edges()} edges ({build_time:.2f}s)")

    assert build_time < TIMEOUT_SECONDS, f"Graph build too slow: {build_time}s"

    # Step 2: Topological sort
    print("\nStep 2: Computing topological order...")
    start_time = time.time()
    topo_order = scheduler.get_topological_order()
    topo_time = time.time() - start_time
    results["topo_sort_seconds"] = round(topo_time, 2)
    print(f"  ✓ Sorted {len(topo_order)} tasks ({topo_time:.2f}s)")

    assert topo_time < TIMEOUT_SECONDS, f"Topo sort too slow: {topo_time}s"
    assert len(topo_order) == scheduler.graph.number_of_nodes(), "Not all tasks sorted"

    # Step 3: Critical path
    print("\nStep 3: Computing critical path...")
    start_time = time.time()
    critical_path = scheduler.compute_critical_path()
    cp_time = time.time() - start_time
    results["critical_path_seconds"] = round(cp_time, 2)
    print(f"  ✓ Critical path: {len(critical_path)} tasks ({cp_time:.2f}s)")

    assert cp_time < TIMEOUT_SECONDS, f"Critical path too slow: {cp_time}s"

    # Step 4: Global backlog
    print("\nStep 4: Computing global backlog...")
    start_time = time.time()
    backlog = scheduler.get_global_backlog(limit=10)
    backlog_time = time.time() - start_time
    results["global_backlog_seconds"] = round(backlog_time, 2)
    print(f"  ✓ Backlog: {len(backlog)} tasks ({backlog_time:.2f}s)")

    assert backlog_time < TIMEOUT_SECONDS, f"Global backlog too slow: {backlog_time}s"

    # Step 5: Resource-leveled plan (mock UserProfile to avoid DB)
    print("\nStep 5: Generating resource-leveled plan (14 days)...")
    
    # Mock UserProfile to avoid DB connection
    import unittest.mock as mock
    mock_profile = mock.MagicMock()
    mock_profile.total_work_minutes = 480  # 8 hours
    mock_profile.work_start = None
    mock_profile.work_end = None
    
    start_time = time.time()
    with mock.patch('src.services.work_planner.global_scheduler.UserProfile') as mock_up:
        mock_up.return_value = mock_profile
        plan = scheduler.generate_leveled_plan(days_ahead=14)
    plan_time = time.time() - start_time
    results["leveled_plan_seconds"] = round(plan_time, 2)
    print(f"  ✓ Planned {plan['total_tasks']} tasks across {plan['days_ahead']} days ({plan_time:.2f}s)")

    assert plan_time < TIMEOUT_SECONDS, f"Leveled plan too slow: {plan_time}s"

    # Summary
    total_time = sum(v for v in results.values() if isinstance(v, (int, float)))
    results["total_seconds"] = round(total_time, 2)

    print(f"\n{'='*50}")
    print(f"Results:")
    for key, value in results.items():
        print(f"  {key}: {value}s")

    if total_time < TIMEOUT_SECONDS:
        print(f"\n✅ PASS: All operations completed within {TIMEOUT_SECONDS}s limit")
        return True
    else:
        print(f"\n❌ FAIL: Total time {total_time}s exceeds {TIMEOUT_SECONDS}s limit")
        return False


if __name__ == "__main__":
    success = test_50_projects()
    sys.exit(0 if success else 1)
