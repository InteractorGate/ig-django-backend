"""Train the AAC phrase-prediction LSTM and save a real model artifact.

Run from the project root:

    python -m ai_modules.rnn.train

Produces:
    ai_modules/rnn/artifacts/phrase_lstm.pt   (weights + config + vocab)
    ai_modules/rnn/artifacts/metrics.json     (loss / perplexity / top-k acc)

Also writes a training-history document to the Cosmos DB ``training_history``
collection (best-effort — skipped with a warning if Django/Cosmos is not
configured, so the script always runs in a bare dev environment).
"""
import json
import math

import torch
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence

from .corpus import load_corpus
from .model import DEFAULT_CONFIG, PhraseLSTM
from .paths import ARTIFACT_DIR, METRICS_PATH, MODEL_PATH
from .vocab import BOS, EOS, Vocabulary, tokenize

# Reproducible training so the committed artifact is regenerable.
SEED = 42
EPOCHS = 120
BATCH_SIZE = 16
LEARNING_RATE = 3e-3
VAL_FRACTION = 0.15
TOP_K = 3


def _build_sequences(sentences, vocab):
    """Turn each sentence into a (input, target) index tensor pair.

    Teacher forcing: predict token t+1 from tokens ≤ t. Each sequence is
    [BOS] w1 w2 ... wn [EOS]; input drops the last token, target drops the
    first, so they are aligned and one step apart.
    """
    bos, eos = vocab.bos_index, vocab.eos_index
    pairs = []
    for tokens in sentences:
        ids = [bos] + vocab.encode(tokens) + [eos]
        if len(ids) < 2:
            continue
        inp = torch.tensor(ids[:-1], dtype=torch.long)
        tgt = torch.tensor(ids[1:], dtype=torch.long)
        pairs.append((inp, tgt))
    return pairs


def _batches(pairs, batch_size, pad_index):
    """Yield padded (inputs, targets) batches."""
    for start in range(0, len(pairs), batch_size):
        chunk = pairs[start:start + batch_size]
        inputs = pad_sequence(
            [p[0] for p in chunk], batch_first=True, padding_value=pad_index
        )
        targets = pad_sequence(
            [p[1] for p in chunk], batch_first=True, padding_value=pad_index
        )
        yield inputs, targets


@torch.no_grad()
def _evaluate(model, pairs, criterion, pad_index):
    """Return (loss, perplexity, top-k accuracy) over the given pairs."""
    if not pairs:
        return 0.0, 0.0, 0.0
    model.eval()
    total_loss, total_tokens, top_k_hits = 0.0, 0, 0
    for inputs, targets in _batches(pairs, BATCH_SIZE, pad_index):
        logits, _ = model(inputs)
        loss = criterion(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        mask = targets != pad_index
        n = int(mask.sum())
        total_loss += float(loss) * n
        total_tokens += n
        # Top-k accuracy over real (non-pad) target positions.
        topk = logits.topk(TOP_K, dim=-1).indices          # (B, T, K)
        hits = (topk == targets.unsqueeze(-1)) & mask.unsqueeze(-1)
        top_k_hits += int(hits.any(dim=-1).sum())
    avg_loss = total_loss / max(total_tokens, 1)
    return avg_loss, math.exp(avg_loss), top_k_hits / max(total_tokens, 1)


def train():
    torch.manual_seed(SEED)

    # ── Data ──────────────────────────────────────────────────────────────
    raw = load_corpus()
    tokenized = [tokenize(s) for s in raw]
    tokenized = [t for t in tokenized if t]
    vocab = Vocabulary.build(tokenized, min_freq=1)

    pairs = _build_sequences(tokenized, vocab)
    # Deterministic shuffle + split.
    g = torch.Generator().manual_seed(SEED)
    order = torch.randperm(len(pairs), generator=g).tolist()
    pairs = [pairs[i] for i in order]
    n_val = max(1, int(len(pairs) * VAL_FRACTION))
    val_pairs, train_pairs = pairs[:n_val], pairs[n_val:]

    print(f"Corpus: {len(tokenized)} sentences | vocab: {len(vocab)} tokens")
    print(f"Sequences: {len(train_pairs)} train / {len(val_pairs)} val")

    # ── Model ─────────────────────────────────────────────────────────────
    model = PhraseLSTM(len(vocab), vocab.pad_index, **DEFAULT_CONFIG)
    criterion = nn.CrossEntropyLoss(ignore_index=vocab.pad_index)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=LEARNING_RATE, weight_decay=1e-4
    )

    # ── Training loop ─────────────────────────────────────────────────────
    for epoch in range(1, EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        for inputs, targets in _batches(train_pairs, BATCH_SIZE, vocab.pad_index):
            optimizer.zero_grad()
            logits, _ = model(inputs)
            loss = criterion(
                logits.reshape(-1, logits.size(-1)), targets.reshape(-1)
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            optimizer.step()
            epoch_loss += loss.item()
        if epoch % 20 == 0 or epoch == 1:
            v_loss, v_ppl, v_acc = _evaluate(
                model, val_pairs, criterion, vocab.pad_index
            )
            print(
                f"epoch {epoch:3d} | train_loss {epoch_loss:.3f} "
                f"| val_ppl {v_ppl:.2f} | val_top{TOP_K}_acc {v_acc:.2%}"
            )

    # ── Final metrics ─────────────────────────────────────────────────────
    tr_loss, tr_ppl, tr_acc = _evaluate(model, train_pairs, criterion, vocab.pad_index)
    v_loss, v_ppl, v_acc = _evaluate(model, val_pairs, criterion, vocab.pad_index)
    metrics = {
        "model": "PhraseLSTM",
        "framework": f"pytorch-{torch.__version__}",
        "epochs": EPOCHS,
        "vocab_size": len(vocab),
        "train_sentences": len(tokenized),
        "config": model.config,
        "train": {
            "loss": round(tr_loss, 4),
            "perplexity": round(tr_ppl, 3),
            f"top{TOP_K}_accuracy": round(tr_acc, 4),
        },
        "val": {
            "loss": round(v_loss, 4),
            "perplexity": round(v_ppl, 3),
            f"top{TOP_K}_accuracy": round(v_acc, 4),
        },
    }

    # ── Save artifact + metrics ───────────────────────────────────────────
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "config": model.config,
            "vocab": vocab.to_dict(),
        },
        MODEL_PATH,
    )
    METRICS_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"\nSaved model -> {MODEL_PATH}")
    print(f"Saved metrics -> {METRICS_PATH}")
    print(json.dumps(metrics["val"], ensure_ascii=False))

    _record_training_history(metrics)
    return metrics


def _record_training_history(metrics):
    """Best-effort write of training metrics to Cosmos DB.

    Skipped (with a warning) if Django settings / Cosmos credentials are not
    available, so training never hard-fails in a bare environment.
    """
    try:
        import os

        import django

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
        django.setup()
        from datetime import datetime, timezone

        from config.mongo import training_history_collection

        doc = {
            **metrics,
            "recorded_at": datetime.now(timezone.utc),
        }
        result = training_history_collection().insert_one(doc)
        print(f"Recorded training history -> Cosmos (_id={result.inserted_id})")
    except Exception as exc:  # noqa: BLE001 — best-effort, never block training
        print(f"[warn] skipped Cosmos training-history write: {exc}")


if __name__ == "__main__":
    train()
