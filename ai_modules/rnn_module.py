"""Stub RNN contextual text-prediction module.

The real implementation (PyTorch) will replace ``TextPredictor.predict()``
in a later sprint. For now it returns canned phrase suggestions so the
pipeline is testable.
"""
import random


class TextPredictor:
    """Suggests next phrases given the current text context."""

    _PHRASES = [
        ["quiero agua", "quiero comer", "necesito ayuda"],
        ["estoy bien", "me duele algo", "tengo sueño"],
        ["gracias", "por favor", "hablamos más tarde"],
    ]

    def predict(self, context):
        """context: current text / list of words. Returns suggested phrases."""
        suggestions = random.choice(self._PHRASES)
        return {
            "suggestions": suggestions,
            "confidence": round(random.uniform(0.70, 0.95), 3),
        }
