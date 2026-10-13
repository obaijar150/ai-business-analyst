from django.conf import settings
from django.db import models


class Dataset(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="datasets")
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="datasets/%Y/%m/")
    file_type = models.CharField(max_length=10)
    row_count = models.PositiveBigIntegerField(default=0)
    column_count = models.PositiveIntegerField(default=0)
    columns = models.JSONField(default=list)
    statistics = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        self.file.delete(save=False)
        return super().delete(*args, **kwargs)


class AnalysisRecord(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="analysis_records")
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name="analyses")
    question = models.TextField()
    analysis = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    explanation = models.TextField()
    evidence = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Analysis of {self.dataset.name} by {self.owner}"
