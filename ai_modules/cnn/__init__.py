"""Real appearance-based gaze-estimation CNN (Phase 5, OE3-I2).

A compact convolutional network (PyTorch) trained on the **MPIIGaze** dataset
that maps a normalised grayscale eye patch to a 2D gaze direction (pitch, yaw).
It replaces the previous random ``EyeTracker`` stub on the ``/api/predictions/``
gaze path.

Training data lives outside the repo (MPIIGaze, CC BY-NC-SA 4.0); only the small
trained artifact ``artifacts/gaze_cnn.pt`` is committed. See ``README.md``.
"""
