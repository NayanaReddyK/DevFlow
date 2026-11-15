from django.urls import path
from .views import (
    ProjectTaskListCreateView,
    TaskDetailView,
    ProjectLabelListCreateView,
    TaskLabelDetailView,
)
urlpatterns = [
    path(
        "projects/<int:project_id>/tasks/",
        ProjectTaskListCreateView.as_view(),
        name="project-task-list-create",
    ),
    path(
        "tasks/<int:pk>/",
        TaskDetailView.as_view(),
        name="task-detail",
    ),
    path(
        "projects/<int:project_id>/labels/",
        ProjectLabelListCreateView.as_view(),
        name="project-label-list-create",
        ),
    path(
        "labels/<int:pk>/",
        TaskLabelDetailView.as_view(),
        name="task-label-detail",
    ),
]
