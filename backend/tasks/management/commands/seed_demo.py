import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from projects.models import Project, ProjectMember
from tasks.models import Task, TaskDependency
from workspaces.models import Workspace, WorkspaceMember


class Command(BaseCommand):
    help = "Create an idempotent DevFlow demo workspace, project, and tasks."

    def handle(self, *args, **options):
        email = os.getenv("DEMO_USER_EMAIL", "demo@example.com").strip().lower()
        password = os.getenv("DEMO_USER_PASSWORD")
        username = os.getenv("DEMO_USER_NAME", "demo")
        if not password:
            raise CommandError("Set DEMO_USER_PASSWORD before running seed_demo.")

        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"username": username},
        )
        if created or not user.check_password(password):
            user.set_password(password)
            user.save(update_fields=["password"])

        workspace, _ = Workspace.objects.get_or_create(
            slug="devflow-demo",
            defaults={"name": "DevFlow Demo", "owner": user},
        )
        WorkspaceMember.objects.get_or_create(
            workspace=workspace,
            user=user,
            defaults={"role": WorkspaceMember.Role.OWNER},
        )

        project, _ = Project.objects.get_or_create(
            workspace=workspace,
            slug="workflow-intelligence-demo",
            defaults={
                "name": "Workflow Intelligence Demo",
                "description": "Seeded tasks that demonstrate dependency-aware insights.",
                "created_by": user,
                "target_date": timezone.localdate() + timedelta(days=14),
            },
        )
        ProjectMember.objects.get_or_create(
            project=project,
            user=user,
            defaults={"role": ProjectMember.Role.MANAGER},
        )

        root, _ = Task.objects.get_or_create(
            project=project,
            title="Resolve the shared API contract",
            defaults={
                "description": "This prerequisite blocks six downstream tasks.",
                "created_by": user,
                "assignee": user,
                "status": Task.Status.IN_PROGRESS,
                "priority": Task.Priority.HIGH,
                "due_date": timezone.localdate() - timedelta(days=1),
                "estimate": 3,
            },
        )

        for index in range(1, 7):
            dependent, _ = Task.objects.get_or_create(
                project=project,
                title=f"Complete dependent work item {index}",
                defaults={
                    "created_by": user,
                    "assignee": user,
                    "status": Task.Status.TODO,
                    "priority": Task.Priority.MEDIUM,
                },
            )
            TaskDependency.objects.get_or_create(
                prerequisite_task=root,
                dependent_task=dependent,
                defaults={"created_by": user},
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded demo workspace '{workspace.slug}' and project '{project.slug}'."
            )
        )
        self.stdout.write(f"Demo login email: {email}")
        self.stdout.write("Password was read from DEMO_USER_PASSWORD and is not printed.")
