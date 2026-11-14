
from django.db import transaction
from django.utils.text import slugify

from .models import Workspace, WorkspaceMember


@transaction.atomic
def create_workspace(*, name, owner):

    base_slug = slugify(name)

    if not base_slug:
        raise ValueError("Workspace name must contain valid characters.")

    slug = base_slug
    counter = 2

    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    workspace = Workspace.objects.create(
        name=name,
        slug=slug,
        owner=owner
    )

    WorkspaceMember.objects.create(
        workspace=workspace,
        user=owner,
        role=WorkspaceMember.Role.OWNER
    )

    return workspace

import hashlib
import secrets
from datetime import timedelta

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import WorkspaceInvitation, WorkspaceMember


@transaction.atomic
def create_workspace_invitation(*, workspace, email, role, invited_by):

    email = email.strip().lower()

    if workspace.memberships.filter(
        user__email__iexact=email
    ).exists():
        raise ValueError("This user is already a workspace member.")

    if WorkspaceInvitation.objects.filter(
        workspace=workspace,
        email__iexact=email,
        accepted_at__isnull=True,
        expires_at__gt=timezone.now()
    ).exists():
        raise ValueError("An active invitation already exists.")

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(
        raw_token.encode()
    ).hexdigest()

    invitation = WorkspaceInvitation.objects.create(
        workspace=workspace,
        email=email,
        role=role,
        invited_by=invited_by,
        token_hash=token_hash,
        expires_at=timezone.now() + timedelta(days=7)
    )

    send_mail(
        subject=f"Invitation to join {workspace.name} on DevFlow",
        message=(
            f"You have been invited to join {workspace.name}.\n\n"
            f"Your assigned role: {role}\n\n"
            f"Your invitation expires in 7 days.\n\n"
            f"Accept your invitation using this token:\n"
            f"Token: {raw_token}\n\n"
            f"POST this token to /api/v1/workspaces/invitations/accept/"
        ),
        from_email=None,
        recipient_list=[email],
        fail_silently=False
    )

    return invitation


@transaction.atomic
def accept_workspace_invitation(*, token, user):

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    invitation = (
        WorkspaceInvitation.objects
        .select_for_update()
        .filter(token_hash=token_hash)
        .first()
    )

    if invitation is None:
        raise ValueError("Invalid invitation token.")

    if invitation.accepted_at is not None:
        raise ValueError("This invitation has already been accepted.")

    if invitation.expires_at <= timezone.now():
        raise ValueError("This invitation has expired.")

    if invitation.email.casefold() != user.email.casefold():
        raise ValueError(
            "This invitation belongs to a different email address."
        )

    if invitation.workspace.memberships.filter(user=user).exists():
        raise ValueError("You are already a workspace member.")

    membership = WorkspaceMember.objects.create(
        workspace=invitation.workspace,
        user=user,
        role=invitation.role
    )

    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])

    return membership
