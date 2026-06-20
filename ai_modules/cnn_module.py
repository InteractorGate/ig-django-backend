"""Stub CNN eye-tracking module.

The real implementation (OpenCV + TensorFlow) will replace
``EyeTracker.predict()`` in a later sprint. For now it returns plausible
gaze coordinates so the prediction pipeline can be wired and tested
end-to-end.
"""
import random


class EyeTracker:
    """Maps a camera frame to a gaze point and the AAC cell it selects."""

    # Demo communication-board cells the gaze can land on.
    _CELLS = ["sí", "no", "agua", "comida", "ayuda", "baño", "dormir", "gracias"]

    def predict(self, frame):
        """frame: raw payload (base64 image, coords, ...). Returns gaze data."""
        x = round(random.uniform(0.0, 1.0), 3)
        y = round(random.uniform(0.0, 1.0), 3)
        selected = self._CELLS[int(x * len(self._CELLS)) % len(self._CELLS)]
        return {
            "gaze": {"x": x, "y": y},
            "selected": selected,
            "confidence": round(random.uniform(0.75, 0.99), 3),
        }
