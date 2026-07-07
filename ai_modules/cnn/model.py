"""PyTorch CNN for appearance-based gaze estimation (MPIIGaze).

A compact LeNet-style network: three Conv-BN-ReLU-Pool blocks over a 1x36x60
grayscale eye patch, then a small MLP head regressing 2D gaze (pitch, yaw).
Small by design (thesis / CPU inference on Azure B1) but a real trainable CNN —
not a stub.
"""
import torch
import torch.nn as nn

# Default hyper-parameters. Kept small so the artifact stays well under a MB and
# inference is fast on CPU.
DEFAULT_CONFIG = {
    "channels": [16, 32, 64],
    "fc_dim": 128,
    "dropout": 0.3,
}


class GazeCNN(nn.Module):
    """Grayscale eye patch (1x36x60) -> 2D gaze angle (pitch, yaw)."""

    def __init__(self, channels=(16, 32, 64), fc_dim=128, dropout=0.3):
        super().__init__()
        self.config = {
            "channels": list(channels),
            "fc_dim": fc_dim,
            "dropout": dropout,
        }
        c1, c2, c3 = channels
        self.features = nn.Sequential(
            nn.Conv2d(1, c1, 3, padding=1), nn.BatchNorm2d(c1), nn.ReLU(),
            nn.MaxPool2d(2),                      # 36x60 -> 18x30
            nn.Conv2d(c1, c2, 3, padding=1), nn.BatchNorm2d(c2), nn.ReLU(),
            nn.MaxPool2d(2),                      # 18x30 -> 9x15
            nn.Conv2d(c2, c3, 3, padding=1), nn.BatchNorm2d(c3), nn.ReLU(),
            nn.MaxPool2d(2),                      # 9x15 -> 4x7
        )
        self.flat_dim = c3 * 4 * 7
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(self.flat_dim, fc_dim), nn.ReLU(), nn.Dropout(dropout),
            nn.Linear(fc_dim, 2),                 # (pitch, yaw) in radians
        )

    def forward(self, x):
        """x: (batch, 1, 36, 60). Returns (batch, 2) gaze angles."""
        return self.head(self.features(x))
