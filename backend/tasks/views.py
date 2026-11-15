
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from projects.models import Project
from workspaces.models import WorkspaceMember

from .models import Task, TaskLabel
from .permissions import TaskPermission
from .serializers import (
    TaskCreateSerializer,
    TaskFilterSerializer,
    TaskSerializer,
    TaskUpdateSerializer,
    TaskLabelSerializer,
)



class TaskPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def paginate_queryset(self, queryset, request, view=None):
        page = request.query_params.get(self.page_query_param)

        if page is not None:
            if not page.isdigit() or int(page) < 1:
                raise ValidationError({
                    "page": "Page must be a positive integer."
                })

        return super().paginate_queryset(queryset, request, view)

    def get_page_size(self, request):
        value = request.query_params.get(self.page_size_query_param)

        if value is None:
            return self.page_size

        if not value.isdigit() or int(value) < 1:
            raise ValidationError({
                "page_size": "Page size must be a positive integer."
            })

        return min(int(value), self.max_page_size)


class ProjectTaskListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    pagination_class = TaskPagination

    def get_project(self):
        user = self.request.user

        accessible_projects = Project.objects.filter(
            Q(memberships__user=user)
            | Q(
                workspace__memberships__user=user,
                workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        )

        return get_object_or_404(
            accessible_projects.distinct(),
            pk=self.kwargs["project_id"],
        )

    def get_queryset(self):
        project = self.get_project()

        queryset = Task.objects.filter(
            project=project
        ).select_related(
            "project",
            "created_by",
            "assignee",
        ).prefetch_related("labels")

        filter_serializer = TaskFilterSerializer(
            data=self.request.query_params
        )
        filter_serializer.is_valid(raise_exception=True)

        filters = filter_serializer.validated_data

        if "status" in filters:
            queryset = queryset.filter(status=filters["status"])

        if "priority" in filters:
            queryset = queryset.filter(priority=filters["priority"])

        if "assignee" in filters:
            assignee = filters["assignee"]

            if assignee == "unassigned":
                queryset = queryset.filter(assignee__isnull=True)
            else:
                queryset = queryset.filter(assignee_id=assignee)

        if "search" in filters:
            queryset = queryset.filter(
                title__icontains=filters["search"].strip()
            )
        if "label" in filters:
                    queryset = queryset.filter(
                        labels__id=filters["label"]
                    ).distinct()

        return queryset
        

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TaskCreateSerializer

        return TaskSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_project()
        return context

    def perform_create(self, serializer):
        project = self.get_project()

        if project.status != Project.Status.ACTIVE:
            raise PermissionDenied(
                "Tasks cannot be created in an active projects."
            )

        serializer.save()


class TaskDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [
        IsAuthenticated,
        TaskPermission,
    ]

    queryset = Task.objects.select_related(
        "project",
        "created_by",
        "assignee",
    ).prefetch_related("labels")

    def get_queryset(self):
        user = self.request.user

        return Task.objects.filter(
            Q(project__memberships__user=user)
            | Q(
                project__workspace__memberships__user=user,
                project__workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        ).select_related(
            "project",
            "created_by",
            "assignee",
        ).distinct()

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return TaskUpdateSerializer

        return TaskSerializer

class ProjectLabelListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskLabelSerializer

    def get_project(self):
        user = self.request.user

        accessible_projects = Project.objects.filter(
            Q(memberships__user=user)
            | Q(
                workspace__memberships__user=user,
                workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        )

        return get_object_or_404(
            accessible_projects.distinct(),
            pk=self.kwargs["project_id"],
        )

    def get_queryset(self):
        project = self.get_project()

        return TaskLabel.objects.filter(
            project=project
        ).select_related("project", "created_by")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["project"] = self.get_project()
        return context

    def perform_create(self, serializer):
        project = self.get_project()
        user = self.request.user

        is_manager = project.memberships.filter(
            user=user,
            role="MANAGER",
        ).exists()

        is_workspace_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
            role__in=[
                WorkspaceMember.Role.OWNER,
                WorkspaceMember.Role.ADMIN,
            ],
        ).exists()

        if project.status != Project.Status.ACTIVE:
            raise PermissionDenied(
                "Labels cannot be created in an inactive project."
            )

        if not (is_manager or is_workspace_admin):
            raise PermissionDenied(
                "Only project managers and workspace admins can create labels."
            )

        serializer.save(
            project=project,
            created_by=user,
        )


class TaskLabelDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskLabelSerializer

    def get_queryset(self):
        user = self.request.user

        return TaskLabel.objects.filter(
            Q(project__memberships__user=user)
            | Q(
                project__workspace__memberships__user=user,
                project__workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        ).select_related(
            "project",
            "created_by",
        ).distinct()

    def _can_manage_label(self, label):
        user = self.request.user
        project = label.project

        is_manager = project.memberships.filter(
            user=user,
            role="MANAGER",
        ).exists()

        is_workspace_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
            role__in=[
                WorkspaceMember.Role.OWNER,
                WorkspaceMember.Role.ADMIN,
            ],
        ).exists()

        if project.status != Project.Status.ACTIVE:
            return False

        return is_manager or is_workspace_admin

    def update(self, request, *args, **kwargs):
        label = self.get_object()

        if not self._can_manage_label(label):
            raise PermissionDenied(
                "You do not have permission to update this label."
            )

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        label = self.get_object()

        if not self._can_manage_label(label):
            raise PermissionDenied(
                "You do not have permission to delete this label."
            )

        return super().destroy(request, *args, **kwargs)
