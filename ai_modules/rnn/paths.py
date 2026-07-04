"""Shared filesystem locations for the RNN model artifacts."""
from pathlib import Path

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = ARTIFACT_DIR / "phrase_lstm.pt"      # torch weights + config + vocab
METRICS_PATH = ARTIFACT_DIR / "metrics.json"      # training/benchmark metrics
