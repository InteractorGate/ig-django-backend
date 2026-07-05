"""Shared filesystem locations for the gaze CNN.

The trained artifact and metrics live inside the repo (small, committed). The
raw MPIIGaze dataset does **not** — it is large and non-commercially licensed,
so its location is resolved at training time from the ``MPIIGAZE_DIR`` env var
with a sensible local default.
"""
import os
from pathlib import Path

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "gaze_cnn.pt"      # torch weights + config + norm stats
METRICS_PATH = ARTIFACT_DIR / "metrics.json"   # training/benchmark metrics


def dataset_dir() -> Path:
    """Root of the MPIIGaze dataset (the folder containing ``Data/Normalized``).

    Override with the ``MPIIGAZE_DIR`` environment variable. The default points
    at the copy downloaded next to this thesis repo during development.
    """
    default = Path(__file__).resolve().parents[3] / "MPIIGaze"
    return Path(os.environ.get("MPIIGAZE_DIR", default))
