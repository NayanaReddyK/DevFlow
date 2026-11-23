"""
Workflow Intelligence Engine for DevFlow.
All rules are deterministic. Every result includes an `evidence` field.
Thresholds are module-level constants so tests can override them.
"""
from __future__ import annotations
from collections import deque
from datetime import date, timedelta
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from .models import ActivityLog, Task, TaskDependency


# --- Configurable thresholds (documented in README) ---
BOTTLENECK_IMPACT_THRESHOLD = 3   # FR-INT-02: flag if downstream count >= this
STALE_BLOCKER_DAYS = 5            # FR-INT-03: flag if blocked for >= this many days
DUE_SOON_DAYS = 3                 # FR-INT-05: flag if due within this many days
AT_RISK_OVERDUE_COUNT = 2         # FR-INT-07: At Risk if >= this many overdue crit/high tasks
AT_RISK_BOTTLENECK_IMPACT = 5     # FR-INT-07: At Risk if bottleneck impact >= this and overdue


def _incomplete_statuses():
    return [Task.Status.TODO, Task.Status.IN_PROGRESS, Task.Status.IN_REVIEW]


# ---------------------------------------------------------------------------
# FR-INT-01: Downstream impact
# ---------------------------------------------------------------------------
def downstream_impact(task_id: int, all_deps: list[tuple[int, int]]) -> int:
    """
    Count all tasks that transitively depend on task_id (directly or indirectly).
    all_deps: list of (prerequisite_task_id, dependent_task_id) tuples for the project.
    Uses iterative BFS — no recursion.
    """
    adjacency: dict[int, list[int]] = {}
    for pre, dep in all_deps:
        adjacency.setdefault(pre, []).append(dep)

    visited = set()
    queue = deque(adjacency.get(task_id, []))
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        queue.extend(adjacency.get(current, []))
    return len(visited)


# ---------------------------------------------------------------------------
# FR-INT-02: Bottleneck detection
# ---------------------------------------------------------------------------
def get_bottlenecks(project, threshold: int = BOTTLENECK_IMPACT_THRESHOLD) -> list[dict[str, Any]]:
    """
    Flag incomplete tasks whose downstream impact >= threshold.
    Returns list of dicts with task info and evidence.
    """
    incomplete_tasks = Task.objects.filter(
        project=project,
        status__in=_incomplete_statuses(),
    ).values_list("id", flat=True)

    all_deps = list(
        TaskDependency.objects.filter(
            prerequisite_task__project=project
        ).values_list("prerequisite_task_id", "dependent_task_id")
    )

    bottlenecks = []
    for task_id in incomplete_tasks:
        impact = downstream_impact(task_id, all_deps)
        if impact >= threshold:
            task = Task.objects.select_related("assignee").get(pk=task_id)
            bottlenecks.append({
                "task_id": task_id,
                "task_title": task.title,
                "assignee_id": task.assignee_id,
                "status": task.status,
                "priority": task.priority,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "downstream_count": impact,
                "evidence": {
                    "downstream_task_count": impact,
                    "threshold": threshold,
                },
            })
    bottlenecks.sort(key=lambda x: -x["downstream_count"])
    return bottlenecks


# ---------------------------------------------------------------------------
# FR-INT-03: Stale blockers
# ---------------------------------------------------------------------------
def get_stale_blockers(project, days: int = STALE_BLOCKER_DAYS) -> list[dict[str, Any]]:
    """
    Flag tasks that are currently blocked and have been in a blocked state for >= `days`.
    Uses ActivityLog to find when the task last received a STATUS_CHANGED log that
    transitioned it INTO a blocked-relevant status (TODO/IN_PROGRESS/IN_REVIEW).
    Falls back to task.updated_at if no log exists.
    """
    # Get all tasks that are currently blocked
    blocked_tasks = [
        t for t in Task.objects.filter(
            project=project,
            status__in=_incomplete_statuses(),
        ).prefetch_related("prerequisites__prerequisite_task")
        if t.is_blocked
    ]

    cutoff = timezone.now() - timedelta(days=days)
    stale = []

    for task in blocked_tasks:
        # Find the most recent status-change log for this task
        last_log = ActivityLog.objects.filter(
            task=task,
            action=ActivityLog.Action.STATUS_CHANGED,
        ).order_by("-created_at").first()

        last_changed = last_log.created_at if last_log else task.updated_at

        if last_changed <= cutoff:
            blocking_ids = list(
                task.prerequisites.filter(
                    prerequisite_task__status__in=_incomplete_statuses()
                ).values_list("prerequisite_task_id", flat=True)
            )
            days_blocked = (timezone.now() - last_changed).days
            stale.append({
                "task_id": task.pk,
                "task_title": task.title,
                "status": task.status,
                "days_blocked": days_blocked,
                "blocking_task_ids": blocking_ids,
                "evidence": {
                    "last_status_change": last_changed.isoformat(),
                    "days_since_last_change": days_blocked,
                    "threshold_days": days,
                    "blocking_task_ids": blocking_ids,
                },
            })
    stale.sort(key=lambda x: -x["days_blocked"])
    return stale


# ---------------------------------------------------------------------------
# FR-INT-04: Critical path (longest chain by count)
# ---------------------------------------------------------------------------
def get_critical_path(project) -> dict[str, Any]:
    """
    Find the longest chain of dependent incomplete tasks (by count).
    Returns the chain as an ordered list of task IDs (prerequisite first).
    Uses iterative topological sort + DP — no recursion.
    """
    incomplete_ids = set(
        Task.objects.filter(
            project=project,
            status__in=_incomplete_statuses(),
        ).values_list("id", flat=True)
    )

    if not incomplete_ids:
        return {"length": 0, "task_ids": [], "evidence": {"message": "No incomplete tasks."}}

    # Build adjacency list (only among incomplete tasks)
    all_deps = list(
        TaskDependency.objects.filter(
            prerequisite_task__project=project,
            prerequisite_task_id__in=incomplete_ids,
            dependent_task_id__in=incomplete_ids,
        ).values_list("prerequisite_task_id", "dependent_task_id")
    )

    # prerequisite → list of dependents
    forward: dict[int, list[int]] = {t: [] for t in incomplete_ids}
    # dependent → list of prerequisites (for in-degree)
    in_degree: dict[int, int] = {t: 0 for t in incomplete_ids}
    for pre, dep in all_deps:
        forward[pre].append(dep)
        in_degree[dep] = in_degree.get(dep, 0) + 1

    # Kahn's topological sort
    queue = deque([t for t in incomplete_ids if in_degree[t] == 0])
    topo_order = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbour in forward.get(node, []):
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    # DP: dp[node] = (length, predecessor)
    dp: dict[int, int] = {t: 1 for t in incomplete_ids}
    predecessor: dict[int, int | None] = {t: None for t in incomplete_ids}
    for node in topo_order:
        for dep in forward.get(node, []):
            if dp[node] + 1 > dp[dep]:
                dp[dep] = dp[node] + 1
                predecessor[dep] = node

    # Find the end of the longest path
    end_node = max(dp, key=lambda t: dp[t])
    path_length = dp[end_node]

    # Reconstruct path
    path = []
    current = end_node
    while current is not None:
        path.append(current)
        current = predecessor[current]
    path.reverse()

    return {
        "length": path_length,
        "task_ids": path,
        "evidence": {
            "chain_length": path_length,
            "start_task_id": path[0] if path else None,
            "end_task_id": path[-1] if path else None,
        },
    }


# ---------------------------------------------------------------------------
# FR-INT-05: Overdue and due-soon
# ---------------------------------------------------------------------------
def get_overdue_and_due_soon(project, due_soon_days: int = DUE_SOON_DAYS) -> dict[str, Any]:
    today = date.today()
    soon_cutoff = today + timedelta(days=due_soon_days)

    incomplete_qs = Task.objects.filter(
        project=project,
        status__in=_incomplete_statuses(),
    )

    overdue = list(
        incomplete_qs.filter(due_date__lt=today)
        .values("id", "title", "due_date", "priority", "assignee_id")
    )
    due_soon = list(
        incomplete_qs.filter(due_date__gte=today, due_date__lte=soon_cutoff)
        .values("id", "title", "due_date", "priority", "assignee_id")
    )

    for t in overdue:
        t["days_overdue"] = (today - t["due_date"]).days
        t["due_date"] = t["due_date"].isoformat()
        t["evidence"] = {"due_date": t["due_date"], "days_overdue": t["days_overdue"]}
    for t in due_soon:
        t["days_until_due"] = (t["due_date"] - today).days
        t["due_date"] = t["due_date"].isoformat()
        t["evidence"] = {"due_date": t["due_date"], "days_until_due": t["days_until_due"]}

    return {"overdue": overdue, "due_soon": due_soon}


# ---------------------------------------------------------------------------
# FR-INT-06: Workload view
# ---------------------------------------------------------------------------
def get_workload(project) -> dict[str, Any]:
    """
    Active task count per member (assigned incomplete tasks).
    Includes a disclaimer that counts are not a productivity measure.
    """
    rows = (
        Task.objects.filter(
            project=project,
            status__in=_incomplete_statuses(),
            assignee__isnull=False,
        )
        .values("assignee_id", "assignee__username", "assignee__email")
        .annotate(active_task_count=Count("id"))
        .order_by("-active_task_count")
    )
    return {
        "disclaimer": "Task counts reflect assignments only and are not a measure of productivity or effort.",
        "workload": [
            {
                "user_id": r["assignee_id"],
                "username": r["assignee__username"],
                "email": r["assignee__email"],
                "active_task_count": r["active_task_count"],
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# FR-INT-07: Project health
# ---------------------------------------------------------------------------
def get_project_health(project) -> dict[str, Any]:
    """
    Classify project as Healthy / Needs Attention / At Risk.
    Rules (documented in README):
      At Risk:
        - >= 2 overdue Critical/High tasks, OR
        - a bottleneck with impact >= AT_RISK_BOTTLENECK_IMPACT that is also overdue, OR
        - critical path cannot finish before project.target_date (if set)
      Needs Attention:
        - any overdue task, OR
        - any stale blocker, OR
        - any bottleneck above threshold
      Healthy: none of the above
    """
    today = date.today()
    evidence: dict[str, Any] = {}

    # Overdue tasks
    overdue_all = list(
        Task.objects.filter(
            project=project,
            status__in=_incomplete_statuses(),
            due_date__lt=today,
        ).values("id", "title", "priority", "due_date")
    )
    overdue_critical_high = [
        t for t in overdue_all
        if t["priority"] in (Task.Priority.CRITICAL, Task.Priority.HIGH)
    ]

    # Bottlenecks
    bottlenecks = get_bottlenecks(project)
    severe_overdue_bottleneck = any(
        b["downstream_count"] >= AT_RISK_BOTTLENECK_IMPACT
        and b["due_date"] is not None
        and date.fromisoformat(b["due_date"]) < today
        for b in bottlenecks
    )

    # Critical path vs target_date
    critical_path_at_risk = False
    if project.target_date:
        cp = get_critical_path(project)
        if cp["length"] > 0:
            # Rough heuristic: if incomplete chain length > days remaining, flag
            days_remaining = (project.target_date - today).days
            if cp["length"] > max(days_remaining, 0):
                critical_path_at_risk = True
                evidence["critical_path_length"] = cp["length"]
                evidence["days_remaining"] = days_remaining

    # Stale blockers
    stale = get_stale_blockers(project)

    # --- Classify ---
    if (
        len(overdue_critical_high) >= AT_RISK_OVERDUE_COUNT
        or severe_overdue_bottleneck
        or critical_path_at_risk
    ):
        health = "AT_RISK"
        evidence.update({
            "overdue_critical_high_count": len(overdue_critical_high),
            "overdue_critical_high_ids": [t["id"] for t in overdue_critical_high],
            "severe_overdue_bottleneck": severe_overdue_bottleneck,
            "critical_path_at_risk": critical_path_at_risk,
        })
    elif overdue_all or stale or bottlenecks:
        health = "NEEDS_ATTENTION"
        evidence.update({
            "overdue_task_count": len(overdue_all),
            "overdue_task_ids": [t["id"] for t in overdue_all],
            "stale_blocker_count": len(stale),
            "bottleneck_count": len(bottlenecks),
        })
    else:
        health = "HEALTHY"

    return {"health": health, "evidence": evidence}


# ---------------------------------------------------------------------------
# FR-INT-08: Recommendations with evidence
# ---------------------------------------------------------------------------
def get_recommendations(project) -> list[dict[str, Any]]:
    """
    Generate plain-language recommendations, each with evidence.
    Rules are deterministic — no AI involved.
    """
    today = date.today()
    recs = []

    # Overdue high/critical tasks
    overdue_important = Task.objects.filter(
        project=project,
        status__in=_incomplete_statuses(),
        due_date__lt=today,
        priority__in=[Task.Priority.CRITICAL, Task.Priority.HIGH],
    ).select_related("assignee")

    for task in overdue_important:
        days_overdue = (today - task.due_date).days
        recs.append({
            "type": "OVERDUE_HIGH_PRIORITY",
            "severity": "HIGH",
            "message": (
                f'Task "{task.title}" is {task.priority.lower()} priority and {days_overdue} day(s) overdue. '
                f"Prioritize or reassign it."
            ),
            "evidence": {
                "task_id": task.pk,
                "task_title": task.title,
                "priority": task.priority,
                "due_date": task.due_date.isoformat(),
                "days_overdue": days_overdue,
                "assignee_id": task.assignee_id,
            },
        })

    # Bottlenecks
    for b in get_bottlenecks(project):
        is_overdue = b["due_date"] and date.fromisoformat(b["due_date"]) < today
        recs.append({
            "type": "BOTTLENECK",
            "severity": "HIGH" if is_overdue else "MEDIUM",
            "message": (
                f'Task "{b["task_title"]}" blocks {b["downstream_count"]} other task(s)'
                + (" and is overdue" if is_overdue else "")
                + ". Prioritize it to unblock downstream work."
            ),
            "evidence": b["evidence"] | {"task_id": b["task_id"], "task_title": b["task_title"]},
        })

    # Stale blockers
    for s in get_stale_blockers(project):
        recs.append({
            "type": "STALE_BLOCKER",
            "severity": "MEDIUM",
            "message": (
                f'Task "{s["task_title"]}" has been blocked for {s["days_blocked"]} day(s). '
                f"Resolve the {len(s['blocking_task_ids'])} blocking prerequisite(s) to move it forward."
            ),
            "evidence": s["evidence"] | {"task_id": s["task_id"], "task_title": s["task_title"]},
        })

    # Unassigned overdue tasks
    unassigned_overdue = Task.objects.filter(
        project=project,
        status__in=_incomplete_statuses(),
        due_date__lt=today,
        assignee__isnull=True,
    )
    for task in unassigned_overdue:
        days_overdue = (today - task.due_date).days
        recs.append({
            "type": "UNASSIGNED_OVERDUE",
            "severity": "MEDIUM",
            "message": (
                f'Task "{task.title}" is overdue by {days_overdue} day(s) and has no assignee. '
                f"Assign it to someone."
            ),
            "evidence": {
                "task_id": task.pk,
                "task_title": task.title,
                "due_date": task.due_date.isoformat(),
                "days_overdue": days_overdue,
            },
        })

    # Sort: HIGH severity first
    recs.sort(key=lambda r: (0 if r["severity"] == "HIGH" else 1))
    return recs


# ---------------------------------------------------------------------------
# FR-INT-09: Project summary (used by insights/ endpoint)
# ---------------------------------------------------------------------------
def get_project_summary(project) -> dict[str, Any]:
    """
    Top-level summary used by GET /projects/{id}/insights/.
    """
    health_result = get_project_health(project)
    overdue_data = get_overdue_and_due_soon(project)
    bottlenecks = get_bottlenecks(project)
    stale = get_stale_blockers(project)
    cp = get_critical_path(project)

    incomplete_count = Task.objects.filter(
        project=project, status__in=_incomplete_statuses()
    ).count()
    done_count = Task.objects.filter(project=project, status=Task.Status.DONE).count()
    total_count = incomplete_count + done_count

    return {
        "health": health_result["health"],
        "health_evidence": health_result["evidence"],
        "total_tasks": total_count,
        "done_tasks": done_count,
        "incomplete_tasks": incomplete_count,
        "overdue_count": len(overdue_data["overdue"]),
        "due_soon_count": len(overdue_data["due_soon"]),
        "bottleneck_count": len(bottlenecks),
        "stale_blocker_count": len(stale),
        "critical_path_length": cp["length"],
    }
