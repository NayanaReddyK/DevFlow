from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db.models.deletion import ProtectedError

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from workspaces.models import Workspace, WorkspaceMember

from .models import Project, ProjectMember
from .serializers import (
    ProjectCreateSerializer,
    ProjectListSerializer,
    ProjectUpdateSerializer,
    ProjectMemberSerializer,
    ProjectMemberAddSerializer,
    ProjectMemberRoleSerializer,
)
from .permissions import ProjectPermission
from tasks.insights import (
    get_project_summary,
    get_bottlenecks,
    get_stale_blockers,
    get_critical_path,
    get_recommendations,
    get_workload,
)


class WorkspaceProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    
                  
    def get_workspace(self):
        return get_object_or_404(
            Workspace.objects.filter(members=self.request.user).distinct(),
            slug=self.kwargs["workspace_slug"],
        )
    def get_queryset(self):
        workspace = self.get_workspace()

        return Project.objects.filter(
            Q(memberships__user=self.request.user)
            | Q(
                workspace__memberships__user=self.request.user,
                workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            ),
            workspace=workspace,
        ).select_related(
            "workspace", "created_by"
        ).distinct()



    def get_serializer_class(self):
        if self.request.method == "POST":
            return ProjectCreateSerializer
        return ProjectListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["workspace"] = self.get_workspace()
        return context

    def create(self, request, *args, **kwargs):
        workspace = self.get_workspace()

        membership = WorkspaceMember.objects.filter(
            workspace=workspace,
            user=request.user,
        ).first()

        if membership.role not in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]:
            return Response(
                {"detail": "Only workspace owners and admins can create projects."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = serializer.save()

        return Response(
            ProjectListSerializer(
                project,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, ProjectPermission]
    
    def get_queryset(self):
        return Project.objects.filter(
            Q(memberships__user=self.request.user)
            | Q(
                workspace__memberships__user=self.request.user,
                workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        ).select_related(
            "workspace", "created_by"
        ).distinct()
    def destroy(self, request, *args, **kwargs):
        project = self.get_object()

        is_workspace_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=request.user,
            role=WorkspaceMember.Role.ADMIN,
        ).exists()

        if not is_workspace_admin and project.status != Project.Status.ARCHIVED:
            return Response(
                {"detail": "Only archived projects can be permanently deleted."},
                status=status.HTTP_409_CONFLICT,
            )

        if project.tasks.exists():
            return Response(
                {
                    "detail": (
                        "Projects containing tasks cannot be deleted. "
                        "Preserve the project history by keeping it archived."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        try:
            project.delete()
        except ProtectedError:
            return Response(
                {"detail": "This project contains protected records and cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return ProjectUpdateSerializer
        return ProjectListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context

    def retrieve(self, request, *args, **kwargs):
        project = self.get_object()
        return Response(
            ProjectListSerializer(
                project, context=self.get_serializer_context()
            ).data
        )


class ProjectMemberBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self):
        return get_object_or_404(
            Project.objects.filter(
                workspace__members=self.request.user
            ).distinct(),
            pk=self.kwargs["project_id"],
        )

    def get_workspace_role(self, project):
        return WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=self.request.user,
        ).values_list("role", flat=True).first()

    def can_manage(self, project):
        workspace_role = self.get_workspace_role(project)

        if workspace_role in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]:
            return True

        return ProjectMember.objects.filter(
            project=project,
            user=self.request.user,
            role=ProjectMember.Role.MANAGER,
        ).exists()


class ProjectMemberListCreateView(ProjectMemberBaseView):

    def get(self, request, project_id):
        project = self.get_project()

        if not ProjectMember.objects.filter(
            project=project, user=request.user
        ).exists() and self.get_workspace_role(project) not in [
            WorkspaceMember.Role.OWNER,
            WorkspaceMember.Role.ADMIN,
        ]:
            return Response(
                {"detail": "You do not have access to this project."},
                status=status.HTTP_403_FORBIDDEN,
            )

        members = project.memberships.select_related("user").order_by(
            "joined_at"
        )

        return Response(ProjectMemberSerializer(members, many=True).data)

    def post(self, request, project_id):
        project = self.get_project()

        if not self.can_manage(project):
            return Response(
                {"detail": "You cannot manage this project's members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ProjectMemberAddSerializer(
            data=request.data,
            context={"project": project, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        member = serializer.save()

        return Response(
            ProjectMemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )


class ProjectMemberDetailView(ProjectMemberBaseView):

    def patch(self, request, project_id, user_id):
        project = self.get_project()

        if not self.can_manage(project):
            return Response(
                {"detail": "You cannot manage this project's members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = get_object_or_404(
            ProjectMember,
            project=project,
            user_id=user_id,
        )

        if member.user_id == project.created_by_id:
            return Response(
                {"detail": "The project creator cannot be demoted or removed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ProjectMemberRoleSerializer(
            member,
            data=request.data,
            partial=True,
            context={"project": project, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(ProjectMemberSerializer(member).data)
    
    def delete(self, request, project_id, user_id):
        project = self.get_project()

        if not self.can_manage(project):
            return Response(
                {"detail": "You cannot manage this project's members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = get_object_or_404(
            ProjectMember,
            project=project,
            user_id=user_id,
        )

        if member.user_id == project.created_by_id:
            return Response(
                {"detail": "The project creator cannot be removed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectInsightBaseView(APIView):
    permission_classes = [IsAuthenticated]

    def get_project(self):
        user = self.request.user
        accessible = Project.objects.filter(
            Q(memberships__user=user)
            | Q(
                workspace__memberships__user=user,
                workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        ).distinct()
        return get_object_or_404(accessible, pk=self.kwargs["project_id"])


class ProjectInsightSummaryView(ProjectInsightBaseView):
    def get(self, request, project_id):
        project = self.get_project()
        summary = get_project_summary(project)
        workload = get_workload(project)
        return Response({**summary, "workload": workload})


class ProjectInsightBottlenecksView(ProjectInsightBaseView):
    def get(self, request, project_id):
        project = self.get_project()
        return Response({
            "bottlenecks": get_bottlenecks(project),
            "stale_blockers": get_stale_blockers(project),
        })


class ProjectInsightCriticalPathView(ProjectInsightBaseView):
    def get(self, request, project_id):
        project = self.get_project()
        cp = get_critical_path(project)
        # Enrich with task titles
        from tasks.models import Task
        task_map = {
            t["id"]: t
            for t in Task.objects.filter(
                id__in=cp["task_ids"]
            ).values("id", "title", "status", "priority", "due_date")
        }
        ordered_tasks = [task_map[tid] for tid in cp["task_ids"] if tid in task_map]
        for t in ordered_tasks:
            if t["due_date"]:
                t["due_date"] = t["due_date"].isoformat()
        return Response({
            "length": cp["length"],
            "evidence": cp["evidence"],
            "tasks": ordered_tasks,
        })


class ProjectRecommendationsView(ProjectInsightBaseView):
    def get(self, request, project_id):
        project = self.get_project()
        return Response({
            "recommendations": get_recommendations(project),
        })