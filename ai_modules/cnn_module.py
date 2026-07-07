"""CNN eye-tracking module (real appearance-based gaze model).

The implementation now lives in the ``ai_modules.cnn`` package. This module
stays as the stable import path used by the orchestrator; it re-exports the
real ``EyeTracker`` so no caller had to change when the stub was replaced.

Training the artifact:  python -m ai_modules.cnn.train
"""
from ai_modules.cnn.infer import EyeTracker  # noqa: F401
