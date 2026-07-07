# CNN — Appearance-Based Gaze Estimation (Phase 5, OE3-I2)

A real **convolutional neural network** (PyTorch) that powers the
`/api/predictions/` gaze path. Given a normalised grayscale eye patch it
predicts the user's **2D gaze direction** (pitch, yaw) and maps it to the AAC
communication-board cell being looked at, with a real confidence score.

This replaces the previous random stub. Real-time gaze is expected to run on the
**client** (see the project recap); this backend model serves the
batch/verification path and provides the trained, dataset-backed CNN deliverable
for the thesis.

## Dataset

Trained on **MPIIGaze** (Zhang et al., CVPR 2015) — 213,659 eye images from 15
participants captured during everyday laptop use.

- **Source:** <https://perceptualui.org/research/datasets/MPIIGaze/>
- **License:** Creative Commons **CC BY-NC-SA 4.0** (non-commercial; attribution
  + share-alike). Appropriate for academic thesis use; **cite the papers below**.
- We use the **Normalized** subset: 36×60 grayscale eye patches + ground-truth
  3D gaze direction, both eyes. The dataset is **not committed** to the repo
  (large, non-commercial); only the small trained artifact is.

**Citation (required by the license):**
> X. Zhang, Y. Sugano, M. Fritz, A. Bulling. *Appearance-Based Gaze Estimation
> in the Wild.* CVPR 2015.
> X. Zhang, Y. Sugano, M. Fritz, A. Bulling. *MPIIGaze: Real-World Dataset and
> Deep Appearance-Based Gaze Estimation.* IEEE TPAMI 2019.

## Layout

| File | Purpose |
|---|---|
| `dataset.py` | Loads MPIIGaze Normalized `.mat`, converts 3D gaze → 2D (pitch, yaw), participant-disjoint split. |
| `model.py` | `GazeCNN` — 3 Conv-BN-ReLU-Pool blocks → MLP head → (pitch, yaw). |
| `train.py` | Trains the model, writes the artifact + metrics, records history to Cosmos. |
| `board.py` | AAC board layout + gaze-angle → screen point → nearest-cell mapping. |
| `infer.py` | `EyeTracker` — load-once inference with real selection confidence. |
| `artifacts/gaze_cnn.pt` | Trained weights + config + normalisation stats (committed). |
| `artifacts/metrics.json` | Benchmark metrics from the last training run. |

## How it plugs in

`ai_modules/cnn_module.py` re-exports `EyeTracker`, so `ai_modules/orchestrator.py`
and `predictions/views.py` were **not** changed. The model is loaded **once**
(module-level singleton in `infer.py`) and reused across requests. PyTorch is
imported lazily, so Django startup and the text/RNN path do not pay torch's
import cost. The gaze endpoint tolerates an absent/garbage frame (it degrades to
a neutral patch) because real-time gaze runs client-side.

## Training / retraining

Requires the MPIIGaze dataset and `scipy` (offline-only — to read the `.mat`
files; never imported at inference/deploy time):

```powershell
pip install scipy
$env:MPIIGAZE_DIR = "C:\path\to\MPIIGaze"   # folder containing Data\Normalized
python -m ai_modules.cnn.train
```

This regenerates `artifacts/gaze_cnn.pt` and `artifacts/metrics.json`, and
(best-effort) writes a document to the Cosmos DB `training_history` collection.
Training is deterministic (`SEED = 42`). Tunables via env vars: `CNN_EPOCHS`,
`CNN_MAX_PER_PARTICIPANT`.

## Protocol & metric

- **Split:** participant-disjoint — train on `p00`–`p11`, validate on `p12`–`p14`.
  The reported error is therefore a **cross-person** generalisation error (the
  model is evaluated on people it never saw), the honest protocol for this task.
- **Metric:** **mean angular error in degrees** between the predicted and true
  3D gaze directions — the standard MPIIGaze benchmark metric.
- Eye-image-only (no head-pose fusion) — a clean, correct baseline. Head-pose
  fusion is the documented next step to lower the error further.

## Benchmark (last run)

Config: `channels=[16,32,64], fc_dim=128, dropout=0.3`, 253,282 params, 20
epochs, 18,000 train / 4,500 val patches (1,500 per participant per split),
eye-image-only. Artifact ≈ 1.0 MB.

| Split | MSE (rad²) | Mean angular error |
|---|---|---|
| Train (p00–p11) | 0.00635 | **5.67°** |
| Val (p12–p14, cross-person) | 0.01137 | **7.67°** |

The train/val gap is the expected cross-person generalisation gap: validation
uses three people the model never saw. 7.67° cross-person from an eye-only CNN on
a per-participant subset is a solid baseline — the original MPIIGaze LeNet
reaches ~6° using the full data **and** head-pose fusion (see next steps).

**Next steps to lower the error:** fuse 2D head pose into the FC head (the
original MPIIGaze LeNet setup), train on more samples per participant (or the
full set), add data augmentation, and evaluate with full leave-one-person-out
cross-validation instead of a single split.
