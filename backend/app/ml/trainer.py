"""
Train and evaluate the PhishSense XGBoost phishing classifier.
"""

import csv
import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from app.core.logger import LOGGER_NAME
from app.ml.evaluator import ModelEvaluator
from app.ml.feature_fusion import FEATURE_ORDER
from app.ml.metrics import EvaluationMetrics, MetricsWriter

logger = logging.getLogger(LOGGER_NAME)

BACKEND_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATASET_PATH = (
    BACKEND_ROOT
    / "datasets"
    / "processed"
    / "processed_dataset.csv"
)

DEFAULT_MODEL_PATH = (
    BACKEND_ROOT
    / "models"
    / "phishing_xgboost.json"
)


@dataclass(slots=True)
class TrainingResult:
    model: Any
    metrics: EvaluationMetrics
    model_path: Path
    metrics_path: Path
    classification_report_path: Path
    x_test: NDArray[np.float64]
    y_test: NDArray[np.int64]


class XGBoostTrainer:

    def __init__(
        self,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        model_path: Path = DEFAULT_MODEL_PATH,
        evaluator: ModelEvaluator | None = None,
        metrics_writer: MetricsWriter | None = None,
    ):
        self.dataset_path = Path(dataset_path)
        self.model_path = Path(model_path)
        self.evaluator = evaluator or ModelEvaluator()
        self.metrics_writer = metrics_writer or MetricsWriter()

    #######################################################################
    # LOAD DATASET
    #######################################################################

    def load_dataset(self):

        if not self.dataset_path.exists():
            raise FileNotFoundError(self.dataset_path)

        features = []
        labels = []

        with self.dataset_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:

            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise ValueError("Dataset header missing.")

            missing = [
                f
                for f in FEATURE_ORDER
                if f not in reader.fieldnames
            ]

            if missing:
                raise ValueError(
                    f"Missing feature columns: {missing}"
                )

            for row in reader:

                label = int(row["label"])

                sample = []

                for feature in FEATURE_ORDER:

                    value = row.get(feature, "").strip()

                    if value == "":
                        sample.append(np.nan)

                    else:
                        sample.append(float(value))

                labels.append(label)
                features.append(sample)

        X = np.asarray(features, dtype=np.float64)
        y = np.asarray(labels, dtype=np.int64)

        logger.info("Dataset Loaded")
        logger.info("Samples : %d", len(y))
        logger.info("Features: %d", len(FEATURE_ORDER))
        logger.info(
            "Benign : %d",
            int(np.sum(y == 0))
        )
        logger.info(
            "Phishing : %d",
            int(np.sum(y == 1))
        )

        return X, y

    #######################################################################
    # TRAIN
    #######################################################################

    def train(self):

        from sklearn.model_selection import train_test_split
        from xgboost import XGBClassifier

        X, y = self.load_dataset()

        x_train, x_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=42,
            stratify=y,
        )

        logger.info("Training samples : %d", len(y_train))
        logger.info("Testing samples  : %d", len(y_test))

        model = XGBClassifier(

            n_estimators=600,

            max_depth=8,

            learning_rate=0.05,

            subsample=0.85,

            colsample_bytree=0.85,

            min_child_weight=3,

            gamma=0.20,

            reg_alpha=0.10,

            reg_lambda=1.0,

            objective="binary:logistic",

            eval_metric=["logloss", "auc"],

            tree_method="hist",

            missing=np.nan,

            random_state=42,

            n_jobs=-1,

            verbosity=1,
        )

        logger.info("Training XGBoost model...")

        model.fit(
            x_train,
            y_train,
            eval_set=[(x_test, y_test)],
            verbose=False,
        )

        ##########################################################

        self.model_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        model.save_model(str(self.model_path))

        logger.info(
            "Model saved -> %s",
            self.model_path,
        )

        ##########################################################

        metrics = self.evaluator.evaluate(
            model,
            x_test,
            y_test,
        )

        metrics_path, report_path = (
            self.metrics_writer.write(metrics)
        )

        ##########################################################
        # Save Feature Importance
        ##########################################################

        importance = {}

        for feature, score in zip(
            FEATURE_ORDER,
            model.feature_importances_,
        ):
            importance[feature] = float(score)

        importance_path = (
            self.model_path.parent
            / "feature_importance.json"
        )

        with importance_path.open(
            "w",
            encoding="utf-8",
        ) as fp:
            json.dump(
                importance,
                fp,
                indent=4,
            )

        logger.info(
            "Feature importance saved."
        )

        ##########################################################

        return TrainingResult(
            model=model,
            metrics=metrics,
            model_path=self.model_path,
            metrics_path=metrics_path,
            classification_report_path=report_path,
            x_test=x_test,
            y_test=y_test,
        )