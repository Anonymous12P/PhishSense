"""Coordinate the placeholder stages of the scan-analysis pipeline."""

import logging
from typing import Any

from app.core.logger import LOGGER_NAME
from app.feature_extraction.dom_features import DOMFeatureExtractor
from app.feature_extraction.url_features import URLFeatureExtractor
from app.feature_extraction.visual_features import VisualFeatureExtractor
from app.models.scan import Scan
from app.repositories.scan_repository import ScanRepository
from app.services.website_capture import WebsiteCaptureService


logger = logging.getLogger(LOGGER_NAME)


class ScanOrchestrator:
    """Run scan analysis stages and track their transient execution state."""

    def __init__(self, repository: ScanRepository) -> None:
        self.repository = repository
        self.dom_feature_extractor = DOMFeatureExtractor()
        self.url_feature_extractor = URLFeatureExtractor()
        self.visual_feature_extractor = VisualFeatureExtractor()
        self.website_capture_service = WebsiteCaptureService()

    async def run_scan(self, scan_id: int) -> Scan:
        """Run all placeholder analysis stages for a persisted scan.

        The current Scan model has no mapped status or error fields, so these
        values are attached to the in-memory model instance only. Persisting
        them requires a future model and database migration change.
        """
        scan = self.repository.get_by_id(scan_id)
        if scan is None:
            raise ValueError(f"Scan {scan_id} was not found")

        self._set_scan_state(scan, "PROCESSING")
        try:
            url_features = self._extract_url_features(scan.url)
            capture = await self._capture_website(scan.url)
            dom_features = self._extract_dom_features(capture)
            visual_features = self._generate_visual_embedding(capture)
            prediction = self._predict(
                url_features,
                dom_features,
                visual_features,
            )
            self._generate_explanation(prediction)
        except Exception as exc:
            self._set_scan_state(scan, "FAILED", str(exc))
            logger.exception("Scan pipeline failed for scan_id=%s", scan_id)
            raise

        self._set_scan_state(scan, "COMPLETED")
        return scan

    @staticmethod
    def _set_scan_state(
        scan: Scan,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Attach transient status metadata to the current Scan instance."""
        scan.status = status
        scan.error_message = error_message

    def _extract_url_features(self, url: str) -> dict[str, Any]:
        """Extract URL features and keep them in the current pipeline run."""
        return self.url_feature_extractor.extract(url)

    async def _capture_website(self, url: str) -> dict[str, Any]:
        """Capture webpage artifacts for downstream analysis stages."""
        return await self.website_capture_service.capture(url)

    def _extract_dom_features(self, capture: dict[str, Any]) -> dict[str, Any]:
        """Extract DOM features and retain them for this pipeline run."""
        return self.dom_feature_extractor.extract(
            capture["html"],
            capture["final_url"],
        )

    def _generate_visual_embedding(self, capture: dict[str, Any]) -> dict[str, Any]:
        """Generate visual features from the captured screenshot."""
        return self.visual_feature_extractor.extract(capture["screenshot_path"])

    def _predict(
        self,
        url_features: dict[str, Any],
        dom_features: dict[str, Any],
        visual_features: dict[str, Any],
    ) -> dict[str, Any]:
        """Return placeholder prediction data without running a model."""
        return {
            "prediction": "unknown",
            "confidence": 0.0,
            "risk_score": 0.0,
        }

    def _generate_explanation(self, prediction: dict[str, Any]) -> str:
        """Return a placeholder explanation for a prediction."""
        return "Explanation generation is not implemented yet."