
from django.urls import path

from .views import (
    WorkspaceProjectListCreateView,
    ProjectDetailView,
    ProjectMemberListCreateView,
    ProjectMemberDetailView,
    ProjectInsightSummaryView,
    ProjectInsightBottlenecksView,
    ProjectInsightCriticalPathView,
    ProjectRecommendationsView,
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
    path("projects/<int:project_id>/insights/", ProjectInsightSummaryView.as_view(), name="project-insight-summary"),
    path("projects/<int:project_id>/insights/bottlenecks/", ProjectInsightBottlenecksView.as_view(), name="project-insight-bottlenecks"),
    path("projects/<int:project_id>/insights/critical-path/", ProjectInsightCriticalPathView.as_view(), name="project-insight-critical-path"),
    path("projects/<int:project_id>/recommendations/", ProjectRecommendationsView.as_view(), name="project-recommendations"),
]
