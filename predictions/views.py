from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_modules.orchestrator import PredictionOrchestrator

from .models import PredictionRequest, PredictionResult
from .serializers import PredictionRequestSerializer

# Stateless stub modules — safe to instantiate once at import time.
orchestrator = PredictionOrchestrator()


class PredictionView(APIView):
    """POST /api/predictions/ — run a prediction (routes to CNN or RNN)."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        serializer = PredictionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pred_request = serializer.save(user=request.user)

        outcome = orchestrator.predict(
            pred_request.input_type, pred_request.raw_input
        )
        PredictionResult.objects.create(
            request=pred_request,
            model_used=outcome["model_used"],
            output_text=outcome["output_text"],
            confidence_score=outcome["confidence_score"],
            response_time_ms=outcome["response_time_ms"],
        )
        pred_request.refresh_from_db()
        return Response(
            PredictionRequestSerializer(pred_request).data,
            status=status.HTTP_201_CREATED,
        )


class PredictionHistoryView(generics.ListAPIView):
    """GET /api/predictions/history/ — the user's past predictions."""

    permission_classes = (IsAuthenticated,)
    serializer_class = PredictionRequestSerializer

    def get_queryset(self):
        return (
            PredictionRequest.objects.filter(user=self.request.user)
            .select_related("result")
        )
