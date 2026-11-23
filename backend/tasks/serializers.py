
from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Task, TaskLabel, TaskDependency
from projects.models import ProjectMember

from .services import create_task


User = get_user_model()

class ProjectScopedLabelsMixin:
    

    def get_fields(self):
        fields = super().get_fields()
        project = self.context.get("project")
        

        if project is None and self.instance is not None:
            project = self.instance.project

        if project is not None:
            fields["labels"].child_relation.queryset = TaskLabel.objects.filter(
                project=project
            )
        return fields

class TaskCreateSerializer(
    ProjectScopedLabelsMixin,
    serializers.ModelSerializer
    ):
    labels = serializers.PrimaryKeyRelatedField(
    queryset=TaskLabel.objects.none(),
    many=True,
    required=False,
    )

    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "priority",
            "assignee",
            "due_date",
            "labels"
        ]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Task title cannot be empty."
            )
        return value.strip()

    def validate_assignee(self, assignee):
        if assignee is None:
            return assignee

        project = self.context["project"]

        is_project_member = ProjectMember.objects.filter(
            project=project,
            user=assignee,
        ).exists()

        if not is_project_member:
            raise serializers.ValidationError(
                "The assigned user must be a member of this project."
            )

        return assignee

    def create(self, validated_data):
        project = self.context["project"]
        request = self.context["request"]
        labels = validated_data.pop("labels", [])
        return create_task(
            project=project,
            creator=request.user,
            labels=labels,
            **validated_data,
        )


class TaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(
        source="project.name",
        read_only=True,
    )

    created_by_username = serializers.CharField(
        source="created_by.username",
        read_only=True,
    )

    assignee_username = serializers.CharField(
        source="assignee.username",
        read_only=True,
        allow_null=True,
    )
    labels = serializers.PrimaryKeyRelatedField(
    many=True,
    read_only=True,
    )

    is_blocked = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "project",
            "project_name",
            "title",
            "description",
            "status",
            "priority",
            "created_by",
            "created_by_username",
            "assignee",
            "assignee_username",
            "due_date",
            "estimate",
            "completed_at",
            "created_at",
            "updated_at",
            "labels",
            "is_blocked",
        ]
        read_only_fields = fields


class TaskUpdateSerializer(
    ProjectScopedLabelsMixin,
    serializers.ModelSerializer
    ):
    labels = serializers.PrimaryKeyRelatedField(
        queryset=TaskLabel.objects.none(),
        many=True,
        required=False,
    )

    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "due_date",
            "estimate",
            "labels"
        ]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "Task title cannot be empty."
            )
        return value.strip()

    def validate_assignee(self, assignee):
        if assignee is None:
            return assignee

        project = self.instance.project

        is_project_member = ProjectMember.objects.filter(
            project=project,
            user=assignee,
        ).exists()

        if not is_project_member:
            raise serializers.ValidationError(
                "The assigned user must be a member of this project."
            )

        return assignee

class TaskFilterSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=Task.Status.choices,
        required=False,
    )

    priority = serializers.ChoiceField(
        choices=Task.Priority.choices,
        required=False,
    )

    assignee = serializers.CharField(
        required=False,
        max_length=20,
    )

    search = serializers.CharField(
        required=False,
        max_length=200,
        allow_blank=False,
    )
    label = serializers.IntegerField(
    required=False,
    min_value=1,
    )

    def validate_assignee(self, value):
        value = value.strip()

        if value.lower() == "unassigned":
            return "unassigned"

        if not value.isdigit():
            raise serializers.ValidationError(
                "Assignee must be a valid user ID or 'unassigned'."
            )

        return int(value)

    def validate(self, attrs):
        allowed = {"status", "priority", "assignee", "search", "page", "page_size", "label"}
        unknown = set(self.initial_data.keys()) - allowed

        if unknown:
            raise serializers.ValidationError({
                "query_params": (
                    f"Unsupported filter parameter(s): {', '.join(sorted(unknown))}"
                )
            })

        return attrs

class TaskLabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskLabel
        fields = [
            "id",
            "project",
            "name",
            "color",
            "created_by",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "project",
            "created_by",
            "created_at",
        ]

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Label name cannot be empty."
            )

        project = (
            self.instance.project
            if self.instance
            else self.context["project"]
        )

        existing_labels = TaskLabel.objects.filter(
            project=project,
            name__iexact=value,
        )

        if self.instance:
            existing_labels = existing_labels.exclude(
                pk=self.instance.pk
            )

        if existing_labels.exists():
            raise serializers.ValidationError(
                "A label with this name already exists in this project."
            )

        return value

    def validate_color(self, value):
        import re

        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
            raise serializers.ValidationError(
                "Color must be a valid hexadecimal color, such as #64748b."
            )

        return value


class TaskDependencySerializer(serializers.ModelSerializer):
    prerequisite_task_id = serializers.IntegerField(source="prerequisite_task.id", read_only=True)
    prerequisite_task_title = serializers.CharField(source="prerequisite_task.title", read_only=True)
    prerequisite_task_status = serializers.CharField(source="prerequisite_task.status", read_only=True)
    dependent_task_id = serializers.IntegerField(source="dependent_task.id", read_only=True)
    dependent_task_title = serializers.CharField(source="dependent_task.title", read_only=True)

    class Meta:
        model = TaskDependency
        fields = [
            "id",
            "prerequisite_task_id",
            "prerequisite_task_title",
            "prerequisite_task_status",
            "dependent_task_id",
            "dependent_task_title",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class AddDependencySerializer(serializers.Serializer):
    prerequisite_task_id = serializers.IntegerField()

    def validate_prerequisite_task_id(self, value):
        from .models import Task
        try:
            task = Task.objects.get(pk=value)
        except Task.DoesNotExist:
            raise serializers.ValidationError("Task not found.")
        self.context["prerequisite_task"] = task
        return value

    def validate(self, attrs):
        from .models import TaskDependency
        from .services import has_cycle

        dependent_task = self.context["dependent_task"]
        prerequisite_task = self.context["prerequisite_task"]

        # Must be same project
        if prerequisite_task.project_id != dependent_task.project_id:
            raise serializers.ValidationError(
                "Dependencies must be within the same project."
            )

        # Self-dependency
        if prerequisite_task.pk == dependent_task.pk:
            raise serializers.ValidationError(
                "A task cannot depend on itself."
            )

        # Already exists
        if TaskDependency.objects.filter(
            prerequisite_task=prerequisite_task,
            dependent_task=dependent_task,
        ).exists():
            raise serializers.ValidationError(
                "This dependency already exists."
            )

        # Cycle check
        if has_cycle(prerequisite_task.pk, dependent_task.pk):
            raise serializers.ValidationError(
                "Adding this dependency would create a cycle."
            )

        return attrs
