
from django.conf import settings
from django.db import models


class Task(models.Model):
    labels = models.ManyToManyField(
    "tasks.TaskLabel",
    blank=True,
    related_name="tasks",
    )
    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "TODO",
                        "IN_PROGRESS",
                        "IN_REVIEW",
                        "DONE",
                    ]
                ),
                name="task_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    priority__in=[
                        "LOW",
                        "MEDIUM",
                        "HIGH",
                        "CRITICAL",
                    ]
                ),
                name="task_priority_valid",
            ),
        ]
        
    class Status(models.TextChoices):
        TODO = "TODO", "To Do"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        IN_REVIEW = "IN_REVIEW", "In Review"
        DONE = "DONE", "Done"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="tasks",
    )

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tasks",
    )

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )

    due_date = models.DateField(null=True, blank=True)

    estimate = models.PositiveIntegerField(null=True, blank=True, help_text="Estimated effort in story points.")
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:
            old = Task.objects.filter(pk=self.pk).values("status").first()
            if old:
                if old["status"] != self.Status.DONE and self.status == self.Status.DONE:
                    from django.utils import timezone
                    self.completed_at = timezone.now()
                elif old["status"] == self.Status.DONE and self.status != self.Status.DONE:
                    self.completed_at = None
        elif self.status == self.Status.DONE:
            from django.utils import timezone
            self.completed_at = timezone.now()
        super().save(*args, **kwargs)

    @property
    def is_blocked(self):
        return self.prerequisites.filter(
            prerequisite_task__status__in=[
                self.Status.TODO,
                self.Status.IN_PROGRESS,
                self.Status.IN_REVIEW,
            ]
        ).exists()

    def __str__(self):
        return f"{self.title} ({self.project.name})"

class TaskLabel(models.Model):
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="task_labels",
    )

    name = models.CharField(max_length=50)

    color = models.CharField(
        max_length=7,
        default="#64748b",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_task_labels",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                models.functions.Lower("name"),
                "project",
                name="unique_task_label_name_per_project",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.project.name})"


class ActivityLog(models.Model):
    class Action(models.TextChoices):
        CREATED = "CREATED", "Created"
        STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"
        ASSIGNED = "ASSIGNED", "Assigned"
        PRIORITY_CHANGED = "PRIORITY_CHANGED", "Priority Changed"
        DEPENDENCY_ADDED = "DEPENDENCY_ADDED", "Dependency Added"
        DEPENDENCY_REMOVED = "DEPENDENCY_REMOVED", "Dependency Removed"
        COMMENTED = "COMMENTED", "Commented"

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="activity_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="activity_logs",
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task", "created_at"]),
            models.Index(fields=["project", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} on {self.task} by {self.actor}"


class TaskDependency(models.Model):
    """
    Finish-to-Start dependency: `dependent_task` cannot start until
    `prerequisite_task` is DONE.
    """
    prerequisite_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="dependents",
    )
    dependent_task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="prerequisites",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_dependencies",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["prerequisite_task", "dependent_task"],
                name="unique_task_dependency",
            )
        ]
        indexes = [
            models.Index(fields=["dependent_task"]),
            models.Index(fields=["prerequisite_task"]),
        ]

    def __str__(self):
        return f"{self.prerequisite_task} → {self.dependent_task}"
