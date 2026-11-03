import json

from rest_framework import serializers

# Cap on ``data``. Study events weigh a few hundred bytes; the cap also keeps
# images (camera frames, eye patches) out, which the data protocol (thesis
# section 4.5.9) promises never to send.
MAX_DATA_BYTES = 4096


class GazeCoordinatesSerializer(serializers.Serializer):
    x = serializers.FloatField(min_value=0, max_value=1)
    y = serializers.FloatField(min_value=0, max_value=1)


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
    event_id = serializers.UUIDField(required=False)
    participant_id = serializers.IntegerField(min_value=1, required=False)
    sequence = serializers.IntegerField(min_value=1, required=False)
    event_type = serializers.ChoiceField(choices=EVENT_TYPES)
    gaze_coordinates = GazeCoordinatesSerializer(required=False, allow_null=True)
    selected_word = serializers.CharField(
        max_length=255, required=False, allow_blank=True, allow_null=True
    )
    timestamp = serializers.DateTimeField(required=False)
    # Event-specific detail (condition, target phrase, suggestion rank,
    # latency...). Free-form but small.
    data = serializers.DictField(required=False, allow_null=True)

    def validate(self, attrs):
        event_id = attrs.get("event_id")
        if event_id is not None:
            if (event_id.version != 4 or "sequence" not in attrs
                    or "timestamp" not in attrs or "participant_id" not in attrs):
                raise serializers.ValidationError(
                    "event_id must be UUID v4 and requires participant_id, sequence and timestamp."
                )
        elif "sequence" in attrs:
            raise serializers.ValidationError("sequence requires event_id.")
        return attrs

    def validate_data(self, value):
        if value is None:
            return value
        allowed = {
            "study", "bank_version", "provisional", "protocol_session", "practice",
            "participant_number", "trial_id", "phrase_id", "target_phrase", "target",
            "list", "condition", "block", "order", "status", "final_text", "duration_ms",
            "list_with_prediction", "seed", "dwell_enabled", "dwell_seconds",
            "phrase_order", "first_condition", "board_mode", "action", "elapsed_ms",
            "inserted_text", "removed_characters", "text_length", "suggestion_rank",
            "request_id", "suggestions", "latency_ms", "reason", "source",
        }
        if value.keys() - allowed:
            raise serializers.ValidationError("Unsupported telemetry fields.")
        for key, item in value.items():
            if isinstance(item, list):
                if key not in {"phrase_order", "suggestions"} or len(item) > 40 or any(
                    not isinstance(s, str) or len(s) > 255 for s in item
                ):
                    raise serializers.ValidationError("Invalid telemetry list.")
            elif item is not None and not isinstance(item, (str, int, float, bool)):
                raise serializers.ValidationError("Telemetry values must be scalars.")
            if isinstance(item, str) and len(item) > (2000 if key == "final_text" else 255):
                raise serializers.ValidationError("Telemetry text is too long.")
        try:
            size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise serializers.ValidationError("Invalid telemetry value.") from exc
        if size > MAX_DATA_BYTES:
            raise serializers.ValidationError(
                f"data exceeds {MAX_DATA_BYTES} bytes."
            )
        return value
