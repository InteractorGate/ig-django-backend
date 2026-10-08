import json

from rest_framework import serializers

# Cap on ``data``. Study events weigh a few hundred bytes; the cap also keeps
# images (camera frames, eye patches) out, which the data protocol (thesis
# section 4.5.9) promises never to send.
MAX_DATA_BYTES = 4096


class GazeCoordinatesSerializer(serializers.Serializer):
    x = serializers.FloatField()
    y = serializers.FloatField()


class InteractionLogSerializer(serializers.Serializer):
    """Validates an incoming interaction-log event.

    These logs live in MongoDB (not the Django ORM), so this is a plain
    Serializer — it only validates the JSON payload. ``user_id`` and
    ``received_at`` are injected server-side by the view; ``timestamp`` is the
    client's clock (when the event happened), falling back to server time.
    """

    EVENT_TYPES = (
        "gaze",
        "selection",
        "dwell",
        "calibration",
        "session_start",
        "session_end",
        # User-study (E2) events.
        "delete",
        "clear",
        "suggestions",
        "trial_start",
        "trial_end",
        "settings",
    )

    session_id = serializers.CharField(max_length=100)
    event_type = serializers.ChoiceField(choices=EVENT_TYPES)
    gaze_coordinates = GazeCoordinatesSerializer(required=False, allow_null=True)
    selected_word = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    timestamp = serializers.DateTimeField(required=False)
    # Event-specific detail (condition, target phrase, suggestion rank,
    # latency...). Free-form but small.
    data = serializers.DictField(required=False, allow_null=True)

    def validate_data(self, value):
        if value is not None and len(json.dumps(value)) > MAX_DATA_BYTES:
            raise serializers.ValidationError(
                f"data exceeds {MAX_DATA_BYTES} bytes."
            )
        return value
