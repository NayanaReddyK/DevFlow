import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0004_tasklabel_task_labels_and_more"),
        ("projects", "0003_project_start_date_target_date"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- Task new fields ---
        migrations.AddField(
            model_name="task",
            name="estimate",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text="Estimated effort in story points.",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        # --- ActivityLog ---
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("STATUS_CHANGED", "Status Changed"),
                            ("ASSIGNED", "Assigned"),
                            ("PRIORITY_CHANGED", "Priority Changed"),
                            ("DEPENDENCY_ADDED", "Dependency Added"),
                            ("DEPENDENCY_REMOVED", "Dependency Removed"),
                            ("COMMENTED", "Commented"),
                        ],
                        max_length=30,
                    ),
                ),
                ("detail", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_logs",
                        to="projects.project",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="activity_logs",
                        to="tasks.task",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["task", "created_at"], name="tasks_activ_task_id_idx"),
        ),
        migrations.AddIndex(
            model_name="activitylog",
            index=models.Index(fields=["project", "created_at"], name="tasks_activ_project_idx"),
        ),
        # --- TaskDependency ---
        migrations.CreateModel(
            name="TaskDependency",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_dependencies",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "dependent_task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prerequisites",
                        to="tasks.task",
                    ),
                ),
                (
                    "prerequisite_task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dependents",
                        to="tasks.task",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="taskdependency",
            constraint=models.UniqueConstraint(
                fields=["prerequisite_task", "dependent_task"],
                name="unique_task_dependency",
            ),
        ),
        migrations.AddIndex(
            model_name="taskdependency",
            index=models.Index(fields=["dependent_task"], name="tasks_taskd_dep_task_idx"),
        ),
        migrations.AddIndex(
            model_name="taskdependency",
            index=models.Index(fields=["prerequisite_task"], name="tasks_taskd_pre_task_idx"),
        ),
    ]
