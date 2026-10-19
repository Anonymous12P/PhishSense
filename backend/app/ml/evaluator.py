"""Evaluate trained phishing classifiers on held-out samples."""

from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.ml.metrics import EvaluationMetrics


class ModelEvaluator:
    """Compute standard binary classification quality metrics."""

    def evaluate(
        self,
        model: Any,
        features: NDArray[np.float64],
        labels: NDArray[np.int64],
    ) -> EvaluationMetrics:
        """Calculate scalar metrics, confusion matrix, and class report."""
        from sklearn.metrics import (
            accuracy_score,
            classification_report,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )

        predictions = np.asarray(model.predict(features), dtype=np.int64)
        probabilities = np.asarray(model.predict_proba(features))[:, 1]
        return {
            "accuracy": float(accuracy_score(labels, predictions)),
            "precision": float(
                precision_score(labels, predictions, zero_division=0)
            ),
            "recall": float(recall_score(labels, predictions, zero_division=0)),
            "f1_score": float(f1_score(labels, predictions, zero_division=0)),
            "roc_auc": float(roc_auc_score(labels, probabilities)),
            "confusion_matrix": confusion_matrix(
                labels,
                predictions,
                labels=[0, 1],
            ).astype(int).tolist(),
            "classification_report": classification_report(
                labels,
                predictions,
                labels=[0, 1],
                target_names=["legitimate", "phishing"],
                zero_division=0,
            ),
        }