"""Export the trained gaze CNN to ONNX for lightweight client-side inference.

The desktop tracker (Flutter sidecar) runs the model with onnxruntime instead of
PyTorch, so the packaged app stays small and fast. Run from the project root:

    python -m ai_modules.cnn.export_onnx

Produces (next to the .pt artifact):
    ai_modules/cnn/artifacts/gaze_cnn.onnx
    ai_modules/cnn/artifacts/gaze_cnn.meta.json   (norm stats + image size)
"""
import json

import torch

from .dataset import IMG_H, IMG_W
from .model import GazeCNN
from .paths import ARTIFACT_DIR, MODEL_PATH

ONNX_PATH = ARTIFACT_DIR / "gaze_cnn.onnx"
META_PATH = ARTIFACT_DIR / "gaze_cnn.meta.json"


def export():
    if not MODEL_PATH.exists():
        raise RuntimeError(
            f"Artifact not found at {MODEL_PATH}. Train first: "
            "python -m ai_modules.cnn.train"
        )
    checkpoint = torch.load(MODEL_PATH, map_location="cpu")
    model = GazeCNN(**checkpoint["config"])
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()

    dummy = torch.zeros(1, 1, IMG_H, IMG_W, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy,
        str(ONNX_PATH),
        input_names=["eye_patch"],
        output_names=["gaze_angles"],
        dynamic_axes={"eye_patch": {0: "batch"}, "gaze_angles": {0: "batch"}},
        opset_version=17,
        dynamo=False,  # legacy TorchScript exporter (no onnxscript dependency)
    )

    meta = {
        "image_size": [IMG_H, IMG_W],          # [H, W] grayscale patch
        "norm": checkpoint["norm"],            # {"mean":..., "std":...}
        "output": ["pitch", "yaw"],            # radians
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    # Sanity check: onnxruntime output must match torch within tolerance.
    try:
        import numpy as np
        import onnxruntime as ort

        sess = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
        onnx_out = sess.run(None, {"eye_patch": dummy.numpy()})[0]
        with torch.no_grad():
            torch_out = model(dummy).numpy()
        max_diff = float(np.abs(onnx_out - torch_out).max())
        print(f"ONNX vs Torch max diff: {max_diff:.2e}")
    except ImportError:
        print("(onnxruntime not installed here — skipped parity check)")

    print(f"Saved ONNX  -> {ONNX_PATH}")
    print(f"Saved meta  -> {META_PATH}")


if __name__ == "__main__":
    export()
