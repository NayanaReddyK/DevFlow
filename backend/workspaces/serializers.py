from rest_framework import serializers
from .models import Workspace, WorkspaceMember, WorkspaceInvitation
from .services import create_workspace


class WorkspaceCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Workspace
        fields = [
            "id",
            "name",
            "slug",
            "owner",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "slug",
            "owner",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        return create_workspace(
            name=validated_data["name"],
            owner=self.context["request"].user
        )


class WorkspaceListSerializer(serializers.ModelSerializer):

    role = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = [
            "id",
            "name",
            "slug",
            "role",
            "created_at",
        ]

    def get_role(self, obj):
        user = self.context["request"].user

        membership = obj.memberships.filter(
            user=user
        ).first()

        return membership.role if membership else None
class WorkspaceUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Workspace
        fields = ["name"]

class WorkspaceMemberSerializer(serializers.ModelSerializer):

    user_id = serializers.IntegerField(
        source="user.id",
        read_only=True
    )

    username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    class Meta:
        model = WorkspaceMember
        fields = [
            "user_id",
            "username",
            "email",
            "role",
            "joined_at",
        ]

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class WorkspaceMemberAddSerializer(serializers.Serializer):

    email = serializers.EmailField()

    role = serializers.ChoiceField(
        choices=WorkspaceMember.Role.choices,
        default=WorkspaceMember.Role.DEVELOPER
    )

    def validate(self, attrs):
        workspace = self.context["workspace"]
        actor_role = self.context["actor_role"]

        user = User.objects.filter(
            email__iexact=attrs["email"]
        ).first()

        if user is None:
            raise serializers.ValidationError({
                "email": "No registered user found with this email."
            })

        if workspace.memberships.filter(user=user).exists():
            raise serializers.ValidationError({
                "email": "This user is already a workspace member."
            })

        if attrs["role"] == WorkspaceMember.Role.OWNER:
            raise serializers.ValidationError({
                "role": "Owner membership cannot be assigned this way."
            })

        if (
            actor_role == WorkspaceMember.Role.ADMIN
            and attrs["role"] != WorkspaceMember.Role.DEVELOPER
        ):
            raise serializers.ValidationError({
                "role": "Admins can only add Developers."
            })

        attrs["user"] = user
        return attrs

    def create(self, validated_data):
        return WorkspaceMember.objects.create(
            workspace=self.context["workspace"],
            user=validated_data["user"],
            role=validated_data["role"]
        )


class WorkspaceMemberRoleUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = WorkspaceMember
        fields = ["role"]

    def validate_role(self, value):
        if value == WorkspaceMember.Role.OWNER:
            raise serializers.ValidationError(
                "Owner role cannot be assigned through this endpoint."
            )

        return value

from .services import create_workspace_invitation


class WorkspaceInvitationSerializer(serializers.ModelSerializer):

    class Meta:
        model = WorkspaceInvitation
        fields = [
            "id",
            "email",
            "role",
            "created_at",
            "expires_at",
            "accepted_at",
        ]
        read_only_fields = fields


class WorkspaceInvitationCreateSerializer(serializers.Serializer):

    email = serializers.EmailField()

    role = serializers.ChoiceField(
        choices=WorkspaceMember.Role.choices,
        default=WorkspaceMember.Role.DEVELOPER
    )

    def validate(self, attrs):
        workspace = self.context["workspace"]
        actor_role = self.context["actor_role"]

        attrs["email"] = attrs["email"].strip().lower()

        if attrs["role"] == WorkspaceMember.Role.OWNER:
            raise serializers.ValidationError({
                "role": "Owner cannot be assigned through invitations."
            })

        if (
            actor_role == WorkspaceMember.Role.ADMIN
            and attrs["role"] != WorkspaceMember.Role.DEVELOPER
        ):
            raise serializers.ValidationError({
                "role": "Admins can only invite Developers."
            })

        return attrs

    def create(self, validated_data):
        return create_workspace_invitation(
            workspace=self.context["workspace"],
            email=validated_data["email"],
            role=validated_data["role"],
            invited_by=self.context["request"].user
        )


class WorkspaceInvitationAcceptSerializer(serializers.Serializer):

    token = serializers.CharField(write_only=True)
