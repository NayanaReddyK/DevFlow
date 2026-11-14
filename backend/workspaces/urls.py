

from django.urls import path

from .views import (
    WorkspaceListCreateView,
    WorkspaceDetailView,
    WorkspaceMemberListCreateView,
    WorkspaceMemberDetailView,
    WorkspaceInvitationListCreateView,
    WorkspaceInvitationAcceptView,
)

urlpatterns = [
    path("", WorkspaceListCreateView.as_view(), name="workspace-list-create"),

    path(
        "<slug:slug>/",
        WorkspaceDetailView.as_view(),
        name="workspace-detail",
    ),

    path(
        "<slug:slug>/members/",
        WorkspaceMemberListCreateView.as_view(),
        name="workspace-member-list-create",
    ),

    path(
        "<slug:slug>/members/<int:user_id>/",
        WorkspaceMemberDetailView.as_view(),
        name="workspace-member-detail",
    ),

    path(
        "<slug:slug>/invitations/",
        WorkspaceInvitationListCreateView.as_view(),
        name="workspace-invitations",
    ),

    path(
        "invitations/accept/",
        WorkspaceInvitationAcceptView.as_view(),
        name="workspace-invitation-accept",
    ),
]

