import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Dataset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("file", models.FileField(upload_to="datasets/%Y/%m/")),
                ("file_type", models.CharField(max_length=10)),
                ("row_count", models.PositiveBigIntegerField(default=0)),
                ("column_count", models.PositiveIntegerField(default=0)),
                ("columns", models.JSONField(default=list)),
                ("statistics", models.JSONField(default=dict)),
                ("metadata", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="datasets", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
