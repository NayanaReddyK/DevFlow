
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Workspace, WorkspaceMember, WorkspaceInvitation
from .permissions import WorkspaceRolePermission



from .services import accept_workspace_invitation
from .serializers import (
    WorkspaceCreateSerializer,
    WorkspaceListSerializer,
    WorkspaceUpdateSerializer,
    WorkspaceMemberSerializer,
    WorkspaceMemberAddSerializer,
    WorkspaceMemberRoleUpdateSerializer,
    WorkspaceInvitationSerializer,
    WorkspaceInvitationCreateSerializer,
    WorkspaceInvitationAcceptSerializer,
)

User = get_user_model()


class WorkspaceListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Workspace.objects.filter(
            members=self.request.user
        ).distinct()

    def get_serializer_class(self):
        if self.request.method == "POST":
            return WorkspaceCreateSerializer

        return WorkspaceListSerializer


class WorkspaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [
        IsAuthenticated,
        WorkspaceRolePermission,
    ]
    lookup_field = "slug"

    def get_queryset(self):
        return Workspace.objects.filter(
            members=self.request.user
        ).distinct()

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return WorkspaceUpdateSerializer

        return WorkspaceListSerializer


class WorkspaceMemberBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def get_workspace(self, slug):
        return get_object_or_404(
            Workspace.objects.filter(
                members=self.request.user
            ).distinct(),
            slug=slug
        )

    def get_actor_membership(self, workspace):
        return get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=self.request.user
        )


class WorkspaceMemberListCreateView(WorkspaceMemberBaseView):

    def get(self, request, slug):
        workspace = self.get_workspace(slug)

        members = WorkspaceMember.objects.filter(
            workspace=workspace
        ).select_related("user").order_by("joined_at")

        serializer = WorkspaceMemberSerializer(
            members,
            many=True
        )

        return Response(serializer.data)

    def post(self, request, slug):
        workspace = self.get_workspace(slug)
        actor = self.get_actor_membership(workspace)

        if actor.role not in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]:
            return Response(
                {"detail": "You do not have permission to add members."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = WorkspaceMemberAddSerializer(
            data=request.data,
            context={
                "workspace": workspace,
                "actor_role": actor.role,
            }
        )

        serializer.is_valid(raise_exception=True)
        membership = serializer.save()

        return Response(
            WorkspaceMemberSerializer(membership).data,
            status=status.HTTP_201_CREATED
        )


class WorkspaceMemberDetailView(WorkspaceMemberBaseView):

    def patch(self, request, slug, user_id):
        workspace = self.get_workspace(slug)
        actor = self.get_actor_membership(workspace)

        if actor.role not in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]:
            return Response(
                {"detail": "You cannot manage workspace members."},
                status=status.HTTP_403_FORBIDDEN
            )

        target = get_object_or_404(
            WorkspaceMember.objects.select_related("user"),
            workspace=workspace,
            user_id=user_id
        )

        if target.role == WorkspaceMember.Role.OWNER:
            return Response(
                {"detail": "The workspace owner cannot be modified."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = WorkspaceMemberRoleUpdateSerializer(
            target,
            data=request.data,
            partial=True
        )

        serializer.is_valid(raise_exception=True)

        new_role = serializer.validated_data.get(
            "role",
            target.role
        )

        if actor.role == WorkspaceMember.Role.ADMIN:
            if (
                target.role != WorkspaceMember.Role.DEVELOPER
                or new_role != WorkspaceMember.Role.DEVELOPER
            ):
                return Response(
                    {"detail": "Admins can only manage Developers."},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer.save()

        return Response(
            WorkspaceMemberSerializer(target).data,
            status=status.HTTP_200_OK
        )

    def delete(self, request, slug, user_id):
        workspace = self.get_workspace(slug)
        actor = self.get_actor_membership(workspace)

        if actor.role not in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]:
            return Response(
                {"detail": "You cannot remove workspace members."},
                status=status.HTTP_403_FORBIDDEN
            )

        target = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user_id=user_id
        )

        if target.role == WorkspaceMember.Role.OWNER:
            return Response(
                {"detail": "The workspace owner cannot be removed."},
                status=status.HTTP_403_FORBIDDEN
            )

        if (
            actor.role == WorkspaceMember.Role.ADMIN
            and target.role != WorkspaceMember.Role.DEVELOPER
        ):
            return Response(
                {"detail": "Admins can only remove Developers."},
                status=status.HTTP_403_FORBIDDEN
            )

        target.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceInvitationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get_workspace(self, slug, user):
        return get_object_or_404(
            Workspace.objects.filter(members=user),
            slug=slug
        )

    def get(self, request, slug):
        workspace = self.get_workspace(slug, request.user)

        invitations = WorkspaceInvitation.objects.filter(
            workspace=workspace,
            accepted_at__isnull=True
        ).order_by("-created_at")

        serializer = WorkspaceInvitationSerializer(
            invitations,
            many=True
        )

        return Response(serializer.data)

    def post(self, request, slug):
        workspace = self.get_workspace(slug, request.user)

        membership = get_object_or_404(
            WorkspaceMember,
            workspace=workspace,
            user=request.user
        )

        if membership.role not in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]:
            return Response(
                {"detail": "You cannot invite members."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = WorkspaceInvitationCreateSerializer(
            data=request.data,
            context={
                "workspace": workspace,
                "actor_role": membership.role,
                "request": request,
            }
        )

        serializer.is_valid(raise_exception=True)

        try:
            invitation = serializer.save()
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            WorkspaceInvitationSerializer(invitation).data,
            status=status.HTTP_201_CREATED
        )


class WorkspaceInvitationAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WorkspaceInvitationAcceptSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        try:
            membership = accept_workspace_invitation(
                token=serializer.validated_data["token"],
                user=request.user
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            WorkspaceMemberSerializer(membership).data,
            status=status.HTTP_201_CREATED
        )
