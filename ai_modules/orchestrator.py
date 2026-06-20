"""Routes a prediction request to the correct AI module and returns a
unified result that the ``PredictionResult`` model can store.
"""
import time

from .cnn_module import EyeTracker
from .rnn_module import TextPredictor


class PredictionOrchestrator:
    """Single entry point used by the API to run a prediction."""

    def __init__(self):
        self._eye_tracker = EyeTracker()
        self._text_predictor = TextPredictor()

    def predict(self, input_type, raw_input):
        """Run the appropriate model and return a unified result dict."""
        start = time.perf_counter()

        if input_type == "gaze":
            raw = self._eye_tracker.predict(raw_input)
            model_used = "CNN"
            output_text = raw["selected"]
            confidence = raw["confidence"]
        elif input_type == "text":
            raw = self._text_predictor.predict(raw_input)
            model_used = "RNN"
            output_text = " | ".join(raw["suggestions"])
            confidence = raw["confidence"]
        else:
            raise ValueError(f"Unsupported input_type: {input_type!r}")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {
            "model_used": model_used,
            "output_text": output_text,
            "confidence_score": confidence,
            "response_time_ms": elapsed_ms,
            "raw_output": raw,
        }
