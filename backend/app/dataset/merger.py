"""Merge cleaned labeled URL sources into the pipeline dataset."""

import csv
import logging
from pathlib import Path
from typing import Iterable

from app.core.logger import LOGGER_NAME
from app.dataset.constants import CSV_FIELDS, DATASET_LABELS, PROCESSED_DATA_DIR


logger = logging.getLogger(LOGGER_NAME)


class DatasetMerger:
    """Combine cleaned source CSVs and deduplicate URLs globally."""

    def __init__(self, processed_dir: Path = PROCESSED_DATA_DIR) -> None:
        self.processed_dir = Path(processed_dir)

    def merge(
        self,
        cleaned_paths: Iterable[Path] | None = None,
        output_path: Path | None = None,
    ) -> Path:
        """Write the merged dataset, retaining positive labels on conflicts."""
        paths = list(cleaned_paths) if cleaned_paths is not None else [
            self.processed_dir / f"{source}_clean.csv"
            for source in DATASET_LABELS
        ]
        destination = Path(output_path) if output_path else self.processed_dir / "urls.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)

        merged: dict[str, dict[str, str]] = {}
        for path in paths:
            if not Path(path).is_file():
                continue
            with Path(path).open("r", encoding="utf-8", newline="") as source_file:
                for row in csv.DictReader(source_file):
                    url = (row.get("url") or "").strip()
                    source = (row.get("source") or "").strip()
                    if not url or not source:
                        continue
                    label = "1" if row.get("label", "0").strip() == "1" else "0"
                    if url not in merged:
                        merged[url] = {
                            "url": url,
                            "label": label,
                            "source": source,
                        }
                        continue

                    current = merged[url]
                    current_sources = current["source"].split(";")
                    if source not in current_sources:
                        current_sources.append(source)
                        current["source"] = ";".join(current_sources)
                    if label == "1":
                        current["label"] = "1"

        with destination.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(merged.values())

        logger.info("Merged %s unique URLs into %s", len(merged), destination)
        return destination