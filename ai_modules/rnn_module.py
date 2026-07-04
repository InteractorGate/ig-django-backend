"""RNN contextual text-prediction module (real PyTorch LSTM).

The implementation now lives in the ``ai_modules.rnn`` package. This module
stays as the stable import path used by the orchestrator; it re-exports the
real ``TextPredictor`` so no caller had to change when the stub was replaced.

Training the artifact:  python -m ai_modules.rnn.train
"""
from ai_modules.rnn.infer import TextPredictor  # noqa: F401
