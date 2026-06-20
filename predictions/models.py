from django.conf import settings
from django.db import models


class PredictionRequest(models.Model):
    """An incoming prediction request (gaze frame or text context)."""

    class InputType(models.TextChoices):
        GAZE = "gaze", "Gaze"
        TEXT = "text", "Text"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prediction_requests",
    )
    input_type = models.CharField(max_length=10, choices=InputType.choices)
    raw_input = models.JSONField()
    session_id = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "predictions_request"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.input_type} req #{self.pk} (session {self.session_id})"


class PredictionResult(models.Model):
    """The AI output produced for a PredictionRequest."""

    class ModelUsed(models.TextChoices):
        CNN = "CNN", "CNN (eye tracking)"
        RNN = "RNN", "RNN (text prediction)"

    request = models.OneToOneField(
        PredictionRequest,
        on_delete=models.CASCADE,
        related_name="result",
    )
    model_used = models.CharField(max_length=8, choices=ModelUsed.choices)
    output_text = models.TextField()
    confidence_score = models.FloatField()
    response_time_ms = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "predictions_result"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.model_used} result for req #{self.request_id}"
