
from django.urls import path

from .views import (
    WorkspaceProjectListCreateView,
    ProjectDetailView,
    ProjectMemberListCreateView,
    ProjectMemberDetailView,
)

urlpatterns = [
    path(
        "workspaces/<slug:workspace_slug>/projects/",
        WorkspaceProjectListCreateView.as_view(),
        name="workspace-project-list-create",
    ),
    path(
        "projects/<int:pk>/",
        ProjectDetailView.as_view(),
        name="project-detail",
    ),
    path(
        "projects/<int:project_id>/members/",
        ProjectMemberListCreateView.as_view(),
        name="project-member-list-create",
    ),
    path(
        "projects/<int:project_id>/members/<int:user_id>/",
        ProjectMemberDetailView.as_view(),
        name="project-member-detail",
    ),
]
