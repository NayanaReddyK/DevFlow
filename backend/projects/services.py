
from django.db import transaction
from django.utils.text import slugify

from .models import Project, ProjectMember


@transaction.atomic
def create_project(*, workspace, name, description, creator):

    if not workspace.memberships.filter(user=creator).exists():
        raise ValueError(
            "You must be a workspace member to create a project."
        )

    base_slug = slugify(name)

    if not base_slug:
        raise ValueError("Project name must contain valid characters.")

    slug = base_slug
    counter = 2

    while Project.objects.filter(
        workspace=workspace,
        slug=slug,
    ).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    project = Project.objects.create(
        workspace=workspace,
        name=name,
        slug=slug,
        description=description,
        created_by=creator,
    )

    ProjectMember.objects.create(
        project=project,
        user=creator,
        role=ProjectMember.Role.MANAGER,
    )

    return project
