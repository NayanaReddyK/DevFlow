
from rest_framework import serializers

from users.models import User
from workspaces.models import WorkspaceMember
from .models import Project, ProjectMember
from .services import create_project


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id", "name", "slug", "description",
            "status", "workspace", "created_by",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "slug", "status", "workspace",
            "created_by", "created_at", "updated_at",
        ]

    def create(self, validated_data):
        workspace = self.context["workspace"]
        creator = self.context["request"].user

        return create_project(
            workspace=workspace,
            name=validated_data["name"],
            description=validated_data.get("description", ""),
            creator=creator,
        )


class ProjectListSerializer(serializers.ModelSerializer):
    workspace_name = serializers.CharField(
        source="workspace.name", read_only=True
    )
    workspace_slug = serializers.SlugField(
        source="workspace.slug", read_only=True
    )
    role = serializers.SerializerMethodField()
    workspace_role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "name", "slug", "description",
            "status", "workspace_name", "workspace_slug", "role", "created_at",
            "start_date", "target_date", "workspace_role",
        ]

    def get_role(self, obj):
        membership = obj.memberships.filter(
            user=self.context["request"].user
        ).first()

        return membership.role if membership else None

    def get_workspace_role(self, obj):
        membership = obj.workspace.memberships.filter(
            user=self.context["request"].user
        ).only("role").first()
        return membership.role if membership else None


class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["name", "description", "status", "start_date", "target_date"]

    def validate_status(self, value):
        project = self.instance

        if (
            project.status == Project.Status.CANCELLED
            and value != Project.Status.CANCELLED
        ):
            raise serializers.ValidationError(
                "A cancelled project cannot be reactivated."
            )

        return value


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = ProjectMember
        fields = ["user_id", "username", "email", "role", "joined_at"]
        read_only_fields = fields


class ProjectMemberAddSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=ProjectMember.Role.choices,
        default=ProjectMember.Role.MEMBER,
    )

    def validate_email(self, value):
        try:
            user = User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "No registered user exists with this email."
            )

        project = self.context["project"]

        if not WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=user,
        ).exists():
            raise serializers.ValidationError(
                "User must belong to the project workspace first."
            )

        if ProjectMember.objects.filter(
            project=project,
            user=user,
        ).exists():
            raise serializers.ValidationError(
                "User is already a project member."
            )

        self.user = user
        return value

    def validate(self, attrs):
        actor = self.context["request"].user
        project = self.context["project"]

        actor_workspace_role = WorkspaceMember.objects.filter(
            workspace=project.workspace,
            user=actor,
        ).values_list("role", flat=True).first()

        if (
            attrs["role"] == ProjectMember.Role.MANAGER
            and actor_workspace_role not in [
                WorkspaceMember.Role.OWNER,
                WorkspaceMember.Role.ADMIN,
            ]
        ):
            raise serializers.ValidationError(
                "Only workspace owners and admins can assign managers."
            )

        return attrs

    def create(self, validated_data):
        return ProjectMember.objects.create(
            project=self.context["project"],
            user=self.user,
            role=validated_data["role"],
        )


class ProjectMemberRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectMember
        fields = ["role"]

    def validate_role(self, value):
        project = self.context["project"]
        actor = self.context["request"].user

        if value == ProjectMember.Role.MANAGER:
            is_workspace_admin = WorkspaceMember.objects.filter(
                workspace=project.workspace,
                user=actor,
                role__in=[
                    WorkspaceMember.Role.OWNER,
                    WorkspaceMember.Role.ADMIN,
                ],
            ).exists()

            if not is_workspace_admin:
                raise serializers.ValidationError(
                    "Only workspace owners and admins can assign managers."
                )

        return value
