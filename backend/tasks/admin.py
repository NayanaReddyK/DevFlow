from django.contrib import admin

from .models import ActivityLog, Task, TaskDependency, TaskLabel


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "priority", "assignee", "due_date")
    list_filter = ("status", "priority")
    search_fields = ("title",)


@admin.register(TaskLabel)
class TaskLabelAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "color")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "task", "project", "actor", "created_at")
    list_filter = ("action",)
    readonly_fields = ("created_at",)


@admin.register(TaskDependency)
class TaskDependencyAdmin(admin.ModelAdmin):
    list_display = ("prerequisite_task", "dependent_task", "created_by", "created_at")
    readonly_fields = ("created_at",)
