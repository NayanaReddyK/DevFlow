
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    
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
