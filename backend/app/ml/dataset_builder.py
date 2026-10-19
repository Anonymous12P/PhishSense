"""Append multimodal URL samples to the PhishSense training dataset."""

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.dataset.constants import PROCESSED_DATA_DIR
from app.ml.feature_fusion import FEATURE_ORDER, FeatureFusion


OUTPUT_DATASET_PATH = PROCESSED_DATA_DIR / "processed_dataset.csv"
METADATA_FIELDS = ("url", "label", "source")
DATASET_FIELDS = METADATA_FIELDS + FEATURE_ORDER
OUTPUT_FLUSH_INTERVAL = 500


class DatasetBuilder:
    """Fuse features and append samples to the model-training CSV."""

    def __init__(
        self,
        output_path: Path = OUTPUT_DATASET_PATH,
        feature_fusion: FeatureFusion | None = None,
    ) -> None:
        self.output_path = Path(output_path)
        self.feature_fusion = feature_fusion or FeatureFusion()
        self._buffer: list[dict[str, str | int | float]] = []
        self._known_urls: set[str] = set()
        self._initialized = False

    def start(self, resume: bool = False) -> None:
        """Prepare the output file for a new run or resume an existing one."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._buffer.clear()
        self._known_urls.clear()

        if resume and self.output_path.is_file() and self.output_path.stat().st_size:
            if self._read_header() != list(DATASET_FIELDS):
                raise ValueError(
                    f"Dataset header does not match expected schema: {self.output_path}"
                )
            with self.output_path.open("r", encoding="utf-8", newline="") as dataset_file:
                for row in csv.DictReader(dataset_file):
                    url = (row.get("url") or "").strip()
                    if url:
                        self._known_urls.add(url)
        else:
            with self.output_path.open("w", encoding="utf-8", newline="") as output_file:
                csv.writer(output_file).writerow(DATASET_FIELDS)

        self._initialized = True

    def append_sample(
        self,
        url: str,
        label: int,
        source: str,
        url_features: Mapping[str, Any],
        dom_features: Mapping[str, Any],
        visual_features: Mapping[str, Any],
    ) -> None:
        """Append one URL and its fixed-order fused features to the CSV."""
        if not self._initialized:
            self.start(resume=True)
        if label not in (0, 1):
            raise ValueError("label must be either 0 or 1")
        if url in self._known_urls:
            return

        fused_features = self.feature_fusion.fuse(
            url_features,
            dom_features,
            visual_features,
        )
        row: dict[str, str | int | float] = {
            "url": url,
            "label": label,
            "source": source,
        }
        row.update(zip(FEATURE_ORDER, fused_features, strict=True))
        self._buffer.append(row)
        self._known_urls.add(url)
        if len(self._buffer) >= OUTPUT_FLUSH_INTERVAL:
            self.flush()

    def flush(self) -> None:
        """Write buffered samples to disk and flush them to the filesystem."""
        if not self._buffer:
            return
        if not self._initialized:
            self.start(resume=True)

        with self.output_path.open("a", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=DATASET_FIELDS)
            writer.writerows(self._buffer)
            output_file.flush()
        self._buffer.clear()

    @property
    def known_urls(self) -> set[str]:
        """Return the URLs already written or queued for output."""
        return self._known_urls

    def _read_header(self) -> list[str] | None:
        """Read the existing CSV header to prevent incompatible appends."""
        with self.output_path.open("r", encoding="utf-8", newline="") as dataset_file:
            return next(csv.reader(dataset_file), None)