
from rest_framework.permissions import BasePermission, SAFE_METHODS

from workspaces.models import WorkspaceMember
from .models import ProjectMember


class ProjectPermission(BasePermission):

    def has_object_permission(self, request, view, obj):
        workspace_role = WorkspaceMember.objects.filter(
            workspace=obj.workspace,
            user=request.user,
        ).values_list("role", flat=True).first()

        if workspace_role is None:
            return False

        is_workspace_admin = workspace_role in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]

        project_membership = ProjectMember.objects.filter(
            project=obj,
            user=request.user,
        ).first()

        if request.method in SAFE_METHODS:
            return is_workspace_admin or project_membership is not None

        if request.method == "DELETE":
            return is_workspace_admin

        return (
            is_workspace_admin
            or (
                project_membership is not None
                and project_membership.role == ProjectMember.Role.MANAGER
            )
        )
