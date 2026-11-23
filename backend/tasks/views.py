
from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from projects.models import Project
from workspaces.models import WorkspaceMember

from .models import Task, TaskLabel, TaskDependency, ActivityLog
from .permissions import TaskPermission
from .serializers import (
    TaskCreateSerializer,
    TaskFilterSerializer,
    TaskSerializer,
    TaskUpdateSerializer,
    TaskLabelSerializer,
    TaskDependencySerializer,
    AddDependencySerializer,
)
from .services import create_task, log_activity



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

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data.get("status")
        warnings = []
        if new_status == Task.Status.IN_PROGRESS and instance.is_blocked:
            warnings.append("This task is blocked by incomplete prerequisites.")

        # Log status change
        if new_status and new_status != instance.status:
            log_activity(
                task=instance,
                actor=request.user,
                action=ActivityLog.Action.STATUS_CHANGED,
                detail={"from": instance.status, "to": new_status},
            )

        self.perform_update(serializer)
        response_data = TaskSerializer(instance, context=self.get_serializer_context()).data
        if warnings:
            response_data["warnings"] = warnings
        return Response(response_data)

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


class TaskDependencyListCreateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_task(self):
        user = self.request.user
        accessible = Task.objects.filter(
            Q(project__memberships__user=user)
            | Q(
                project__workspace__memberships__user=user,
                project__workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        ).distinct()
        return get_object_or_404(accessible, pk=self.kwargs["task_pk"])

    def _can_manage(self, task):
        user = self.request.user
        project = task.project
        is_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
            role__in=[WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN],
        ).exists()
        from projects.models import ProjectMember
        is_manager = ProjectMember.objects.filter(
            project=project, user=user, role=ProjectMember.Role.MANAGER
        ).exists()
        return is_admin or is_manager

    def get(self, request, task_pk):
        task = self.get_task()
        prerequisites = TaskDependency.objects.filter(
            dependent_task=task
        ).select_related("prerequisite_task", "dependent_task", "created_by")
        dependents = TaskDependency.objects.filter(
            prerequisite_task=task
        ).select_related("prerequisite_task", "dependent_task", "created_by")
        return Response({
            "prerequisites": TaskDependencySerializer(prerequisites, many=True).data,
            "dependents": TaskDependencySerializer(dependents, many=True).data,
        })

    def post(self, request, task_pk):
        task = self.get_task()
        if not self._can_manage(task):
            raise PermissionDenied("Only project managers and workspace admins can add dependencies.")
        if task.project.status != "ACTIVE":
            raise PermissionDenied("Cannot add dependencies to tasks in an inactive project.")

        serializer = AddDependencySerializer(
            data=request.data,
            context={"request": request, "dependent_task": task},
        )
        serializer.is_valid(raise_exception=True)
        prerequisite_task = serializer.context["prerequisite_task"]

        dep = TaskDependency.objects.create(
            prerequisite_task=prerequisite_task,
            dependent_task=task,
            created_by=request.user,
        )
        log_activity(
            task=task,
            actor=request.user,
            action=ActivityLog.Action.DEPENDENCY_ADDED,
            detail={"prerequisite_task_id": prerequisite_task.pk, "prerequisite_task_title": prerequisite_task.title},
        )
        return Response(TaskDependencySerializer(dep).data, status=status.HTTP_201_CREATED)


class TaskDependencyDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get_task(self):
        user = self.request.user
        accessible = Task.objects.filter(
            Q(project__memberships__user=user)
            | Q(
                project__workspace__memberships__user=user,
                project__workspace__memberships__role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            )
        ).distinct()
        return get_object_or_404(accessible, pk=self.kwargs["task_pk"])

    def _can_manage(self, task):
        user = self.request.user
        project = task.project
        is_admin = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
            role__in=[WorkspaceMember.Role.OWNER, WorkspaceMember.Role.ADMIN],
        ).exists()
        from projects.models import ProjectMember
        is_manager = ProjectMember.objects.filter(
            project=project, user=user, role=ProjectMember.Role.MANAGER
        ).exists()
        return is_admin or is_manager

    def delete(self, request, task_pk, dep_id):
        task = self.get_task()
        if not self._can_manage(task):
            raise PermissionDenied("Only project managers and workspace admins can remove dependencies.")
        dep = get_object_or_404(TaskDependency, pk=dep_id, dependent_task=task)
        prereq_title = dep.prerequisite_task.title
        prereq_id = dep.prerequisite_task.pk
        dep.delete()
        log_activity(
            task=task,
            actor=request.user,
            action=ActivityLog.Action.DEPENDENCY_REMOVED,
            detail={"prerequisite_task_id": prereq_id, "prerequisite_task_title": prereq_title},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
