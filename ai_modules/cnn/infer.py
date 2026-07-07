"""Real-time inference for the appearance-based gaze CNN.

``EyeTracker`` keeps the same ``predict(frame)`` contract the stub used
(returns ``{"selected": ..., "confidence": float, ...}``) so the orchestrator
is unchanged. The trained model is loaded **once** on first use and shared
across all requests via a module-level cache.

PyTorch is imported lazily (inside the load path) so importing this module —
e.g. at Django startup or on the text/RNN code path — does not pay torch's
import cost unless a gaze prediction is actually requested.

Frame input is tolerant: the ``/api/predictions/`` gaze path is a
batch/verification endpoint (real-time gaze runs on the client), so an
unparseable/absent frame degrades to a neutral patch rather than erroring.
"""
import base64
import threading

import numpy as np

from .board import gaze_angle_to_screen, select_cell
from .dataset import IMG_H, IMG_W
from .paths import MODEL_PATH

# Module-level singleton: (model, norm) loaded once, reused across requests.
_MODEL = None
_NORM = None
_LOAD_LOCK = threading.Lock()


def _load_model():
    """Load weights + normalisation stats from the artifact into an eval model."""
    global _MODEL, _NORM
    with _LOAD_LOCK:
        if _MODEL is not None:
            return
        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"Gaze CNN artifact not found at {MODEL_PATH}. "
                "Train it first: python -m ai_modules.cnn.train"
            )
        import torch  # lazy: only when a gaze prediction is actually needed

        from .model import GazeCNN

        checkpoint = torch.load(MODEL_PATH, map_location="cpu")
        model = GazeCNN(**checkpoint["config"])
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        _MODEL, _NORM = model, checkpoint["norm"]


def _coerce_patch(frame):
    """Best-effort decode of ``frame`` into a (36,60) float32 patch in [0,255].

    Accepts a raw 36x60 uint8 buffer (base64 or bytes), a 2D/flat numeric list,
    or a dict wrapping any of those. Returns a neutral mid-grey patch when the
    frame cannot be interpreted, so the endpoint never 500s on a bad payload.
    """
    if isinstance(frame, dict):
        for key in ("patch", "image", "eye", "frame"):
            if key in frame:
                frame = frame[key]
                break

    try:
        if isinstance(frame, str):
            raw = base64.b64decode(frame, validate=False)
            arr = np.frombuffer(raw, dtype=np.uint8)
            if arr.size == IMG_H * IMG_W:
                return arr.reshape(IMG_H, IMG_W).astype(np.float32)
        elif isinstance(frame, (list, tuple, np.ndarray)):
            arr = np.asarray(frame, dtype=np.float32)
            if arr.size == IMG_H * IMG_W:
                return arr.reshape(IMG_H, IMG_W)
    except Exception:  # noqa: BLE001 — any decode failure -> neutral fallback
        pass

    # Neutral mid-grey patch: no usable signal -> model returns its prior.
    return np.full((IMG_H, IMG_W), 127.0, dtype=np.float32)


class EyeTracker:
    """Maps a normalised eye patch to a gaze point and the AAC cell it selects."""

    def predict(self, frame):
        """frame: raw payload (base64 patch, coords, dict). Returns gaze data."""
        if _MODEL is None:
            _load_model()

        import torch  # already imported by _load_model; cheap here

        patch = _coerce_patch(frame)
        x = (patch / 255.0 - _NORM["mean"]) / _NORM["std"]
        tensor = torch.from_numpy(x).float().unsqueeze(0).unsqueeze(0)  # (1,1,H,W)

        with torch.no_grad():
            pitch, yaw = (float(v) for v in _MODEL(tensor)[0])

        sx, sy = gaze_angle_to_screen(pitch, yaw)
        word, confidence = select_cell(sx, sy)
        return {
            "selected": word,
            "confidence": round(confidence, 4),
            "gaze": {"x": round(sx, 4), "y": round(sy, 4)},
            "angle": {"pitch": round(pitch, 4), "yaw": round(yaw, 4)},
            "model": "GazeCNN",
        }
