"""Word-level tokenizer and vocabulary for the AAC RNN model.

Kept dependency-free (pure Python) so it can be imported for tokenization
without pulling in PyTorch. Serialises to/from a plain dict for JSON storage
alongside the model weights.
"""
import re
import unicodedata

# Special tokens. Order matters: PAD must be index 0 so it can be used as the
# CrossEntropyLoss ignore_index and for padding batches.
PAD = "<pad>"
BOS = "<bos>"
EOS = "<eos>"
UNK = "<unk>"
SPECIALS = [PAD, BOS, EOS, UNK]

_TOKEN_RE = re.compile(r"[a-záéíóúüñ]+", re.IGNORECASE)


def tokenize(text):
    """Lowercase and split Spanish text into word tokens.

    Accents are preserved (they are meaningful in Spanish); punctuation and
    digits are dropped. Accepts a str, a list of words, or a dict carrying a
    ``context``/``text``/``words`` field.
    """
    if isinstance(text, dict):
        text = (
            text.get("context")
            or text.get("text")
            or text.get("words")
            or ""
        )
    if isinstance(text, (list, tuple)):
        text = " ".join(str(w) for w in text)
    text = str(text).lower()
    # Normalise to NFC so composed accented chars match the regex reliably.
    text = unicodedata.normalize("NFC", text)
    return _TOKEN_RE.findall(text)


class Vocabulary:
    """Bidirectional word ↔ index mapping."""

    def __init__(self, itos):
        self.itos = list(itos)
        self.stoi = {tok: i for i, tok in enumerate(self.itos)}

    def __len__(self):
        return len(self.itos)

    @property
    def pad_index(self):
        return self.stoi[PAD]

    @property
    def bos_index(self):
        return self.stoi[BOS]

    @property
    def eos_index(self):
        return self.stoi[EOS]

    @property
    def unk_index(self):
        return self.stoi[UNK]

    def encode(self, tokens):
        """Map a list of word tokens to a list of indices (OOV → <unk>)."""
        unk = self.unk_index
        return [self.stoi.get(tok, unk) for tok in tokens]

    def decode_token(self, index):
        return self.itos[index]

    @classmethod
    def build(cls, sentences, min_freq=1):
        """Build a vocabulary from an iterable of token lists."""
        freq = {}
        for tokens in sentences:
            for tok in tokens:
                freq[tok] = freq.get(tok, 0) + 1
        # Deterministic order: by descending frequency, then alphabetically.
        words = sorted(
            (w for w, c in freq.items() if c >= min_freq),
            key=lambda w: (-freq[w], w),
        )
        return cls(SPECIALS + words)

    def to_dict(self):
        return {"itos": self.itos}

    @classmethod
    def from_dict(cls, data):
        return cls(data["itos"])
