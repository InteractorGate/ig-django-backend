"""AAC communication board + gaze-to-cell mapping.

The CNN predicts a 2D gaze *angle*; the app selects a board *cell*. This module
bridges the two: project the gaze angle onto the normalised screen and pick the
nearest cell, with a real confidence derived from how cleanly the gaze lands on
that cell versus its neighbours.

The angle->screen projection is a deployment placeholder (a fixed field of view,
no per-user calibration). On a real client the per-user calibration from the
tracker replaces it; here it gives a stable, documented mapping for the
batch/verification endpoint.
"""
import math

# Demo communication-board cells (same set the previous stub exposed), laid out
# on a 4-column x 2-row grid. Centres are normalised screen coordinates [0..1].
_GRID = [
    ["sí", "no", "agua", "comida"],
    ["ayuda", "baño", "dormir", "gracias"],
]
_ROWS = len(_GRID)
_COLS = len(_GRID[0])

CELLS = [
    {
        "word": word,
        "x": (col + 0.5) / _COLS,
        "y": (row + 0.5) / _ROWS,
    }
    for row, line in enumerate(_GRID)
    for col, word in enumerate(line)
]

# Half field of view (radians) mapped to half the screen. ~25° each way.
_HALF_FOV = math.radians(25.0)
# Softmax temperature over cell distances -> selection confidence.
_TEMP = 0.15


def gaze_angle_to_screen(pitch, yaw):
    """Map a gaze angle (radians) to a normalised screen point (x, y) in [0,1]."""
    x = 0.5 + (yaw / (2 * _HALF_FOV))
    y = 0.5 - (pitch / (2 * _HALF_FOV))
    return _clamp01(x), _clamp01(y)


def select_cell(x, y):
    """Nearest board cell to screen point (x, y) + a softmax confidence.

    Returns (word, confidence) where confidence is the softmax probability of
    the chosen cell given negative distances to every cell (high when the gaze
    lands squarely on one cell, low when it falls between cells).
    """
    dists = [math.hypot(x - c["x"], y - c["y"]) for c in CELLS]
    weights = [math.exp(-d / _TEMP) for d in dists]
    total = sum(weights) or 1.0
    best = min(range(len(CELLS)), key=lambda i: dists[i])
    return CELLS[best]["word"], weights[best] / total


def _clamp01(v):
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v
