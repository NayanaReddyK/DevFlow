
import pytest

from rest_framework.test import APIClient

from projects.models import Project, ProjectMember
from tasks.models import Task, TaskLabel
from workspaces.models import Workspace, WorkspaceMember


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
