"""Load the MPIIGaze *Normalized* data for gaze-CNN training.

The normalized set stores, per participant/day, ``.mat`` (MATLAB v5) files with
grayscale 36x60 eye patches plus the ground-truth 3D gaze direction. We:

1. read the patches and 3D gaze vectors (both eyes),
2. convert each 3D gaze direction to a 2D (pitch, yaw) angle — the standard
   MPIIGaze target representation,
3. build a **participant-disjoint** train/val split so the reported error is a
   cross-person generalisation error (the honest protocol).

``scipy`` is imported here (offline training only); it is never needed at
inference time.
"""
from __future__ import annotations

import numpy as np

from .paths import dataset_dir

# Eye patches are stored 36 (H) x 60 (W) grayscale.
IMG_H, IMG_W = 36, 60

# Participant-disjoint split: train on the first 12, validate on the last 3.
TRAIN_PARTICIPANTS = [f"p{i:02d}" for i in range(12)]   # p00..p11
VAL_PARTICIPANTS = [f"p{i:02d}" for i in range(12, 15)]  # p12..p14


def gaze3d_to_2d(gaze: np.ndarray) -> np.ndarray:
    """Convert 3D gaze direction vectors (N,3) to 2D (pitch, yaw) angles (N,2).

    Uses the convention from the MPIIGaze ReadMe: a camera-looking direction
    maps to (0, 0). pitch = asin(-y); yaw = atan2(-x, -z).
    """
    x, y, z = gaze[:, 0], gaze[:, 1], gaze[:, 2]
    pitch = np.arcsin(-y)
    yaw = np.arctan2(-x, -z)
    return np.stack([pitch, yaw], axis=1).astype(np.float32)


def angles_to_3d(angles: np.ndarray) -> np.ndarray:
    """Inverse of :func:`gaze3d_to_2d` — 2D (pitch, yaw) -> unit 3D (N,3)."""
    pitch, yaw = angles[:, 0], angles[:, 1]
    x = -np.cos(pitch) * np.sin(yaw)
    y = -np.sin(pitch)
    z = -np.cos(pitch) * np.cos(yaw)
    return np.stack([x, y, z], axis=1)


def _load_participant(part_dir, max_samples):
    """Return (images (N,36,60) uint8, angles (N,2) float32) for one participant."""
    import scipy.io as sio  # offline-only dependency

    images, angles = [], []
    for mat_path in sorted(part_dir.glob("*.mat")):
        m = sio.loadmat(str(mat_path))
        data = m["data"]
        for side in ("left", "right"):
            sub = data[side][0, 0]
            imgs = sub["image"][0, 0]          # (n, 36, 60) uint8
            gaze = sub["gaze"][0, 0]           # (n, 3) float64
            if imgs.size == 0:
                continue
            images.append(imgs)
            angles.append(gaze3d_to_2d(gaze))

    if not images:
        return np.empty((0, IMG_H, IMG_W), np.uint8), np.empty((0, 2), np.float32)

    images = np.concatenate(images, axis=0)
    angles = np.concatenate(angles, axis=0)

    # Optional per-participant cap keeps CPU training time bounded and the split
    # balanced across people. Deterministic subsample (seeded).
    if max_samples and len(images) > max_samples:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(images), size=max_samples, replace=False)
        images, angles = images[idx], angles[idx]
    return images, angles


def load_split(participants, max_per_participant):
    """Load and stack (images, angles) for a list of participant ids."""
    norm_root = dataset_dir() / "Data" / "Normalized"
    if not norm_root.is_dir():
        raise RuntimeError(
            f"MPIIGaze Normalized data not found at {norm_root}. "
            "Set MPIIGAZE_DIR to the dataset root (folder with Data/Normalized)."
        )
    all_imgs, all_ang = [], []
    for pid in participants:
        pdir = norm_root / pid
        if not pdir.is_dir():
            continue
        imgs, ang = _load_participant(pdir, max_per_participant)
        if len(imgs):
            all_imgs.append(imgs)
            all_ang.append(ang)
    if not all_imgs:
        raise RuntimeError(f"No samples loaded for participants {participants}.")
    return np.concatenate(all_imgs), np.concatenate(all_ang)
