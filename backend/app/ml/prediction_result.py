"""Structured output from a phishing prediction."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PredictionResult:
    """Binary prediction and its associated class probabilities."""

    prediction: int
    label: str
    confidence: float
    phishing_probability: float
    legitimate_probability: float