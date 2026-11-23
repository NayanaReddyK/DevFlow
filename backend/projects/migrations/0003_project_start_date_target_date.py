from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0002_alter_project_status_alter_project_workspace"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="project",
            name="target_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
