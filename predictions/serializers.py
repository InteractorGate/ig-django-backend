from rest_framework import serializers

from .models import PredictionRequest, PredictionResult


class PredictionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = PredictionResult
        fields = (
            "id",
            "model_used",
            "output_text",
            "confidence_score",
            "response_time_ms",
            "created_at",
        )
        read_only_fields = fields


class PredictionRequestSerializer(serializers.ModelSerializer):
    """Used for both input (create) and output (with nested result)."""

    result = PredictionResultSerializer(read_only=True)

    class Meta:
        model = PredictionRequest
        fields = (
            "id",
            "input_type",
            "raw_input",
            "session_id",
            "created_at",
            "result",
        )
        read_only_fields = ("id", "created_at", "result")
