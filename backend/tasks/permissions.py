
from rest_framework.permissions import BasePermission, SAFE_METHODS

from projects.models import ProjectMember
from workspaces.models import WorkspaceMember

from projects.models import Project


class TaskPermission(BasePermission):
    """
    Read:
        Project members and workspace Owners/Admins.

    Update:
        Workspace Owners/Admins, Project Managers,
        task creators and task assignees who remain project members.

    Delete:
        Workspace Owners/Admins and Project Managers.

    Archived projects:
        Read-only.
    """

    def _is_workspace_admin(self, user, project):
        return WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
            role__in=[
                WorkspaceMember.Role.OWNER,
                WorkspaceMember.Role.ADMIN,
            ],
        ).exists()

    def _is_project_manager(self, user, project):
        return ProjectMember.objects.filter(
            project=project,
            user=user,
            role=ProjectMember.Role.MANAGER,
        ).exists()

    def _is_project_member(self, user, project):
        return ProjectMember.objects.filter(
            project=project,
            user=user,
        ).exists()

    def has_object_permission(self, request, view, obj):
        user = request.user
        project = obj.project

        is_admin = self._is_workspace_admin(user, project)
        is_manager = self._is_project_manager(user, project)
        is_member = self._is_project_member(user, project)

        if request.method in SAFE_METHODS:
            return is_admin or is_member

        # Archived projects are read-only for everyone.
        if project.status != Project.Status.ACTIVE:
            return False

        if request.method in ("PUT", "PATCH"):
            return (
                is_admin
                or is_manager
                or obj.created_by_id == user.id
                or obj.assignee_id == user.id
            ) and (is_admin or is_member)

        if request.method == "DELETE":
            return is_admin or is_manager

        return False
