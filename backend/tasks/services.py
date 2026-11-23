
from django.db import transaction
from rest_framework.exceptions import ValidationError
from projects.models import Project
from projects.models import ProjectMember
from workspaces.models import WorkspaceMember

from .models import Task


@transaction.atomic
def create_task(
    *,
    project,
    title,
    description="",
    priority=Task.Priority.MEDIUM,
    assignee=None,
    due_date=None,
    labels=None,
    creator,
):
    """
    Create a task inside a project.

    Rules:
    1. Creator must have access to the project.
    2. Assignee must be a member of the project.
    3. Task is created with TODO status by default.
    """
    if project.status != Project.Status.ACTIVE:
        raise ValidationError({
            "project": "Tasks can only be created in active projects."
        })

    # Check whether the creator is a project member.
    is_project_member = ProjectMember.objects.filter(
        project=project,
        user=creator,
    ).exists()

    # Workspace Owners and Admins can also create tasks.
    is_workspace_admin = WorkspaceMember.objects.filter(
        workspace=project.workspace,
        user=creator,
        role__in=[
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ],
    ).exists()

    if not (is_project_member or is_workspace_admin):
        raise ValidationError({
            "permission": "You do not have permission to create tasks in this project."
        })

    # Validate the assignee.
    if assignee is not None:
        is_valid_assignee = ProjectMember.objects.filter(
            project=project,
            user=assignee,
        ).exists()

        if not is_valid_assignee:
            raise ValidationError({
                "assignee": "The assigned user must be a member of this project."
            })

    # Validate the title.
    if not title or not title.strip():
        raise ValidationError({
            "title": "Task title cannot be empty."
        })

    # Create the task.
    task = Task.objects.create(
        project=project,
        title=title.strip(),
        description=description,
        priority=priority,
        assignee=assignee,
        due_date=due_date,
        created_by=creator,
    )
    if labels:
        task.labels.set(labels)
    return task


def has_cycle(prerequisite_task_id: int, dependent_task_id: int) -> bool:
    """
    Return True if adding the edge prerequisite→dependent would create a cycle.
    Uses iterative BFS from dependent_task looking for prerequisite_task.
    Does NOT use recursion (safe for large graphs, NFR-04).
    """
    from .models import TaskDependency
    from collections import deque
    visited = set()
    queue = deque([dependent_task_id])
    while queue:
        current = queue.popleft()
        if current == prerequisite_task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        # All tasks that `current` depends on (its prerequisites)
        for dependent_id in TaskDependency.objects.filter(
            prerequisite_task_id=current
        ).values_list("dependent_task_id", flat=True):
            if dependent_id not in visited:
                queue.append(dependent_id)


def log_activity(*, task, actor, action, detail=None):
    from .models import ActivityLog
    ActivityLog.objects.create(
        task=task,
        project=task.project,
        actor=actor,
        action=action,
        detail=detail or {},
    )