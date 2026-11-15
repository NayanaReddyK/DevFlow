
import pytest

from rest_framework.test import APIClient

from users.models import User
from workspaces.models import WorkspaceMember
from workspaces.services import create_workspace

from .models import Project, ProjectMember


def make_user(username, email):
    return User.objects.create_user(
        username=username,
        email=email,
        password="StrongPass@123",
    )


def make_workspace(owner, name="Test Workspace"):
    return create_workspace(name=name, owner=owner)


def make_project(workspace, creator, name="Test Project"):
    return Project.objects.create(
        workspace=workspace,
        name=name,
        slug=name.lower().replace(" ", "-"),
        description="Test project description",
        created_by=creator,
    )


def add_project_member(project, user, role=ProjectMember.Role.MEMBER):
    return ProjectMember.objects.create(
        project=project,
        user=user,
        role=role,
    )


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_workspace_owner_can_create_project():
    owner = make_user("projectowner1", "projectowner1@example.com")
    workspace = make_workspace(owner)

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/projects/",
        {
            "name": "Backend API",
            "description": "Backend development",
        },
        format="json",
    )

    assert response.status_code == 201

    project = Project.objects.get(
        workspace=workspace,
        name="Backend API",
    )

    assert project.created_by == owner
    assert project.status == Project.Status.ACTIVE

    membership = ProjectMember.objects.get(
        project=project,
        user=owner,
    )

    assert membership.role == ProjectMember.Role.MANAGER


@pytest.mark.django_db
def test_workspace_admin_can_create_project():
    owner = make_user("projectowner2", "projectowner2@example.com")
    admin = make_user("projectadmin2", "projectadmin2@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=admin,
        role=WorkspaceMember.Role.ADMIN,
    )

    client = authenticated_client(admin)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/projects/",
        {"name": "Admin Project"},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_workspace_developer_cannot_create_project():
    owner = make_user("projectowner3", "projectowner3@example.com")
    developer = make_user("projectdev3", "projectdev3@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    client = authenticated_client(developer)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/projects/",
        {"name": "Unauthorized Project"},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_project_slug_is_unique_within_workspace():
    owner = make_user("projectowner4", "projectowner4@example.com")
    workspace = make_workspace(owner)

    client = authenticated_client(owner)

    first = client.post(
        f"/api/v1/workspaces/{workspace.slug}/projects/",
        {"name": "DevFlow API"},
        format="json",
    )

    second = client.post(
        f"/api/v1/workspaces/{workspace.slug}/projects/",
        {"name": "DevFlow API"},
        format="json",
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["slug"] != second.data["slug"]


@pytest.mark.django_db
def test_workspace_admin_can_list_all_workspace_projects():
    owner = make_user("projectowner5", "projectowner5@example.com")
    admin = make_user("projectadmin5", "projectadmin5@example.com")
    developer = make_user("projectdev5", "projectdev5@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=admin,
        role=WorkspaceMember.Role.ADMIN,
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    project = make_project(workspace, owner)

    # Admin is deliberately not a ProjectMember.
    client = authenticated_client(admin)

    response = client.get(
        f"/api/v1/workspaces/{workspace.slug}/projects/"
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == project.id


@pytest.mark.django_db
def test_project_member_can_list_their_projects():
    owner = make_user("projectowner6", "projectowner6@example.com")
    developer = make_user("projectdev6", "projectdev6@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    project = make_project(workspace, owner)
    add_project_member(project, developer)

    client = authenticated_client(developer)

    response = client.get(
        f"/api/v1/workspaces/{workspace.slug}/projects/"
    )

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["id"] == project.id


@pytest.mark.django_db
def test_workspace_developer_cannot_see_unassigned_projects():
    owner = make_user("projectowner7", "projectowner7@example.com")
    developer = make_user("projectdev7", "projectdev7@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    make_project(workspace, owner)

    client = authenticated_client(developer)

    response = client.get(
        f"/api/v1/workspaces/{workspace.slug}/projects/"
    )

    assert response.status_code == 200
    assert len(response.data) == 0


@pytest.mark.django_db
def test_project_member_can_retrieve_project():
    owner = make_user("projectowner8", "projectowner8@example.com")
    developer = make_user("projectdev8", "projectdev8@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    project = make_project(workspace, owner)
    add_project_member(project, developer)

    client = authenticated_client(developer)

    response = client.get(f"/api/v1/projects/{project.id}/")

    assert response.status_code == 200
    assert response.data["id"] == project.id


@pytest.mark.django_db
def test_non_member_cannot_retrieve_project():
    owner = make_user("projectowner9", "projectowner9@example.com")
    outsider = make_user("outsider9", "outsider9@example.com")

    workspace = make_workspace(owner)
    project = make_project(workspace, owner)

    client = authenticated_client(outsider)

    response = client.get(f"/api/v1/projects/{project.id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_project_manager_can_update_project():
    owner = make_user("projectowner10", "projectowner10@example.com")
    workspace = make_workspace(owner)
    project = make_project(workspace, owner)

    add_project_member(
        project,
        owner,
        ProjectMember.Role.MANAGER,
    )

    client = authenticated_client(owner)

    response = client.patch(
        f"/api/v1/projects/{project.id}/",
        {"description": "Updated description"},
        format="json",
    )

    assert response.status_code == 200

    project.refresh_from_db()
    assert project.description == "Updated description"


@pytest.mark.django_db
def test_project_member_cannot_update_project():
    owner = make_user("projectowner11", "projectowner11@example.com")
    developer = make_user("projectdev11", "projectdev11@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    project = make_project(workspace, owner)
    add_project_member(project, developer)

    client = authenticated_client(developer)

    response = client.patch(
        f"/api/v1/projects/{project.id}/",
        {"description": "Unauthorized update"},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_workspace_admin_can_delete_project():
    owner = make_user("projectowner12", "projectowner12@example.com")
    admin = make_user("projectadmin12", "projectadmin12@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=admin,
        role=WorkspaceMember.Role.ADMIN,
    )

    project = make_project(workspace, owner)

    client = authenticated_client(admin)

    response = client.delete(f"/api/v1/projects/{project.id}/")

    assert response.status_code == 204
    assert not Project.objects.filter(id=project.id).exists()


@pytest.mark.django_db
def test_project_manager_can_add_workspace_member():
    owner = make_user("projectowner13", "projectowner13@example.com")
    manager = make_user("projectmanager13", "projectmanager13@example.com")
    developer = make_user("projectdev13", "projectdev13@example.com")

    workspace = make_workspace(owner)

    for user in [manager, developer]:
        WorkspaceMember.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMember.Role.DEVELOPER,
        )

    project = make_project(workspace, owner)
    add_project_member(project, manager, ProjectMember.Role.MANAGER)

    client = authenticated_client(manager)

    response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {
            "email": developer.email,
            "role": "MEMBER",
        },
        format="json",
    )

    assert response.status_code == 201

    assert ProjectMember.objects.filter(
        project=project,
        user=developer,
        role=ProjectMember.Role.MEMBER,
    ).exists()


@pytest.mark.django_db
def test_project_manager_cannot_assign_another_manager():
    owner = make_user("projectowner14", "projectowner14@example.com")
    manager = make_user("projectmanager14", "projectmanager14@example.com")
    developer = make_user("projectdev14", "projectdev14@example.com")

    workspace = make_workspace(owner)

    for user in [manager, developer]:
        WorkspaceMember.objects.create(
            workspace=workspace,
            user=user,
            role=WorkspaceMember.Role.DEVELOPER,
        )

    project = make_project(workspace, owner)
    add_project_member(project, manager, ProjectMember.Role.MANAGER)

    client = authenticated_client(manager)

    response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {
            "email": developer.email,
            "role": "MANAGER",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_duplicate_project_membership_is_rejected():
    owner = make_user("projectowner15", "projectowner15@example.com")
    developer = make_user("projectdev15", "projectdev15@example.com")

    workspace = make_workspace(owner)

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER,
    )

    project = make_project(workspace, owner)
    add_project_member(project, developer)

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {"email": developer.email},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_user_from_another_workspace_cannot_be_added():
    owner = make_user("projectowner16", "projectowner16@example.com")
    outsider = make_user("outsider16", "outsider16@example.com")

    workspace = make_workspace(owner)
    other_workspace = make_workspace(
        outsider,
        name="Other Workspace",
    )

    project = make_project(workspace, owner)

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/projects/{project.id}/members/",
        {"email": outsider.email},
        format="json",
    )

    assert response.status_code == 400
    assert not ProjectMember.objects.filter(
        project=project,
        user=outsider,
    ).exists()


@pytest.mark.django_db
def test_project_creator_cannot_be_removed():
    owner = make_user("projectowner17", "projectowner17@example.com")
    workspace = make_workspace(owner)
    project = make_project(workspace, owner)

    add_project_member(project, owner, ProjectMember.Role.MANAGER)

    client = authenticated_client(owner)

    response = client.delete(
        f"/api/v1/projects/{project.id}/members/{owner.id}/"
    )

    assert response.status_code == 400
    assert ProjectMember.objects.filter(
        project=project,
        user=owner,
    ).exists()
@pytest.mark.django_db
def test_active_project_cannot_be_deleted():
    owner = make_user("activeowner", "activeowner@example.com")
    workspace = make_workspace(owner)
    project = make_project(workspace, owner)

    client = authenticated_client(owner)

    response = client.delete(
        f"/api/v1/projects/{project.id}/"
    )

    assert response.status_code == 409
    assert Project.objects.filter(id=project.id).exists()


@pytest.mark.django_db
def test_archived_project_with_tasks_cannot_be_deleted(
    django_user_model,
):
    from tasks.models import Task

    owner = make_user("archiveowner", "archiveowner@example.com")
    workspace = make_workspace(owner)
    project = make_project(workspace, owner)

    project.status = Project.Status.ARCHIVED
    project.save()

    Task.objects.create(
        project=project,
        title="Preserve this task",
        created_by=owner,
    )

    client = authenticated_client(owner)

    response = client.delete(
        f"/api/v1/projects/{project.id}/"
    )

    assert response.status_code == 409
    assert Project.objects.filter(id=project.id).exists()
    assert Task.objects.filter(project=project).exists()


@pytest.mark.django_db
def test_archived_empty_project_can_be_deleted():
    owner = make_user("emptyowner", "emptyowner@example.com")
    workspace = make_workspace(owner)
    project = make_project(workspace, owner)

    project.status = Project.Status.ARCHIVED
    project.save()

    client = authenticated_client(owner)

    response = client.delete(
        f"/api/v1/projects/{project.id}/"
    )

    assert response.status_code == 204
    assert not Project.objects.filter(id=project.id).exists()


@pytest.mark.django_db
def test_cancelled_project_cannot_be_reactivated():
    owner = make_user("cancelowner", "cancelowner@example.com")
    workspace = make_workspace(owner)
    project = make_project(workspace, owner)

    project.status = Project.Status.CANCELLED
    project.save()

    client = authenticated_client(owner)

    response = client.patch(
        f"/api/v1/projects/{project.id}/",
        {"status": "ACTIVE"},
        format="json",
    )

    assert response.status_code == 400

    project.refresh_from_db()
    assert project.status == Project.Status.CANCELLED