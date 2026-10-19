"""Normalize, validate, and deduplicate downloaded URL datasets."""

import csv
import logging
from pathlib import Path
from typing import Iterator, TextIO
from urllib.parse import urlsplit, urlunsplit

from app.core.logger import LOGGER_NAME
from app.dataset.constants import (
    DATASET_LABELS,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
)
from app.dataset.validator import DatasetValidator


logger = logging.getLogger(LOGGER_NAME)


class DatasetCleaner:
    """Clean one public source into a normalized labeled CSV file."""

    def __init__(
        self,
        raw_dir: Path = RAW_DATA_DIR,
        processed_dir: Path = PROCESSED_DATA_DIR,
        validator: DatasetValidator | None = None,
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.validator = validator or DatasetValidator()

    def clean_all(self) -> dict[str, Path]:
        """Clean every source file that exists in the raw directory."""
        cleaned: dict[str, Path] = {}
        for source, filename in (
            ("phishtank", "phishtank.csv"),
            ("openphish", "openphish.txt"),
            ("tranco", "tranco.csv"),
        ):
            input_path = self.raw_dir / filename
            if input_path.is_file():
                cleaned[source] = self.clean_source(source, input_path)
        return cleaned

    def clean_source(self, source: str, input_path: Path) -> Path:
        """Clean a source file and write normalized URL, label, and source rows."""
        normalized_source = source.lower()
        if normalized_source not in DATASET_LABELS:
            raise ValueError(f"Unsupported dataset source: {source}")

        label, source_name = DATASET_LABELS[normalized_source]
        output_path = self.processed_dir / f"{normalized_source}_clean.csv"
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        seen: set[str] = set()

        with Path(input_path).open("r", encoding="utf-8-sig", newline="", errors="replace") as source_file:
            candidates = self._iter_candidates(normalized_source, source_file)
            with output_path.open("w", encoding="utf-8", newline="") as output_file:
                writer = csv.DictWriter(
                    output_file,
                    fieldnames=("url", "label", "source"),
                )
                writer.writeheader()
                for candidate in candidates:
                    normalized_url = self.normalize_url(candidate, normalized_source)
                    if (
                        normalized_url is None
                        or not self.validator.validate(normalized_url)
                        or normalized_url in seen
                    ):
                        continue
                    seen.add(normalized_url)
                    writer.writerow(
                        {"url": normalized_url, "label": label, "source": source_name}
                    )

        logger.info("Cleaned %s URLs into %s", len(seen), output_path)
        return output_path

    def normalize_url(self, candidate: str, source: str) -> str | None:
        """Canonicalize a web URL and add HTTPS to bare Tranco domains."""
        value = candidate.strip().strip("\ufeff")
        if not value:
            return None
        if source == "tranco" and "://" not in value:
            value = f"https://{value}"

        try:
            parsed = urlsplit(value)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                return None
            hostname = parsed.hostname.encode("idna").decode("ascii").lower()
            port = parsed.port
        except (UnicodeError, ValueError):
            return None

        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        netloc = hostname
        if parsed.username is not None:
            credentials = parsed.username
            if parsed.password is not None:
                credentials += f":{parsed.password}"
            netloc = f"{credentials}@{netloc}"
        default_port = 443 if parsed.scheme.lower() == "https" else 80
        if port is not None and port != default_port:
            netloc = f"{netloc}:{port}"

        path = parsed.path or "/"
        return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))

    def _iter_candidates(
        self,
        source: str,
        source_file: TextIO,
    ) -> Iterator[str]:
        """Yield URL values from each source's raw file format."""
        if source == "openphish":
            for line in source_file:
                yield line.strip()
            return

        reader = csv.reader(source_file)
        first_row = True
        phishtank_url_index = 0
        for row in reader:
            if not row:
                continue
            if source == "phishtank":
                if first_row and any(cell.strip().lower() == "url" for cell in row):
                    phishtank_url_index = next(
                        index
                        for index, cell in enumerate(row)
                        if cell.strip().lower() == "url"
                    )
                    first_row = False
                    continue
                first_row = False
                if len(row) > phishtank_url_index:
                    yield row[phishtank_url_index].strip()
            elif source == "tranco":
                first_row = False
                candidate = row[1] if len(row) > 1 else row[0]
                yield candidate.strip()