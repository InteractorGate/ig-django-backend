from rest_framework import serializers


class GazeCoordinatesSerializer(serializers.Serializer):
    x = serializers.FloatField()
    y = serializers.FloatField()


class InteractionLogSerializer(serializers.Serializer):
    """Validates an incoming interaction-log event.

    These logs live in MongoDB (not the Django ORM), so this is a plain
    Serializer — it only validates the JSON payload. ``user_id`` and a
    fallback ``timestamp`` are injected server-side by the view.
    """

    EVENT_TYPES = (
        "gaze",
        "selection",
        "dwell",
        "calibration",
        "session_start",
        "session_end",
    )

    session_id = serializers.CharField(max_length=100)
    event_type = serializers.ChoiceField(choices=EVENT_TYPES)
    gaze_coordinates = GazeCoordinatesSerializer(required=False, allow_null=True)
    selected_word = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    timestamp = serializers.DateTimeField(required=False)
