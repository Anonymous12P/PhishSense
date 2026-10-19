"""Load and cache the trained phishing classifier."""

import logging
from functools import lru_cache
from pathlib import Path

from xgboost import XGBClassifier

from app.core.logger import LOGGER_NAME


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = BACKEND_ROOT / "models" / "phishing_xgboost.json"
logger = logging.getLogger(LOGGER_NAME)


class ModelLoader:
    """Load the XGBoost model once per artifact path."""

    def __init__(self, model_path: Path = DEFAULT_MODEL_PATH) -> None:
        self.model_path = Path(model_path)

    def load(self) -> XGBClassifier:
        """Return the cached model, loading and validating the artifact as needed."""
        return self._load_cached(str(self.model_path.resolve()))

    @staticmethod
    @lru_cache(maxsize=4)
    def _load_cached(model_path: str) -> XGBClassifier:
        path = Path(model_path)
        if not path.is_file():
            message = f"Phishing model not found: {path}"
            logger.error(message)
            raise FileNotFoundError(message)

        model = XGBClassifier()
        try:
            model.load_model(str(path))
        except Exception as exc:
            message = f"Unable to load phishing model at {path}: {exc}"
            logger.exception(message)
            raise ValueError(message) from exc

        logger.info("Loaded phishing model from %s", path)
        return model

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached models, primarily for controlled reloads and tests."""
        cls._load_cached.cache_clear()