"""Generate phishing predictions from fused feature vectors."""

import logging
from collections.abc import Sequence
from math import isinf
from numbers import Real

import numpy as np
from numpy.typing import NDArray

from app.core.logger import LOGGER_NAME
from app.ml.feature_fusion import FEATURE_ORDER
from app.ml.model_loader import ModelLoader
from app.ml.prediction_result import PredictionResult


logger = logging.getLogger(LOGGER_NAME)


class PhishingPredictor:
    """Classify fused URL, DOM, and visual features with the trained model."""

    def __init__(self, model_loader: ModelLoader | None = None) -> None:
        self.model_loader = model_loader or ModelLoader()

    def predict(self, fused_features: Sequence[Real]) -> PredictionResult:
        """Validate one fused vector and return its phishing prediction."""
        if len(fused_features) != len(FEATURE_ORDER):
            raise ValueError(
                f"Expected {len(FEATURE_ORDER)} fused features; "
                f"got {len(fused_features)}"
            )

        for index, value in enumerate(fused_features):
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"Feature at index {index} must be numeric")
            if isinf(float(value)):
                raise ValueError(f"Feature at index {index} must not be infinite")

        features: NDArray[np.float64] = np.asarray(
            fused_features,
            dtype=np.float64,
        ).reshape(1, -1)
        model = self.model_loader.load()
        probabilities = np.asarray(model.predict_proba(features), dtype=np.float64)
        if probabilities.shape != (1, 2):
            raise ValueError(
                "Phishing model must return probabilities for exactly two classes; "
                f"got shape {probabilities.shape}"
            )

        classes = np.asarray(model.classes_)
        if classes.shape != (2,) or set(classes.tolist()) != {0, 1}:
            raise ValueError("Phishing model must be trained with labels 0 and 1")
        legitimate_probability = float(probabilities[0, int(np.where(classes == 0)[0][0])])
        phishing_probability = float(probabilities[0, int(np.where(classes == 1)[0][0])])
        prediction = int(model.predict(features)[0])
        if prediction not in (0, 1):
            raise ValueError(f"Phishing model returned invalid prediction: {prediction}")

        result = PredictionResult(
            prediction=prediction,
            label="phishing" if prediction == 1 else "legitimate",
            confidence=max(phishing_probability, legitimate_probability),
            phishing_probability=phishing_probability,
            legitimate_probability=legitimate_probability,
        )
        logger.info(
            "Generated %s prediction with confidence %.4f",
            result.label,
            result.confidence,
        )
        return result