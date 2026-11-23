import pytest
from tasks.insights import get_critical_path
from rest_framework.test import APIClient
from tasks.insights import get_bottlenecks
from projects.models import Project, ProjectMember
from tasks.models import Task, TaskLabel, TaskDependency
from workspaces.models import Workspace, WorkspaceMember
from tasks.insights import downstream_impact
from datetime import date, timedelta
from tasks.models import ActivityLog, TaskDependency
from tasks.insights import (
    get_overdue_and_due_soon,
    get_project_health,
    get_project_summary,
    get_recommendations,
    get_stale_blockers,
    get_workload,
)
from django.utils import timezone
from tasks.services import has_cycle
@pytest.fixture
def task_test_data(db, django_user_model):
    # Create users.
    owner = django_user_model.objects.create_user(
        username="workspace_owner",
        email="owner@example.com",
        password="TestPassword123!",
    )

    admin = django_user_model.objects.create_user(
        username="workspace_admin",
        email="admin@example.com",
        password="TestPassword123!",
    )

    manager = django_user_model.objects.create_user(
        username="project_manager",
        email="manager@example.com",
        password="TestPassword123!",
    )

    member = django_user_model.objects.create_user(
        username="project_member",
        email="member@example.com",
        password="TestPassword123!",
    )

    assignee = django_user_model.objects.create_user(
        username="task_assignee",
        email="assignee@example.com",
        password="TestPassword123!",
    )

    outsider = django_user_model.objects.create_user(
        username="outsider",
        email="outsider@example.com",
        password="TestPassword123!",
    )

    # Create workspace.
    workspace = Workspace.objects.create(
        name="Test Workspace",
        slug="test-workspace",
        owner=owner,
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=owner,
        role=WorkspaceMember.Role.OWNER,
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=admin,
        role=WorkspaceMember.Role.ADMIN,
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=manager,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=member,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=assignee,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    # Create project.
    project = Project.objects.create(
        workspace=workspace,
        name="Test Project",
        slug="test-project",
        created_by=owner,
    )

    ProjectMember.objects.create(
        project=project,
        user=manager,
        role=ProjectMember.Role.MANAGER,
    )

    ProjectMember.objects.create(
        project=project,
        user=member,
        role=ProjectMember.Role.MEMBER,
    )

    ProjectMember.objects.create(
        project=project,
        user=assignee,
        role=ProjectMember.Role.MEMBER,
    )

    return {
        "owner": owner,
        "admin": admin,
        "manager": manager,
        "member": member,
        "assignee": assignee,
        "outsider": outsider,
        "workspace": workspace,
        "project": project,
    }


@pytest.fixture
def api_client():
    return APIClient()


def task_list_url(project):
    return f"/api/v1/projects/{project.id}/tasks/"


def task_detail_url(task):
    return f"/api/v1/tasks/{task.id}/"
def project_label_url(project):
    return f"/api/v1/projects/{project.id}/labels/"


def label_detail_url(label):
    return f"/api/v1/labels/{label.id}/"

def create_test_task(project, creator, **kwargs):
    return Task.objects.create(
        project=project,
        title=kwargs.get("title", "Test Task"),
        description=kwargs.get("description", ""),
        status=kwargs.get("status", Task.Status.TODO),
        priority=kwargs.get("priority", Task.Priority.MEDIUM),
        created_by=creator,
        assignee=kwargs.get("assignee"),
        due_date=kwargs.get("due_date"),
    )


# --------------------------------------------------
# TASK CREATION
# --------------------------------------------------

@pytest.mark.django_db
def test_project_member_can_create_task(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        task_list_url(data["project"]),
        {
            "title": "Implement authentication",
            "description": "Build JWT authentication.",
            "priority": "HIGH",
        },
        format="json",
    )

    assert response.status_code == 201
    assert Task.objects.filter(
        title="Implement authentication"
    ).exists()


@pytest.mark.django_db
def test_workspace_admin_can_create_task(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["admin"])

    response = api_client.post(
        task_list_url(data["project"]),
        {
            "title": "Admin created task",
            "priority": "MEDIUM",
        },
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_unauthorized_user_cannot_create_task(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["outsider"])

    response = api_client.post(
        task_list_url(data["project"]),
        {"title": "Unauthorized task"},
        format="json",
    )

    assert response.status_code == 404
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_assignee_must_belong_to_project(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        task_list_url(data["project"]),
        {
            "title": "Invalid assignment",
            "assignee": data["outsider"].id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert Task.objects.count() == 0


@pytest.mark.django_db
def test_task_uses_default_status_and_priority(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        task_list_url(data["project"]),
        {"title": "Default values task"},
        format="json",
    )

    assert response.status_code == 201

    task = Task.objects.get(title="Default values task")

    assert task.status == Task.Status.TODO
    assert task.priority == Task.Priority.MEDIUM


# --------------------------------------------------
# TASK LISTING AND FILTERING
# --------------------------------------------------

@pytest.mark.django_db
def test_project_member_can_list_tasks(
    api_client, task_test_data
):
    data = task_test_data

    create_test_task(data["project"], data["manager"])
    create_test_task(
        data["project"],
        data["manager"],
        title="Another task",
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"])
    )

    assert response.status_code == 200
    assert response.data["count"] == 2


@pytest.mark.django_db
def test_task_filtering_by_status(
    api_client, task_test_data
):
    data = task_test_data

    create_test_task(
        data["project"],
        data["manager"],
        title="Completed task",
        status=Task.Status.DONE,
    )

    create_test_task(
        data["project"],
        data["manager"],
        title="Pending task",
        status=Task.Status.TODO,
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?status=DONE"
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["title"] == "Completed task"


@pytest.mark.django_db
def test_task_filtering_by_priority(
    api_client, task_test_data
):
    data = task_test_data

    create_test_task(
        data["project"],
        data["manager"],
        title="Critical task",
        priority=Task.Priority.CRITICAL,
    )

    create_test_task(
        data["project"],
        data["manager"],
        title="Low priority task",
        priority=Task.Priority.LOW,
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?priority=CRITICAL"
    )

    assert response.status_code == 200
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_task_search_by_title(
    api_client, task_test_data
):
    data = task_test_data

    create_test_task(
        data["project"],
        data["manager"],
        title="Implement authentication",
    )

    create_test_task(
        data["project"],
        data["manager"],
        title="Build dashboard",
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?search=authentication"
    )

    assert response.status_code == 200
    assert response.data["count"] == 1


# --------------------------------------------------
# TASK RETRIEVAL
# --------------------------------------------------

@pytest.mark.django_db
def test_project_member_can_retrieve_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 200
    assert response.data["id"] == task.id


@pytest.mark.django_db
def test_unauthorized_user_cannot_retrieve_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    api_client.force_authenticate(user=data["outsider"])

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 404


# --------------------------------------------------
# TASK UPDATES
# --------------------------------------------------

@pytest.mark.django_db
def test_task_creator_can_update_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["member"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.patch(
        task_detail_url(task),
        {"title": "Updated task title"},
        format="json",
    )

    assert response.status_code == 200

    task.refresh_from_db()
    assert task.title == "Updated task title"


@pytest.mark.django_db
def test_task_assignee_can_update_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
        assignee=data["assignee"],
    )

    api_client.force_authenticate(user=data["assignee"])

    response = api_client.patch(
        task_detail_url(task),
        {"status": "IN_PROGRESS"},
        format="json",
    )

    assert response.status_code == 200

    task.refresh_from_db()
    assert task.status == Task.Status.IN_PROGRESS


@pytest.mark.django_db
def test_invalid_status_is_rejected(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["member"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.patch(
        task_detail_url(task),
        {"status": "INVALID_STATUS"},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_priority_is_rejected(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["member"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.patch(
        task_detail_url(task),
        {"priority": "URGENT"},
        format="json",
    )

    assert response.status_code == 400


# --------------------------------------------------
# TASK DELETION
# --------------------------------------------------

@pytest.mark.django_db
def test_project_manager_can_delete_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    api_client.force_authenticate(user=data["manager"])

    response = api_client.delete(task_detail_url(task))

    assert response.status_code == 204
    assert not Task.objects.filter(id=task.id).exists()


@pytest.mark.django_db
def test_project_member_cannot_delete_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.delete(task_detail_url(task))

    assert response.status_code == 403
    assert Task.objects.filter(id=task.id).exists()

# --------------------------------------------------
# FILTER VALIDATION
# --------------------------------------------------

@pytest.mark.django_db
def test_invalid_assignee_filter_returns_400(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?assignee=abc"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_status_filter_returns_400(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?status=INVALID"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_priority_filter_returns_400(
    api_client, task_test_data
):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?priority=URGENT"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_assignee_unassigned_filter(
    api_client, task_test_data
):
    data = task_test_data

    create_test_task(
        data["project"],
        data["manager"],
        title="Unassigned task",
    )

    create_test_task(
        data["project"],
        data["manager"],
        title="Assigned task",
        assignee=data["assignee"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?assignee=unassigned"
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["title"] == "Unassigned task"


# --------------------------------------------------
# ARCHIVED PROJECT BEHAVIOUR
# --------------------------------------------------

@pytest.mark.django_db
def test_tasks_can_be_viewed_in_archived_project(
    api_client, task_test_data
):
    data = task_test_data

    data["project"].status = Project.Status.ARCHIVED
    data["project"].save()

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 200


@pytest.mark.django_db
def test_cannot_create_task_in_archived_project(
    api_client, task_test_data
):
    data = task_test_data

    data["project"].status = Project.Status.ARCHIVED
    data["project"].save()

    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        task_list_url(data["project"]),
        {"title": "Should not be created"},
        format="json",
    )

    assert response.status_code == 403
    assert not Task.objects.filter(
        title="Should not be created"
    ).exists()


@pytest.mark.django_db
def test_cannot_update_task_in_archived_project(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["member"],
    )

    data["project"].status = Project.Status.ARCHIVED
    data["project"].save()

    api_client.force_authenticate(user=data["member"])

    response = api_client.patch(
        task_detail_url(task),
        {"title": "Should not update"},
        format="json",
    )

    assert response.status_code == 403

    task.refresh_from_db()
    assert task.title == "Test Task"


@pytest.mark.django_db
def test_cannot_delete_task_in_archived_project(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    data["project"].status = Project.Status.ARCHIVED
    data["project"].save()

    api_client.force_authenticate(user=data["manager"])

    response = api_client.delete(task_detail_url(task))

    assert response.status_code == 403
    assert Task.objects.filter(id=task.id).exists()


@pytest.mark.django_db
def test_reactivated_project_allows_task_updates(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["member"],
    )

    data["project"].status = Project.Status.ARCHIVED
    data["project"].save()

    data["project"].status = Project.Status.ACTIVE
    data["project"].save()

    api_client.force_authenticate(user=data["member"])

    response = api_client.patch(
        task_detail_url(task),
        {"title": "Updated after reactivation"},
        format="json",
    )

    assert response.status_code == 200
    task.refresh_from_db()
    assert task.title == "Updated after reactivation"

@pytest.mark.django_db
def test_invalid_page_returns_400(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?page=abc"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_zero_page_returns_400(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?page=0"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_page_size_returns_400(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?page_size=abc"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_zero_page_size_returns_400(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?page_size=0"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_page_size_is_capped_at_100(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + "?page_size=500"
    )

    assert response.status_code == 200
    assert len(response.data["results"]) <= 100

# --------------------------------------------------
# AUTHENTICATION AND PERMISSION BOUNDARIES
# --------------------------------------------------

@pytest.mark.django_db
def test_unauthenticated_user_cannot_list_tasks(
    api_client, task_test_data
):
    data = task_test_data

    response = api_client.get(
        task_list_url(data["project"])
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_unauthenticated_user_cannot_retrieve_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 401


@pytest.mark.django_db
def test_workspace_admin_can_retrieve_task_without_project_membership(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    # The workspace admin is deliberately not a ProjectMember.
    assert not ProjectMember.objects.filter(
        project=data["project"],
        user=data["admin"],
    ).exists()

    api_client.force_authenticate(user=data["admin"])

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 200


@pytest.mark.django_db
def test_removed_project_member_loses_task_access(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    # Remove the user from the project.
    ProjectMember.objects.filter(
        project=data["project"],
        user=data["member"],
    ).delete()

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 404


@pytest.mark.django_db
def test_removed_project_member_cannot_list_project_tasks(
    api_client, task_test_data
):
    data = task_test_data

    create_test_task(
        data["project"],
        data["manager"],
    )

    ProjectMember.objects.filter(
        project=data["project"],
        user=data["member"],
    ).delete()

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"])
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_user_cannot_access_task_from_another_project(
    api_client, task_test_data
):
    data = task_test_data

    other_project = Project.objects.create(
        workspace=data["workspace"],
        name="Another Project",
        slug="another-project",
        created_by=data["owner"],
    )

    task = create_test_task(
        other_project,
        data["owner"],
        title="Private project task",
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 404


@pytest.mark.django_db
def test_project_manager_can_update_task(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["member"],
    )

    api_client.force_authenticate(user=data["manager"])

    response = api_client.patch(
        task_detail_url(task),
        {"priority": "CRITICAL"},
        format="json",
    )

    assert response.status_code == 200

    task.refresh_from_db()
    assert task.priority == Task.Priority.CRITICAL
@pytest.mark.django_db
def test_cancelled_project_tasks_are_read_only(
    api_client, task_test_data
):
    data = task_test_data

    task = create_test_task(
        data["project"],
        data["manager"],
    )

    data["project"].status = Project.Status.CANCELLED
    data["project"].save()

    api_client.force_authenticate(user=data["manager"])

    response = api_client.patch(
        task_detail_url(task),
        {"title": "Should not change"},
        format="json",
    )

    assert response.status_code == 403

    task.refresh_from_db()
    assert task.title == "Test Task"


@pytest.mark.django_db
def test_cancelled_project_rejects_new_tasks(
    api_client, task_test_data
):
    data = task_test_data

    data["project"].status = Project.Status.CANCELLED
    data["project"].save()

    api_client.force_authenticate(user=data["manager"])

    response = api_client.post(
        task_list_url(data["project"]),
        {"title": "New task"},
        format="json",
    )

    assert response.status_code == 403
    assert not Task.objects.filter(title="New task").exists()

# --------------------------------------------------
# TASK LABEL MANAGEMENT
# --------------------------------------------------

@pytest.mark.django_db
def test_project_manager_can_create_label(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["manager"])

    response = api_client.post(
        project_label_url(data["project"]),
        {"name": "Bug", "color": "#ef4444"},
        format="json",
    )

    assert response.status_code == 201
    assert TaskLabel.objects.filter(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    ).exists()


@pytest.mark.django_db
def test_workspace_owner_can_create_label(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["owner"])

    response = api_client.post(
        project_label_url(data["project"]),
        {"name": "Feature", "color": "#22c55e"},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_workspace_admin_can_create_label(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["admin"])

    response = api_client.post(
        project_label_url(data["project"]),
        {"name": "Documentation"},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_project_member_can_list_labels(api_client, task_test_data):
    data = task_test_data

    TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(project_label_url(data["project"]))

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["name"] == "Bug"


@pytest.mark.django_db
def test_duplicate_label_name_is_rejected_case_insensitively(
    api_client, task_test_data
):
    data = task_test_data

    TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["manager"])

    response = api_client.post(
        project_label_url(data["project"]),
        {"name": "bug"},
        format="json",
    )

    assert response.status_code == 400
    assert TaskLabel.objects.filter(
        project=data["project"]
    ).count() == 1


@pytest.mark.django_db
def test_project_member_cannot_create_label(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        project_label_url(data["project"]),
        {"name": "Unauthorized"},
        format="json",
    )

    assert response.status_code == 403
    assert not TaskLabel.objects.filter(name="Unauthorized").exists()


@pytest.mark.django_db
def test_outsider_cannot_list_project_labels(api_client, task_test_data):
    data = task_test_data
    api_client.force_authenticate(user=data["outsider"])

    response = api_client.get(project_label_url(data["project"]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_project_member_can_retrieve_label(api_client, task_test_data):
    data = task_test_data

    label = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(label_detail_url(label))

    assert response.status_code == 200
    assert response.data["name"] == "Bug"


@pytest.mark.django_db
def test_project_member_cannot_update_label(api_client, task_test_data):
    data = task_test_data

    label = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.patch(
        label_detail_url(label),
        {"name": "Feature"},
        format="json",
    )

    assert response.status_code == 403

    label.refresh_from_db()
    assert label.name == "Bug"


@pytest.mark.django_db
def test_project_manager_can_update_label(api_client, task_test_data):
    data = task_test_data

    label = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["manager"])

    response = api_client.patch(
        label_detail_url(label),
        {"name": "Critical Bug"},
        format="json",
    )

    assert response.status_code == 200

    label.refresh_from_db()
    assert label.name == "Critical Bug"


@pytest.mark.django_db
def test_project_member_cannot_delete_label(api_client, task_test_data):
    data = task_test_data

    label = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.delete(label_detail_url(label))

    assert response.status_code == 403
    assert TaskLabel.objects.filter(id=label.id).exists()


@pytest.mark.django_db
def test_project_manager_can_delete_label(api_client, task_test_data):
    data = task_test_data

    label = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["manager"])

    response = api_client.delete(label_detail_url(label))

    assert response.status_code == 204
    assert not TaskLabel.objects.filter(id=label.id).exists()


@pytest.mark.django_db
def test_user_cannot_access_label_from_another_project(
    api_client, task_test_data
):
    data = task_test_data

    other_project = Project.objects.create(
        workspace=data["workspace"],
        name="Another Project",
        slug="another-project",
        created_by=data["owner"],
    )

    label = TaskLabel.objects.create(
        project=other_project,
        name="Private Label",
        created_by=data["owner"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(label_detail_url(label))

    assert response.status_code == 404


@pytest.mark.django_db
def test_cannot_create_label_in_archived_project(api_client, task_test_data):
    data = task_test_data

    data["project"].status = Project.Status.ARCHIVED
    data["project"].save()

    api_client.force_authenticate(user=data["manager"])

    response = api_client.post(
        project_label_url(data["project"]),
        {"name": "Archived Label"},
        format="json",
    )

    assert response.status_code == 403
    assert not TaskLabel.objects.filter(name="Archived Label").exists()

# --------------------------------------------------
# TASK-LABEL ASSIGNMENT AND FILTERING
# --------------------------------------------------

@pytest.mark.django_db
def test_create_task_with_multiple_labels(api_client, task_test_data):
    data = task_test_data

    bug = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    urgent = TaskLabel.objects.create(
        project=data["project"],
        name="Urgent",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        task_list_url(data["project"]),
        {
            "title": "Fix login issue",
            "labels": [bug.id, urgent.id],
        },
        format="json",
    )

    assert response.status_code == 201, response.data

    task = Task.objects.get(title="Fix login issue")

    assert set(task.labels.values_list("id", flat=True)) == {
        bug.id,
        urgent.id,
    }


@pytest.mark.django_db
def test_update_task_labels(api_client, task_test_data):
    data = task_test_data

    task = create_test_task(data["project"], data["manager"])

    bug = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    feature = TaskLabel.objects.create(
        project=data["project"],
        name="Feature",
        created_by=data["manager"],
    )

    api_client.force_authenticate(user=data["manager"])

    response = api_client.patch(
        task_detail_url(task),
        {"labels": [bug.id, feature.id]},
        format="json",
    )

    assert response.status_code == 200, response.data

    task.refresh_from_db()

    assert set(task.labels.values_list("id", flat=True)) == {
        bug.id,
        feature.id,
    }


@pytest.mark.django_db
def test_remove_all_task_labels(api_client, task_test_data):
    data = task_test_data

    task = create_test_task(data["project"], data["manager"])

    bug = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    task.labels.add(bug)

    api_client.force_authenticate(user=data["manager"])

    response = api_client.patch(
        task_detail_url(task),
        {"labels": []},
        format="json",
    )

    assert response.status_code == 200

    task.refresh_from_db()
    assert task.labels.count() == 0


@pytest.mark.django_db
def test_task_rejects_label_from_another_project(
    api_client, task_test_data
):
    data = task_test_data

    other_project = Project.objects.create(
        workspace=data["workspace"],
        name="Another Project",
        slug="another-project",
        created_by=data["owner"],
    )

    foreign_label = TaskLabel.objects.create(
        project=other_project,
        name="Private",
        created_by=data["owner"],
    )

    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        task_list_url(data["project"]),
        {
            "title": "Invalid label assignment",
            "labels": [foreign_label.id],
        },
        format="json",
    )

    assert response.status_code == 400

    assert not Task.objects.filter(
        title="Invalid label assignment"
    ).exists()


@pytest.mark.django_db
def test_filter_tasks_by_label(api_client, task_test_data):
    data = task_test_data

    bug = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    feature = TaskLabel.objects.create(
        project=data["project"],
        name="Feature",
        created_by=data["manager"],
    )

    bug_task = create_test_task(
        data["project"],
        data["manager"],
        title="Fix login",
    )
    bug_task.labels.add(bug)

    feature_task = create_test_task(
        data["project"],
        data["manager"],
        title="Add dashboard",
    )
    feature_task.labels.add(feature)

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(
        task_list_url(data["project"]) + f"?label={bug.id}"
    )

    assert response.status_code == 200

    returned_ids = {
        task["id"] for task in response.data["results"]
    }

    assert returned_ids == {bug_task.id}


@pytest.mark.django_db
def test_task_response_includes_label_ids(api_client, task_test_data):
    data = task_test_data

    task = create_test_task(data["project"], data["manager"])

    bug = TaskLabel.objects.create(
        project=data["project"],
        name="Bug",
        created_by=data["manager"],
    )

    task.labels.add(bug)

    api_client.force_authenticate(user=data["member"])

    response = api_client.get(task_detail_url(task))

    assert response.status_code == 200
    assert response.data["labels"] == [bug.id]
@pytest.mark.django_db
def test_task_cannot_depend_on_itself(api_client, task_test_data):
    data = task_test_data
    task = create_test_task(data["project"], data["manager"])
    api_client.force_authenticate(user=data["manager"])

    response = api_client.post(
        f"/api/v1/tasks/{task.id}/dependencies/",
        {"prerequisite_task_id": task.id},
        format="json",
    )

    assert response.status_code == 400
    assert "itself" in str(response.data).lower()
def test_dependency_cannot_create_two_task_cycle(api_client, task_test_data):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    api_client.force_authenticate(user=data["manager"])

    # A is a prerequisite of B: A → B
    first_response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )
    assert first_response.status_code == 201

    # B as a prerequisite of A would create A → B → A
    cycle_response = api_client.post(
        f"/api/v1/tasks/{task_a.id}/dependencies/",
        {"prerequisite_task_id": task_b.id},
        format="json",
    )

    assert cycle_response.status_code == 400
    assert "cycle" in str(cycle_response.data).lower()
@pytest.mark.django_db
def test_dependency_cannot_create_three_task_cycle(api_client, task_test_data):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    task_c = create_test_task(data["project"], data["manager"], title="Task C")
    api_client.force_authenticate(user=data["manager"])

    # Build A → B → C
    response_ab = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )
    response_bc = api_client.post(
        f"/api/v1/tasks/{task_c.id}/dependencies/",
        {"prerequisite_task_id": task_b.id},
        format="json",
    )
    assert response_ab.status_code == 201
    assert response_bc.status_code == 201

    # C → A would close the cycle
    response_ca = api_client.post(
        f"/api/v1/tasks/{task_a.id}/dependencies/",
        {"prerequisite_task_id": task_c.id},
        format="json",
    )

    assert response_ca.status_code == 400
    assert "cycle" in str(response_ca.data).lower()
@pytest.mark.django_db
def test_valid_diamond_dependencies_are_allowed(api_client, task_test_data):
    data = task_test_data
    tasks = {
        name: create_test_task(data["project"], data["manager"], title=name)
        for name in ("A", "B", "C", "D")
    }
    api_client.force_authenticate(user=data["manager"])

    edges = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

    for prerequisite, dependent in edges:
        response = api_client.post(
            f"/api/v1/tasks/{tasks[dependent].id}/dependencies/",
            {"prerequisite_task_id": tasks[prerequisite].id},
            format="json",
        )
        assert response.status_code == 201, response.data
@pytest.mark.django_db
def test_dependent_task_unblocks_when_prerequisite_is_done(
    api_client, task_test_data
):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    api_client.force_authenticate(user=data["manager"])

    dependency_response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )
    assert dependency_response.status_code == 201

    blocked_response = api_client.get(task_detail_url(task_b))
    assert blocked_response.data["is_blocked"] is True

    completion_response = api_client.patch(
        task_detail_url(task_a),
        {"status": Task.Status.DONE},
        format="json",
    )
    assert completion_response.status_code == 200

    unblocked_response = api_client.get(task_detail_url(task_b))
    assert unblocked_response.data["is_blocked"] is False
@pytest.mark.django_db
def test_project_member_cannot_add_dependency(api_client, task_test_data):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    api_client.force_authenticate(user=data["member"])

    response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_dependency_must_be_within_same_project(api_client, task_test_data):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")

    other_project = Project.objects.create(
        workspace=data["workspace"],
        name="Other Project",
        slug="other-project",
        created_by=data["owner"],
    )
    task_other = create_test_task(other_project, data["owner"], title="Other task")

    api_client.force_authenticate(user=data["manager"])

    response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_other.id},
        format="json",
    )

    assert response.status_code == 400
    assert "same project" in str(response.data).lower()


@pytest.mark.django_db
def test_dependency_endpoint_lists_prerequisites_and_dependents(
    api_client, task_test_data
):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    api_client.force_authenticate(user=data["manager"])

    add_response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )
    assert add_response.status_code == 201

    b_response = api_client.get(
        f"/api/v1/tasks/{task_b.id}/dependencies/"
    )
    a_response = api_client.get(
        f"/api/v1/tasks/{task_a.id}/dependencies/"
    )

    assert b_response.status_code == 200
    assert [item["prerequisite_task_id"] for item in b_response.data["prerequisites"]] == [task_a.id]
    assert [item["dependent_task_id"] for item in a_response.data["dependents"]] == [task_b.id]


@pytest.mark.django_db
def test_project_manager_can_remove_dependency(api_client, task_test_data):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    api_client.force_authenticate(user=data["manager"])

    add_response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )
    assert add_response.status_code == 201
    dependency_id = add_response.data["id"]

    delete_response = api_client.delete(
        f"/api/v1/tasks/{task_b.id}/dependencies/{dependency_id}/"
    )

    assert delete_response.status_code == 204

    list_response = api_client.get(
        f"/api/v1/tasks/{task_b.id}/dependencies/"
    )
    assert list_response.data["prerequisites"] == []


@pytest.mark.django_db
def test_dependency_requires_authentication(api_client, task_test_data):
    data = task_test_data
    task = create_test_task(data["project"], data["manager"])

    response = api_client.get(
        f"/api/v1/tasks/{task.id}/dependencies/"
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_blocked_task_warns_when_moved_to_in_progress(
    api_client, task_test_data
):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    api_client.force_authenticate(user=data["manager"])

    dependency_response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )
    assert dependency_response.status_code == 201

    response = api_client.patch(
        task_detail_url(task_b),
        {"status": Task.Status.IN_PROGRESS},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["is_blocked"] is True
    assert any("blocked" in warning.lower() for warning in response.data["warnings"])


@pytest.mark.django_db
def test_dependent_task_unblocks_when_prerequisite_is_done(
    api_client, task_test_data
):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    api_client.force_authenticate(user=data["manager"])

    dependency_response = api_client.post(
        f"/api/v1/tasks/{task_b.id}/dependencies/",
        {"prerequisite_task_id": task_a.id},
        format="json",
    )
    assert dependency_response.status_code == 201

    blocked_response = api_client.get(task_detail_url(task_b))
    assert blocked_response.data["is_blocked"] is True

    completion_response = api_client.patch(
        task_detail_url(task_a),
        {"status": Task.Status.DONE},
        format="json",
    )
    assert completion_response.status_code == 200
    unblocked_response = api_client.get(task_detail_url(task_b))
    assert unblocked_response.data["is_blocked"] is False
def test_downstream_impact_counts_unique_transitive_tasks():
    # A branches to B and C; both paths rejoin at D, then continue to E.
    dependencies = [
        (1, 2),
        (1, 3),
        (2, 4),
        (3, 4),
        (4, 5),
    ]

    assert downstream_impact(1, dependencies) == 4
@pytest.mark.django_db
def test_bottleneck_flags_task_at_impact_threshold(
    task_test_data
):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    task_c = create_test_task(data["project"], data["manager"], title="Task C")

    TaskDependency.objects.create(
        prerequisite_task=task_a,
        dependent_task=task_b,
        created_by=data["manager"],
    )
    TaskDependency.objects.create(
        prerequisite_task=task_b,
        dependent_task=task_c,
        created_by=data["manager"],
    )

    bottlenecks = get_bottlenecks(data["project"], threshold=2)

    assert len(bottlenecks) == 1
    assert bottlenecks[0]["task_id"] == task_a.id
    assert bottlenecks[0]["downstream_count"] == 2
    assert bottlenecks[0]["evidence"]["threshold"] == 2
@pytest.mark.django_db
def test_critical_path_returns_longest_incomplete_chain(task_test_data):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")
    task_c = create_test_task(data["project"], data["manager"], title="Task C")

    TaskDependency.objects.create(
        prerequisite_task=task_a,
        dependent_task=task_b,
        created_by=data["manager"],
    )
    TaskDependency.objects.create(
        prerequisite_task=task_b,
        dependent_task=task_c,
        created_by=data["manager"],
    )

    result = get_critical_path(data["project"])

    assert result["length"] == 3
    assert result["task_ids"] == [task_a.id, task_b.id, task_c.id]
@pytest.mark.django_db
def test_stale_blocker_uses_last_status_change_time(task_test_data):
    data = task_test_data
    task_a = create_test_task(data["project"], data["manager"], title="Task A")
    task_b = create_test_task(data["project"], data["manager"], title="Task B")

    TaskDependency.objects.create(
        prerequisite_task=task_a,
        dependent_task=task_b,
        created_by=data["manager"],
    )

    log = ActivityLog.objects.create(
        task=task_b,
        project=data["project"],
        actor=data["manager"],
        action=ActivityLog.Action.STATUS_CHANGED,
        detail={"from": "TODO", "to": "IN_PROGRESS"},
    )
    ActivityLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=6)
    )

    stale = get_stale_blockers(data["project"], days=5)

    assert len(stale) == 1
    assert stale[0]["task_id"] == task_b.id
    assert stale[0]["days_blocked"] >= 5
    assert stale[0]["evidence"]["threshold_days"] == 5


@pytest.mark.django_db
def test_overdue_and_due_soon_only_include_incomplete_tasks(task_test_data):
    data = task_test_data
    today = date.today()

    overdue_task = create_test_task(
        data["project"],
        data["manager"],
        title="Overdue",
        due_date=today - timedelta(days=1),
    )
    due_soon_task = create_test_task(
        data["project"],
        data["manager"],
        title="Due soon",
        due_date=today + timedelta(days=2),
    )
    later_task = create_test_task(
        data["project"],
        data["manager"],
        title="Due later",
        due_date=today + timedelta(days=5),
    )
    done_task = create_test_task(
        data["project"],
        data["manager"],
        title="Already done",
        status=Task.Status.DONE,
        due_date=today - timedelta(days=3),
    )

    result = get_overdue_and_due_soon(data["project"], due_soon_days=3)

    assert [task["id"] for task in result["overdue"]] == [overdue_task.id]
    assert [task["id"] for task in result["due_soon"]] == [due_soon_task.id]
    assert later_task.id not in [task["id"] for task in result["due_soon"]]
    assert done_task.id not in [task["id"] for task in result["overdue"]]


@pytest.mark.django_db
def test_workload_counts_only_assigned_incomplete_tasks(task_test_data):
    data = task_test_data
    create_test_task(
        data["project"], data["manager"], title="Active 1",
        assignee=data["member"],
    )
    create_test_task(
        data["project"], data["manager"], title="Active 2",
        assignee=data["member"],
    )
    create_test_task(
        data["project"], data["manager"], title="Completed",
        status=Task.Status.DONE, assignee=data["member"],
    )

    result = get_workload(data["project"])

    member_workload = next(
        row for row in result["workload"]
        if row["user_id"] == data["member"].id
    )
    assert member_workload["active_task_count"] == 2
    assert "not a measure of productivity" in result["disclaimer"]


@pytest.mark.django_db
def test_project_health_moves_from_healthy_to_attention_to_at_risk(
    task_test_data
):
    data = task_test_data
    today = date.today()

    assert get_project_health(data["project"])["health"] == "HEALTHY"

    create_test_task(
        data["project"],
        data["manager"],
        title="Overdue low priority",
        priority=Task.Priority.LOW,
        due_date=today - timedelta(days=1),
    )
    assert get_project_health(data["project"])["health"] == "NEEDS_ATTENTION"

    create_test_task(
        data["project"],
        data["manager"],
        title="Overdue high priority 1",
        priority=Task.Priority.HIGH,
        due_date=today - timedelta(days=2),
    )
    create_test_task(
        data["project"],
        data["manager"],
        title="Overdue critical priority 2",
        priority=Task.Priority.CRITICAL,
        due_date=today - timedelta(days=3),
    )

    at_risk = get_project_health(data["project"])
    assert at_risk["health"] == "AT_RISK"
    assert at_risk["evidence"]["overdue_critical_high_count"] == 2


@pytest.mark.django_db
def test_recommendations_include_evidence(task_test_data):
    data = task_test_data
    overdue_task = create_test_task(
        data["project"],
        data["manager"],
        title="Late critical task",
        priority=Task.Priority.CRITICAL,
        due_date=date.today() - timedelta(days=2),
    )

    recommendations = get_recommendations(data["project"])

    assert recommendations
    assert all("evidence" in recommendation for recommendation in recommendations)

    overdue_recommendation = next(
        recommendation for recommendation in recommendations
        if recommendation["type"] == "OVERDUE_HIGH_PRIORITY"
    )
    assert overdue_recommendation["evidence"]["task_id"] == overdue_task.id
    assert overdue_recommendation["evidence"]["days_overdue"] == 2


@pytest.mark.django_db
def test_project_summary_reports_task_and_finding_counts(task_test_data):
    data = task_test_data
    create_test_task(data["project"], data["manager"], title="Incomplete")
    create_test_task(
        data["project"],
        data["manager"],
        title="Complete",
        status=Task.Status.DONE,
    )

    summary = get_project_summary(data["project"])

    assert summary["health"] == "HEALTHY"
    assert summary["total_tasks"] == 2
    assert summary["done_tasks"] == 1
    assert summary["incomplete_tasks"] == 1
    assert summary["overdue_count"] == 0
    assert summary["bottleneck_count"] == 0
    assert summary["critical_path_length"] == 1
@pytest.mark.parametrize(
    "endpoint_suffix",
    [
        "insights/",
        "insights/bottlenecks/",
        "insights/critical-path/",
        "recommendations/",
    ],
)
@pytest.mark.django_db
def test_insight_endpoints_require_authentication(
    api_client, task_test_data, endpoint_suffix
):
    project = task_test_data["project"]

    response = api_client.get(
        f"/api/v1/projects/{project.id}/{endpoint_suffix}"
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "endpoint_suffix",
    [
        "insights/",
        "insights/bottlenecks/",
        "insights/critical-path/",
        "recommendations/",
    ],
)
@pytest.mark.django_db
def test_outsider_cannot_access_insight_endpoints(
    api_client, task_test_data, endpoint_suffix
):
    data = task_test_data
    api_client.force_authenticate(user=data["outsider"])

    response = api_client.get(
        f"/api/v1/projects/{data['project'].id}/{endpoint_suffix}"
    )

    assert response.status_code == 404
@pytest.mark.django_db
def test_graph_algorithms_handle_1000_task_chain(task_test_data):
    data = task_test_data
    task_count = 1000

    tasks = Task.objects.bulk_create([
        Task(
            project=data["project"],
            title=f"Chain task {index}",
            created_by=data["manager"],
        )
        for index in range(task_count)
    ])

    edges = [
        TaskDependency(
            prerequisite_task=tasks[index],
            dependent_task=tasks[index + 1],
            created_by=data["manager"],
        )
        for index in range(task_count - 1)
    ]
    TaskDependency.objects.bulk_create(edges)

    edge_ids = [
        (tasks[index].id, tasks[index + 1].id)
        for index in range(task_count - 1)
    ]

    assert downstream_impact(tasks[0].id, edge_ids) == task_count - 1

    critical_path = get_critical_path(data["project"])
    assert critical_path["length"] == task_count
    assert critical_path["task_ids"][0] == tasks[0].id
    assert critical_path["task_ids"][-1] == tasks[-1].id

    # Proposing last → first would close the existing chain into a cycle.
    assert has_cycle(tasks[-1].id, tasks[0].id) is True
@pytest.mark.django_db
def test_scenario_no_issues_means_healthy(task_test_data):
    project = task_test_data["project"]

    summary = get_project_summary(project)
    recommendations = get_recommendations(project)

    assert summary["health"] == "HEALTHY"
    assert summary["total_tasks"] == 0
    assert summary["bottleneck_count"] == 0
    assert recommendations == []


@pytest.mark.django_db
def test_scenario_one_task_blocks_six_others(task_test_data):
    data = task_test_data
    root = create_test_task(data["project"], data["manager"], title="Root task")
    downstream_tasks = [
        create_test_task(
            data["project"], data["manager"], title=f"Downstream {index}"
        )
        for index in range(6)
    ]

    for task in downstream_tasks:
        TaskDependency.objects.create(
            prerequisite_task=root,
            dependent_task=task,
            created_by=data["manager"],
        )

    bottlenecks = get_bottlenecks(data["project"])
    root_finding = next(item for item in bottlenecks if item["task_id"] == root.id)
    recommendation = next(
        item for item in get_recommendations(data["project"])
        if item["type"] == "BOTTLENECK"
    )

    assert root_finding["downstream_count"] == 6
    assert root_finding["evidence"]["downstream_task_count"] == 6
    assert recommendation["evidence"]["downstream_task_count"] == 6
    assert get_project_health(data["project"])["health"] == "NEEDS_ATTENTION"


@pytest.mark.django_db
def test_scenario_two_overdue_important_tasks_mean_at_risk(task_test_data):
    data = task_test_data
    today = date.today()

    task_a = create_test_task(
        data["project"],
        data["manager"],
        title="Overdue high",
        priority=Task.Priority.HIGH,
        due_date=today - timedelta(days=2),
    )
    task_b = create_test_task(
        data["project"],
        data["manager"],
        title="Overdue critical",
        priority=Task.Priority.CRITICAL,
        due_date=today - timedelta(days=4),
    )

    result = get_project_health(data["project"])

    assert result["health"] == "AT_RISK"
    assert result["evidence"]["overdue_critical_high_count"] == 2
    assert set(result["evidence"]["overdue_critical_high_ids"]) == {
        task_a.id, task_b.id
    }


@pytest.mark.django_db
def test_scenario_blocked_for_over_five_days_means_needs_attention(
    task_test_data
):
    data = task_test_data
    prerequisite = create_test_task(
        data["project"], data["manager"], title="Prerequisite"
    )
    blocked_task = create_test_task(
        data["project"], data["manager"], title="Blocked task"
    )
    TaskDependency.objects.create(
        prerequisite_task=prerequisite,
        dependent_task=blocked_task,
        created_by=data["manager"],
    )

    log = ActivityLog.objects.create(
        task=blocked_task,
        project=data["project"],
        actor=data["manager"],
        action=ActivityLog.Action.STATUS_CHANGED,
        detail={"from": "TODO", "to": "IN_PROGRESS"},
    )
    ActivityLog.objects.filter(pk=log.pk).update(
        created_at=timezone.now() - timedelta(days=6)
    )

    stale = get_stale_blockers(data["project"])
    result = get_project_health(data["project"])

    assert any(item["task_id"] == blocked_task.id for item in stale)
    assert result["health"] == "NEEDS_ATTENTION"


@pytest.mark.django_db
def test_scenario_critical_path_past_target_date_means_at_risk(
    task_test_data
):
    data = task_test_data
    project = data["project"]
    project.target_date = date.today() + timedelta(days=1)
    project.save(update_fields=["target_date"])

    tasks = [
        create_test_task(
            project, data["manager"], title=f"Critical path {index}"
        )
        for index in range(3)
    ]
    for index in range(len(tasks) - 1):
        TaskDependency.objects.create(
            prerequisite_task=tasks[index],
            dependent_task=tasks[index + 1],
            created_by=data["manager"],
        )

    result = get_project_health(project)

    assert result["health"] == "AT_RISK"
    assert result["evidence"]["critical_path_length"] == 3
    assert result["evidence"]["days_remaining"] == 1
