"""Real-time inference for the AAC phrase-prediction LSTM.

``TextPredictor`` exposes the same ``predict(context)`` contract the stub used
(returns ``{"suggestions": [...], "confidence": float}``) so the orchestrator
is unchanged. The trained model is loaded **once** on first use and shared
across all requests via a module-level cache.

PyTorch is imported lazily (inside the load path) so importing this module —
e.g. at Django startup or on the gaze/CNN code path — does not pay torch's
import cost unless a text prediction is actually requested.
"""
import threading

from .paths import MODEL_PATH
from .vocab import Vocabulary, tokenize

# How many candidate phrases to return and how far to extend each one.
NUM_SUGGESTIONS = 3
MAX_PHRASE_WORDS = 6

# Module-level singleton: (model, vocab) loaded once, reused across requests.
_MODEL = None
_VOCAB = None
_LOAD_LOCK = threading.Lock()


def _load_model():
    """Load weights + vocab from the artifact into a ready-to-eval model."""
    global _MODEL, _VOCAB
    with _LOAD_LOCK:
        if _MODEL is not None:
            return
        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"RNN model artifact not found at {MODEL_PATH}. "
                "Train it first: python -m ai_modules.rnn.train"
            )
        import torch  # lazy: only when a prediction is actually needed

        from .model import PhraseLSTM

        checkpoint = torch.load(MODEL_PATH, map_location="cpu")
        vocab = Vocabulary.from_dict(checkpoint["vocab"])
        model = PhraseLSTM(
            len(vocab), vocab.pad_index, **checkpoint["config"]
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        _MODEL, _VOCAB = model, vocab


class TextPredictor:
    """Suggests next phrases given the current text context (real RNN)."""

    def predict(self, context):
        """context: str / list of words / dict with a ``context`` field.

        Returns ranked phrase suggestions and a real confidence score (the
        softmax probability of the model's top next-word prediction).
        """
        if _MODEL is None:
            _load_model()

        import torch  # already imported by _load_model; cheap here

        model, vocab = _MODEL, _VOCAB
        specials = {
            vocab.pad_index, vocab.bos_index, vocab.eos_index, vocab.unk_index
        }

        tokens = tokenize(context)
        prefix_ids = [vocab.bos_index] + vocab.encode(tokens)

        @torch.no_grad()
        def next_logits(ids):
            x = torch.tensor([ids], dtype=torch.long)
            logits, _ = model(x)
            return logits[0, -1]

        # Rank candidate next words (excluding special tokens) for the seeds.
        logits = next_logits(prefix_ids)
        probs = torch.softmax(logits, dim=-1)
        ranked = torch.argsort(probs, descending=True).tolist()
        seeds = [i for i in ranked if i not in specials][:NUM_SUGGESTIONS]

        confidence = float(probs[seeds[0]]) if seeds else 0.0

        suggestions = []
        for seed in seeds:
            phrase = self._extend(next_logits, vocab, specials, prefix_ids, seed)
            if phrase and phrase not in suggestions:
                suggestions.append(phrase)

        return {
            "suggestions": suggestions,
            "confidence": round(confidence, 4),
            "model": "RNN-LSTM",
            "context_tokens": tokens,
        }

    @staticmethod
    def _extend(next_logits, vocab, specials, prefix_ids, first_token):
        """Greedily grow a phrase from a seed word until <eos> or max length."""
        ids = list(prefix_ids) + [first_token]
        words = [vocab.decode_token(first_token)]
        for _ in range(MAX_PHRASE_WORDS - 1):
            nxt = int(next_logits(ids).argmax())
            if nxt == vocab.eos_index or nxt in specials:
                break
            ids.append(nxt)
            words.append(vocab.decode_token(nxt))
        return " ".join(words)
