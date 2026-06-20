from datetime import datetime, timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.mongo import interaction_logs_collection

from .serializers import InteractionLogSerializer


def _serialize(doc):
    """Make a MongoDB document JSON-safe (ObjectId -> str)."""
    out = dict(doc)
    _id = out.pop("_id", None)
    if _id is not None:
        out["id"] = str(_id)
    return out


class LogInteractionView(APIView):
    """POST /api/logs/ — write one interaction event to MongoDB."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = InteractionLogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        document = {
            "user_id": request.user.id,
            "session_id": data["session_id"],
            "event_type": data["event_type"],
            "gaze_coordinates": data.get("gaze_coordinates"),
            "selected_word": data.get("selected_word"),
            "timestamp": data.get("timestamp") or datetime.now(timezone.utc),
        }
        result = interaction_logs_collection().insert_one(document)
        return Response(
            _serialize({"_id": result.inserted_id, **document}),
            status=status.HTTP_201_CREATED,
        )


class SessionLogsView(APIView):
    """GET /api/logs/session/<session_id>/ — read a session's events."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, session_id):
        cursor = (
            interaction_logs_collection()
            .find({"session_id": session_id, "user_id": request.user.id})
            .sort("timestamp", 1)
        )
        logs = [_serialize(doc) for doc in cursor]
        return Response(
            {"session_id": session_id, "count": len(logs), "logs": logs}
        )
