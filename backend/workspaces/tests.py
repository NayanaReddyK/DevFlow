import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from .models import Workspace, WorkspaceMember
from unittest.mock import patch
from .services import create_workspace
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
User = get_user_model()

def authenticated_client(user):
    refresh = RefreshToken.for_user(user)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )
    return client
@pytest.mark.django_db
def test_workspace_creation():
    owner = User.objects.create_user(
        username="workspaceowner",
        email="owner@example.com",
        password="StrongPass@123"
    )

    workspace = Workspace.objects.create(
        name="DevFlow Engineering",
        slug="devflow-engineering",
        owner=owner
    )

    assert workspace.name == "DevFlow Engineering"
    assert workspace.owner == owner
    assert workspace.slug == "devflow-engineering"


@pytest.mark.django_db
def test_workspace_member_relationship():
    owner = User.objects.create_user(
        username="owner",
        email="owner@example.com",
        password="StrongPass@123"
    )

    developer = User.objects.create_user(
        username="developer",
        email="developer@example.com",
        password="StrongPass@123"
    )

    workspace = Workspace.objects.create(
        name="DevFlow",
        slug="devflow",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=owner,
        role=WorkspaceMember.Role.OWNER
    )

    workspace.members.add(
        developer,
        through_defaults={
            "role": WorkspaceMember.Role.DEVELOPER
        }
    )

    assert developer in workspace.members.all()
    assert workspace in developer.workspaces.all()


@pytest.mark.django_db
def test_duplicate_workspace_membership_is_rejected():
    owner = User.objects.create_user(
        username="owner",
        email="owner@example.com",
        password="StrongPass@123"
    )

    workspace = Workspace.objects.create(
        name="DevFlow",
        slug="devflow",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=owner,
        role=WorkspaceMember.Role.OWNER
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            WorkspaceMember.objects.create(
                workspace=workspace,
                user=owner,
                role=WorkspaceMember.Role.DEVELOPER
            )

@pytest.mark.django_db
def test_workspace_creation_adds_owner_as_member():
    owner = User.objects.create_user(
        username="serviceowner",
        email="serviceowner@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="DevFlow Engineering",
        owner=owner
    )

    membership = WorkspaceMember.objects.get(
        workspace=workspace,
        user=owner
    )

    assert membership.role == WorkspaceMember.Role.OWNER
    assert owner in workspace.members.all()


@pytest.mark.django_db
def test_workspace_slug_is_unique():
    owner1 = User.objects.create_user(
        username="owner1",
        email="owner1@example.com",
        password="StrongPass@123"
    )

    owner2 = User.objects.create_user(
        username="owner2",
        email="owner2@example.com",
        password="StrongPass@123"
    )

    workspace1 = create_workspace(
        name="Engineering",
        owner=owner1
    )

    workspace2 = create_workspace(
        name="Engineering",
        owner=owner2
    )

    assert workspace1.slug == "engineering"
    assert workspace2.slug == "engineering-2"


@pytest.mark.django_db
def test_workspace_creation_rolls_back_on_membership_failure():
    owner = User.objects.create_user(
        username="rollbackowner",
        email="rollback@example.com",
        password="StrongPass@123"
    )

    with patch(
        "workspaces.services.WorkspaceMember.objects.create",
        side_effect=RuntimeError("Simulated membership failure")
    ):
        with pytest.raises(RuntimeError):
            create_workspace(
                name="Rollback Test",
                owner=owner
            )

    assert not Workspace.objects.filter(
        slug="rollback-test"
    ).exists()

@pytest.mark.django_db
def test_unauthenticated_user_cannot_create_workspace():
    client = APIClient()

    response = client.post(
        "/api/v1/workspaces/",
        {"name": "Unauthorized Workspace"},
        format="json"
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_authenticated_user_can_create_workspace():
    user = User.objects.create_user(
        username="apiuser",
        email="apiuser@example.com",
        password="StrongPass@123"
    )

    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {access}"
    )

    response = client.post(
        "/api/v1/workspaces/",
        {"name": "DevFlow Engineering"},
        format="json"
    )

    assert response.status_code == 201
    assert response.data["name"] == "DevFlow Engineering"
    assert response.data["slug"] == "devflow-engineering"

    membership = WorkspaceMember.objects.get(
        workspace_id=response.data["id"],
        user=user
    )

    assert membership.role == WorkspaceMember.Role.OWNER

@pytest.mark.django_db
def test_user_can_list_own_workspaces():
    user = User.objects.create_user(
        username="listuser",
        email="listuser@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="My Engineering Team",
        owner=user
    )

    refresh = RefreshToken.for_user(user)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    response = client.get("/api/v1/workspaces/")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["name"] == workspace.name
    assert response.data[0]["role"] == WorkspaceMember.Role.OWNER


@pytest.mark.django_db
def test_user_cannot_see_another_users_workspace():
    user1 = User.objects.create_user(
        username="userone",
        email="userone@example.com",
        password="StrongPass@123"
    )

    user2 = User.objects.create_user(
        username="usertwo",
        email="usertwo@example.com",
        password="StrongPass@123"
    )

    create_workspace(
        name="User One Workspace",
        owner=user1
    )

    create_workspace(
        name="User Two Workspace",
        owner=user2
    )

    refresh = RefreshToken.for_user(user1)
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    response = client.get("/api/v1/workspaces/")

    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["name"] == "User One Workspace"

@pytest.mark.django_db
def test_user_can_retrieve_own_workspace():
    user = User.objects.create_user(
        username="detailuser",
        email="detailuser@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="My Engineering Team",
        owner=user
    )

    refresh = RefreshToken.for_user(user)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace.slug}/"
    )

    assert response.status_code == 200
    assert response.data["name"] == workspace.name
    assert response.data["slug"] == workspace.slug
    assert response.data["role"] == WorkspaceMember.Role.OWNER


@pytest.mark.django_db
def test_user_cannot_retrieve_non_member_workspace():
    owner = User.objects.create_user(
        username="workspaceowner",
        email="workspaceowner@example.com",
        password="StrongPass@123"
    )

    outsider = User.objects.create_user(
        username="outsider",
        email="outsider@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Private Engineering Team",
        owner=owner
    )

    refresh = RefreshToken.for_user(outsider)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    response = client.get(
        f"/api/v1/workspaces/{workspace.slug}/"
    )

    assert response.status_code == 404

@pytest.mark.django_db
def test_workspace_owner_can_update_workspace():
    owner = User.objects.create_user(
        username="updateowner",
        email="updateowner@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Original Name",
        owner=owner
    )

    refresh = RefreshToken.for_user(owner)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    response = client.patch(
        f"/api/v1/workspaces/{workspace.slug}/",
        {"name": "Updated Name"},
        format="json"
    )

    assert response.status_code == 200

    workspace.refresh_from_db()
    assert workspace.name == "Updated Name"


@pytest.mark.django_db
def test_admin_can_update_but_not_delete_workspace():
    owner = User.objects.create_user(
        username="adminowner",
        email="adminowner@example.com",
        password="StrongPass@123"
    )

    admin = User.objects.create_user(
        username="workspaceadmin",
        email="workspaceadmin@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Admin Test Workspace",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=admin,
        role=WorkspaceMember.Role.ADMIN
    )

    refresh = RefreshToken.for_user(admin)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    update_response = client.patch(
        f"/api/v1/workspaces/{workspace.slug}/",
        {"name": "Admin Updated Workspace"},
        format="json"
    )

    assert update_response.status_code == 200

    delete_response = client.delete(
        f"/api/v1/workspaces/{workspace.slug}/"
    )

    assert delete_response.status_code == 403


@pytest.mark.django_db
def test_developer_cannot_update_workspace():
    owner = User.objects.create_user(
        username="developerowner",
        email="developerowner@example.com",
        password="StrongPass@123"
    )

    developer = User.objects.create_user(
        username="workspace developer",
        email="developer@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Developer Test Workspace",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER
    )

    refresh = RefreshToken.for_user(developer)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    response = client.patch(
        f"/api/v1/workspaces/{workspace.slug}/",
        {"name": "Unauthorized Change"},
        format="json"
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_workspace_owner_can_delete_workspace():
    owner = User.objects.create_user(
        username="deleteowner",
        email="deleteowner@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Workspace To Delete",
        owner=owner
    )

    refresh = RefreshToken.for_user(owner)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}"
    )

    response = client.delete(
        f"/api/v1/workspaces/{workspace.slug}/"
    )

    assert response.status_code == 204
    assert not Workspace.objects.filter(
        pk=workspace.pk
    ).exists()

@pytest.mark.django_db
def test_owner_can_add_existing_user():
    owner = User.objects.create_user(
        username="memberowner",
        email="memberowner@example.com",
        password="StrongPass@123"
    )
    new_user = User.objects.create_user(
        username="newmember",
        email="newmember@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Member Test",
        owner=owner
    )

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/members/",
        {
            "email": new_user.email,
            "role": "DEVELOPER"
        },
        format="json"
    )

    assert response.status_code == 201

    membership = WorkspaceMember.objects.get(
        workspace=workspace,
        user=new_user
    )
    assert membership.role == WorkspaceMember.Role.DEVELOPER


@pytest.mark.django_db
def test_duplicate_member_addition_is_rejected():
    owner = User.objects.create_user(
        username="duplicateowner",
        email="duplicateowner@example.com",
        password="StrongPass@123"
    )
    member = User.objects.create_user(
        username="existingmember",
        email="existingmember@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Duplicate Test",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=member,
        role=WorkspaceMember.Role.DEVELOPER
    )

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/members/",
        {"email": member.email},
        format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_admin_can_add_developer_but_not_admin():
    owner = User.objects.create_user(
        username="roleowner",
        email="roleowner@example.com",
        password="StrongPass@123"
    )
    admin = User.objects.create_user(
        username="roleadmin",
        email="roleadmin@example.com",
        password="StrongPass@123"
    )
    developer = User.objects.create_user(
        username="roledeveloper",
        email="roledeveloper@example.com",
        password="StrongPass@123"
    )
    another_admin = User.objects.create_user(
        username="anotheradmin",
        email="anotheradmin@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Admin Permission Test",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=admin,
        role=WorkspaceMember.Role.ADMIN
    )

    client = authenticated_client(admin)

    allowed = client.post(
        f"/api/v1/workspaces/{workspace.slug}/members/",
        {"email": developer.email, "role": "DEVELOPER"},
        format="json"
    )

    denied = client.post(
        f"/api/v1/workspaces/{workspace.slug}/members/",
        {"email": another_admin.email, "role": "ADMIN"},
        format="json"
    )

    assert allowed.status_code == 201
    assert denied.status_code == 400


@pytest.mark.django_db
def test_owner_can_change_member_role():
    owner = User.objects.create_user(
        username="changeowner",
        email="changeowner@example.com",
        password="StrongPass@123"
    )
    member = User.objects.create_user(
        username="changemember",
        email="changemember@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Role Change Test",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=member,
        role=WorkspaceMember.Role.DEVELOPER
    )

    client = authenticated_client(owner)

    response = client.patch(
        f"/api/v1/workspaces/{workspace.slug}/members/{member.id}/",
        {"role": "ADMIN"},
        format="json"
    )

    assert response.status_code == 200

    membership = WorkspaceMember.objects.get(
        workspace=workspace,
        user=member
    )
    assert membership.role == WorkspaceMember.Role.ADMIN


@pytest.mark.django_db
def test_workspace_owner_cannot_be_removed_or_demoted():
    owner = User.objects.create_user(
        username="protectedowner",
        email="protectedowner@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Owner Protection Test",
        owner=owner
    )

    client = authenticated_client(owner)

    url = (
        f"/api/v1/workspaces/{workspace.slug}"
        f"/members/{owner.id}/"
    )

    patch_response = client.patch(
        url,
        {"role": "DEVELOPER"},
        format="json"
    )

    delete_response = client.delete(url)

    assert patch_response.status_code == 403
    assert delete_response.status_code == 403

    assert WorkspaceMember.objects.filter(
        workspace=workspace,
        user=owner,
        role=WorkspaceMember.Role.OWNER
    ).exists()


@pytest.mark.django_db
def test_workspace_member_can_list_members():
    owner = User.objects.create_user(
        username="listowner",
        email="listowner@example.com",
        password="StrongPass@123"
    )
    developer = User.objects.create_user(
        username="listdeveloper",
        email="listdeveloper@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Member Listing Test",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=developer,
        role=WorkspaceMember.Role.DEVELOPER
    )

    client = authenticated_client(developer)

    response = client.get(
        f"/api/v1/workspaces/{workspace.slug}/members/"
    )

    assert response.status_code == 200
    assert len(response.data) == 2

from datetime import timedelta

from django.core import mail
from django.test import override_settings
from django.utils import timezone


@pytest.mark.django_db
@override_settings(
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend"
        }
    }
)

def test_owner_can_send_workspace_invitation():
    owner = User.objects.create_user(
        username="inviteowner",
        email="inviteowner@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Invitation Test",
        owner=owner
    )

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/invitations/",
        {
            "email": "newdeveloper@example.com",
            "role": "DEVELOPER"
        },
        format="json"
    )

    assert response.status_code == 201
    assert len(mail.outbox) == 1
    assert "newdeveloper@example.com" in mail.outbox[0].to


@pytest.mark.django_db
@override_settings(
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend"
        }
    }
)

def test_admin_cannot_invite_another_admin():
    owner = User.objects.create_user(
        username="invitationowner",
        email="invitationowner@example.com",
        password="StrongPass@123"
    )

    admin = User.objects.create_user(
        username="invitationadmin",
        email="invitationadmin@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Admin Invitation Test",
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=admin,
        role=WorkspaceMember.Role.ADMIN
    )

    client = authenticated_client(admin)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/invitations/",
        {
            "email": "anotheradmin@example.com",
            "role": "ADMIN"
        },
        format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
@override_settings(
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend"
        }
    }
)
def test_invited_user_can_accept_invitation():
    owner = User.objects.create_user(
        username="acceptowner",
        email="acceptowner@example.com",
        password="StrongPass@123"
    )

    recipient = User.objects.create_user(
        username="inviteduser",
        email="invited@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Invitation Acceptance Test",
        owner=owner
    )

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/invitations/",
        {
            "email": recipient.email,
            "role": "DEVELOPER"
        },
        format="json"
    )

    assert response.status_code == 201

    token = mail.outbox[-1].body.split(
        "Token: ", 1
    )[1].splitlines()[0].strip()

    recipient_client = authenticated_client(recipient)

    accept_response = recipient_client.post(
        "/api/v1/workspaces/invitations/accept/",
        {"token": token},
        format="json"
    )

    assert accept_response.status_code == 201

    assert WorkspaceMember.objects.filter(
        workspace=workspace,
        user=recipient,
        role=WorkspaceMember.Role.DEVELOPER
    ).exists()


@pytest.mark.django_db
@override_settings(
    MAILERS={
        "default": {
            "BACKEND": "django.core.mail.backends.locmem.EmailBackend"
        }
    }
)
def test_expired_invitation_cannot_be_accepted():
    from .models import WorkspaceInvitation

    owner = User.objects.create_user(
        username="expiredowner",
        email="expiredowner@example.com",
        password="StrongPass@123"
    )

    recipient = User.objects.create_user(
        username="expireduser",
        email="expireduser@example.com",
        password="StrongPass@123"
    )

    workspace = create_workspace(
        name="Expired Invitation Test",
        owner=owner
    )

    client = authenticated_client(owner)

    response = client.post(
        f"/api/v1/workspaces/{workspace.slug}/invitations/",
        {
            "email": recipient.email,
            "role": "DEVELOPER"
        },
        format="json"
    )

    assert response.status_code == 201

    token = mail.outbox[-1].body.split(
        "Token: ", 1
    )[1].splitlines()[0].strip()

    WorkspaceInvitation.objects.filter(
        workspace=workspace,
        email=recipient.email
    ).update(
        expires_at=timezone.now() - timedelta(days=1)
    )

    recipient_client = authenticated_client(recipient)

    accept_response = recipient_client.post(
        "/api/v1/workspaces/invitations/accept/",
        {"token": token},
        format="json"
    )

    assert accept_response.status_code == 400
    assert not WorkspaceMember.objects.filter(
        workspace=workspace,
        user=recipient
    ).exists()
