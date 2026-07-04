# RNN — Contextual Text Prediction (Phase 5, OE3-I2)

A real word-level **LSTM language model** (PyTorch) that powers the
`/api/predictions/` text path. Given a few words of context it suggests the
most likely next phrases for an AAC (Augmentative and Alternative
Communication) user, with a real confidence score.

This replaces the previous random stub. The eye-tracking **CNN** remains a stub
(see the project recap for the recommended architecture).

## Layout

| File | Purpose |
|---|---|
| `corpus.py` | Curated Spanish AAC training phrases (daily needs, feelings, requests, social). |
| `vocab.py` | Dependency-free word-level tokenizer + vocabulary. |
| `model.py` | `PhraseLSTM` — Embedding → LSTM → Linear language model. |
| `train.py` | Trains the model, writes the artifact + metrics, records history to Cosmos. |
| `infer.py` | `TextPredictor` — load-once inference with real softmax confidence. |
| `artifacts/phrase_lstm.pt` | Trained weights + config + vocab (committed, ~0.5 MB). |
| `artifacts/metrics.json` | Benchmark metrics from the last training run. |

## How it plugs in

`ai_modules/rnn_module.py` re-exports `TextPredictor`, so
`ai_modules/orchestrator.py` and `predictions/views.py` were **not** changed.
The model is loaded **once** (module-level singleton in `infer.py`) and reused
across requests. PyTorch is imported lazily, so Django startup and the
gaze/CNN path do not pay torch's import cost.

## Retraining

From the project root, with the venv active:

```bash
python -m ai_modules.rnn.train
```

This regenerates `artifacts/phrase_lstm.pt` and `artifacts/metrics.json`, and
(best-effort) writes a document to the Cosmos DB `training_history` collection.
Training is deterministic (`SEED = 42`). Widen `corpus.py` to grow the model's
active vocabulary.

## Benchmark (last run)

Config: `embed_dim=64, hidden_dim=128, num_layers=1, dropout=0.2`, 120 epochs,
103 training sentences, vocab 142 tokens.

| Split | Perplexity | Top-3 next-word accuracy |
|---|---|---|
| Train | 2.72 | 79.9% |
| Val (15%) | 143.4 | 41.8% |

The gap is expected: on a small, high-frequency AAC corpus the model
deliberately memorises core phrases (desirable for this domain). Qualitatively,
suggestions are coherent and context-appropriate, e.g.:

| Context | Suggestions (confidence) |
|---|---|
| `me duele` | *la cabeza · el estómago* (0.48) |
| `tengo` | *calor · sueño · sed* (0.27) |
| `gracias por` | *tu ayuda · venir* (0.53) |
| `llama a mi` | *mamá · papá · hermano* (0.41) |

**Next steps to raise the numbers:** expand the corpus (more sentences per
intent), add early stopping on validation perplexity, and evaluate against a
held-out set of real user utterances collected via the `interaction_logs`
telemetry.
