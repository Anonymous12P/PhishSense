"""Write model evaluation metrics and classification reports to disk."""

import json
import logging
from pathlib import Path
from typing import TypedDict

from app.core.logger import LOGGER_NAME


logger = logging.getLogger(LOGGER_NAME)
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORTS_DIR = BACKEND_ROOT / "reports"


class EvaluationMetrics(TypedDict):
    """Classification metrics produced from a held-out test set."""

    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    confusion_matrix: list[list[int]]
    classification_report: str


class MetricsWriter:
    """Persist JSON metrics and the text classification report."""

    def __init__(self, reports_dir: Path = DEFAULT_REPORTS_DIR) -> None:
        self.reports_dir = Path(reports_dir)

    def write(self, metrics: EvaluationMetrics) -> tuple[Path, Path]:
        """Write ``metrics.json`` and ``classification_report.txt``."""
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        metrics_path = self.reports_dir / "metrics.json"
        report_path = self.reports_dir / "classification_report.txt"

        json_metrics = {
            key: value
            for key, value in metrics.items()
            if key != "classification_report"
        }
        with metrics_path.open("w", encoding="utf-8") as metrics_file:
            json.dump(json_metrics, metrics_file, indent=2, allow_nan=False)
            metrics_file.write("\n")

        report_path.write_text(metrics["classification_report"], encoding="utf-8")
        logger.info("Wrote model metrics to %s and %s", metrics_path, report_path)
        return metrics_path, report_path