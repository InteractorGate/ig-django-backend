"""Train the gaze-estimation CNN on MPIIGaze and save a real model artifact.

Run from the project root (venv active, ``scipy`` installed):

    python -m ai_modules.cnn.train

Produces:
    ai_modules/cnn/artifacts/gaze_cnn.pt    (weights + config + norm stats)
    ai_modules/cnn/artifacts/metrics.json   (loss + mean angular error, degrees)

Also writes a training-history document to the Cosmos DB ``training_history``
collection (best-effort — skipped with a warning if Django/Cosmos is not
configured, so the script always runs in a bare dev environment).

Tunable via env vars:
    MPIIGAZE_DIR            root of the MPIIGaze dataset (see paths.py)
    CNN_EPOCHS             training epochs (default 20)
    CNN_MAX_PER_PARTICIPANT  per-person sample cap for CPU time (default 1500)
"""
import json
import math
import os

import numpy as np
import torch
import torch.nn as nn

from .dataset import (
    IMG_H,
    IMG_W,
    TRAIN_PARTICIPANTS,
    VAL_PARTICIPANTS,
    angles_to_3d,
    load_split,
)
from .model import DEFAULT_CONFIG, GazeCNN
from .paths import ARTIFACT_DIR, METRICS_PATH, MODEL_PATH

# Reproducible training so the committed artifact is regenerable.
SEED = 42
EPOCHS = int(os.environ.get("CNN_EPOCHS", 20))
BATCH_SIZE = 128
LEARNING_RATE = 1e-3
MAX_PER_PARTICIPANT = int(os.environ.get("CNN_MAX_PER_PARTICIPANT", 1500))


def _to_tensors(images, angles, mean, std):
    """Normalise uint8 patches to zero-mean/unit-std and return float tensors."""
    x = (images.astype(np.float32) / 255.0 - mean) / std
    x = torch.from_numpy(x).unsqueeze(1)               # (N, 1, 36, 60)
    y = torch.from_numpy(angles.astype(np.float32))    # (N, 2)
    return x, y


def _mean_angular_error_deg(pred_angles, true_angles):
    """Mean angle (degrees) between predicted and true 3D gaze directions."""
    p = angles_to_3d(pred_angles.numpy())
    t = angles_to_3d(true_angles.numpy())
    p /= np.linalg.norm(p, axis=1, keepdims=True)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    dot = np.clip(np.sum(p * t, axis=1), -1.0, 1.0)
    return float(np.degrees(np.arccos(dot)).mean())


@torch.no_grad()
def _evaluate(model, x, y, criterion):
    """Return (loss, mean angular error in degrees) over a whole tensor set."""
    model.eval()
    preds, total_loss, n = [], 0.0, 0
    for start in range(0, len(x), BATCH_SIZE):
        xb, yb = x[start:start + BATCH_SIZE], y[start:start + BATCH_SIZE]
        out = model(xb)
        total_loss += float(criterion(out, yb)) * len(xb)
        preds.append(out)
        n += len(xb)
    pred = torch.cat(preds)
    return total_loss / max(n, 1), _mean_angular_error_deg(pred, y)


def train():
    torch.manual_seed(SEED)
    np.random.seed(SEED)

    # ── Data ──────────────────────────────────────────────────────────────
    print("Loading MPIIGaze (Normalized)…")
    tr_imgs, tr_ang = load_split(TRAIN_PARTICIPANTS, MAX_PER_PARTICIPANT)
    va_imgs, va_ang = load_split(VAL_PARTICIPANTS, MAX_PER_PARTICIPANT)
    print(f"Train: {len(tr_imgs)} patches ({len(TRAIN_PARTICIPANTS)} people) | "
          f"Val: {len(va_imgs)} patches ({len(VAL_PARTICIPANTS)} people)")

    # Normalisation stats from the TRAIN set only (avoid leaking val stats).
    mean = float(tr_imgs.astype(np.float32).mean() / 255.0)
    std = float(tr_imgs.astype(np.float32).std() / 255.0) or 1.0
    x_tr, y_tr = _to_tensors(tr_imgs, tr_ang, mean, std)
    x_va, y_va = _to_tensors(va_imgs, va_ang, mean, std)

    # ── Model ─────────────────────────────────────────────────────────────
    model = GazeCNN(**DEFAULT_CONFIG)
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE,
                                 weight_decay=1e-4)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"GazeCNN: {n_params:,} params | epochs: {EPOCHS}")

    # ── Training loop ─────────────────────────────────────────────────────
    g = torch.Generator().manual_seed(SEED)
    for epoch in range(1, EPOCHS + 1):
        model.train()
        perm = torch.randperm(len(x_tr), generator=g)
        epoch_loss = 0.0
        for start in range(0, len(x_tr), BATCH_SIZE):
            idx = perm[start:start + BATCH_SIZE]
            xb, yb = x_tr[idx], y_tr[idx]
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item() * len(xb)
        if epoch % 5 == 0 or epoch == 1:
            _, va_err = _evaluate(model, x_va, y_va, criterion)
            print(f"epoch {epoch:3d} | train_mse {epoch_loss / len(x_tr):.5f} "
                  f"| val_angular_err {va_err:.2f}°")

    # ── Final metrics ─────────────────────────────────────────────────────
    tr_loss, tr_err = _evaluate(model, x_tr, y_tr, criterion)
    va_loss, va_err = _evaluate(model, x_va, y_va, criterion)
    metrics = {
        "model": "GazeCNN",
        "dataset": "MPIIGaze (Normalized)",
        "framework": f"pytorch-{torch.__version__}",
        "epochs": EPOCHS,
        "params": n_params,
        "config": model.config,
        "image_size": [IMG_H, IMG_W],
        "train_participants": TRAIN_PARTICIPANTS,
        "val_participants": VAL_PARTICIPANTS,
        "train_samples": len(x_tr),
        "val_samples": len(x_va),
        "norm": {"mean": round(mean, 5), "std": round(std, 5)},
        "train": {"mse": round(tr_loss, 5),
                  "mean_angular_error_deg": round(tr_err, 3)},
        "val": {"mse": round(va_loss, 5),
                "mean_angular_error_deg": round(va_err, 3)},
    }

    # ── Save artifact + metrics ───────────────────────────────────────────
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": model.config,
            "norm": {"mean": mean, "std": std},
            "image_size": [IMG_H, IMG_W],
        },
        MODEL_PATH,
    )
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"\nSaved model   -> {MODEL_PATH}")
    print(f"Saved metrics -> {METRICS_PATH}")
    print(f"Cross-person mean angular error (val): {va_err:.2f}°")

    _record_training_history(metrics)
    return metrics


def _record_training_history(metrics):
    """Best-effort write of training metrics to Cosmos DB (never blocks)."""
    try:
        import django

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
        django.setup()
        from datetime import datetime, timezone

        from config.mongo import training_history_collection

        doc = {**metrics, "recorded_at": datetime.now(timezone.utc)}
        result = training_history_collection().insert_one(doc)
        print(f"Recorded training history -> Cosmos (_id={result.inserted_id})")
    except Exception as exc:  # noqa: BLE001 — best-effort, never block training
        print(f"[warn] skipped Cosmos training-history write: {exc}")


if __name__ == "__main__":
    train()
