
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import WorkspaceMember


class WorkspaceRolePermission(BasePermission):

    def has_object_permission(self, request, view, obj):

        membership = obj.memberships.filter(
            user=request.user
        ).only("role").first()

        if membership is None:
            return False

        if request.method in SAFE_METHODS:
            return True

        if request.method in ["PUT", "PATCH"]:
            return membership.role in [
                WorkspaceMember.Role.OWNER,
                WorkspaceMember.Role.ADMIN,
            ]

        if request.method == "DELETE":
            return membership.role == WorkspaceMember.Role.OWNER

        return False
