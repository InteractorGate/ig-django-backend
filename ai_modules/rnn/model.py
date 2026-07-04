"""PyTorch LSTM language model for AAC next-word / phrase prediction.

A compact word-level LSTM: Embedding → LSTM → Linear projection back to the
vocabulary. Small by design (thesis / CPU inference on Azure B1), but a real
trainable recurrent network — not a stub.
"""
import torch
import torch.nn as nn

# Default hyper-parameters. Kept small so the artifact stays a few hundred KB
# and inference is fast on CPU.
DEFAULT_CONFIG = {
    "embed_dim": 64,
    "hidden_dim": 128,
    "num_layers": 1,
    "dropout": 0.2,
}


class PhraseLSTM(nn.Module):
    """Word-level LSTM language model."""

    def __init__(self, vocab_size, pad_index, embed_dim=64, hidden_dim=128,
                 num_layers=1, dropout=0.2):
        super().__init__()
        self.config = {
            "embed_dim": embed_dim,
            "hidden_dim": hidden_dim,
            "num_layers": num_layers,
            "dropout": dropout,
        }
        self.embedding = nn.Embedding(
            vocab_size, embed_dim, padding_idx=pad_index
        )
        self.lstm = nn.LSTM(
            embed_dim,
            hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_dim, vocab_size)

    def forward(self, x, hidden=None):
        """x: (batch, seq_len) token indices.

        Returns logits (batch, seq_len, vocab_size) and the LSTM hidden state.
        """
        emb = self.dropout(self.embedding(x))
        out, hidden = self.lstm(emb, hidden)
        logits = self.fc(self.dropout(out))
        return logits, hidden
