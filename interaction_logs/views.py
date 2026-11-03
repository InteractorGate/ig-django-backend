from datetime import datetime, timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from pymongo.errors import DuplicateKeyError

from config.mongo import interaction_logs_collection

from .serializers import InteractionLogSerializer
from .summary import summarize_session


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
        now = datetime.now(timezone.utc)
        timestamp = data.get("timestamp") or now
        # BSON dates have millisecond precision; compare retries at that precision.
        timestamp = timestamp.astimezone(timezone.utc).replace(
            microsecond=(timestamp.microsecond // 1000) * 1000
        )

        document = {
            "user_id": request.user.id,
            "session_id": data["session_id"],
            "event_type": data["event_type"],
            "gaze_coordinates": data.get("gaze_coordinates"),
            "selected_word": data.get("selected_word"),
            "data": data.get("data"),
            # Client clock (when it happened) vs. server clock (when it
            # arrived): their difference is the network delay.
            "timestamp": timestamp,
            "received_at": now,
        }
        event_id = data.get("event_id")
        collection = interaction_logs_collection()
        if event_id is not None:
            document.update(
                _id=f"event:{request.user.id}:{event_id}",
                event_id=str(event_id),
                sequence=data["sequence"],
                schema_version=2,
            )
        try:
            result = collection.insert_one(document)
        except DuplicateKeyError:
            if event_id is None:
                raise
            previous = collection.find_one({"_id": document["_id"], "user_id": request.user.id})
            if previous is None:
                return Response({"detail": "Existing event is not readable yet; retry."},
                                status=status.HTTP_503_SERVICE_UNAVAILABLE)
            immutable = set(document) - {"received_at"}
            # Mongo may return naive UTC datetimes, depending on client options.
            if previous and previous.get("timestamp") is not None:
                previous["timestamp"] = previous["timestamp"].replace(tzinfo=timezone.utc)
            if not previous or any(previous.get(k) != document[k] for k in immutable):
                return Response({"detail": "event_id already has a different payload."},
                                status=status.HTTP_409_CONFLICT)
            return Response(_serialize(previous), status=status.HTTP_200_OK)
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
        logs = [_serialize(doc) for doc in cursor.limit(10001)]
        if len(logs) > 10000:
            return Response({"detail": "Session exceeds the 10000 event export limit."},
                            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        return Response(
            {"session_id": session_id, "count": len(logs), "logs": logs,
             "summary": summarize_session(logs)}
        )
