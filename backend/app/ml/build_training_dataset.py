"""Orchestrate public source downloads into the multimodal training dataset."""

import asyncio
import csv
import logging
import os
import random
import shutil
import sqlite3
import tempfile
from pathlib import Path
from typing import TypedDict

from app.core.logger import LOGGER_NAME
from app.dataset.cleaner import DatasetCleaner
from app.dataset.constants import PROCESSED_DATA_DIR, RAW_DATA_DIR
from app.dataset.downloader import DatasetDownloader
from app.dataset.validator import DatasetValidator
from app.ml.dataset_builder import DatasetBuilder
from app.ml.dataset_runner import DatasetBuildStats, DatasetRunner


logger = logging.getLogger(LOGGER_NAME)
SOURCE_NAMES = {
    "phishtank": "PhishTank",
    "tranco": "Tranco",
}
SOURCE_ORDER = tuple(SOURCE_NAMES)
PHISHING_SOURCE_QUOTAS = {"phishtank": 25_000}
TRANCO_STRATA = (
    (1, 1_000, 625),
    (1_001, 10_000, 2_250),
    (10_001, 100_000, 9_375),
    (100_001, 1_000_000, 12_750),
)
TARGET_DATASET_SIZE = 50_000
DEFAULT_SAMPLING_SEED = 42


class TrainingDatasetPipelineResult(TypedDict):
    """Final paths and multimodal build counters from the pipeline."""

    urls_path: str
    training_dataset_path: str
    processed: int
    succeeded: int
    failed: int


class URLDatasetRow(TypedDict):
    """One normalized URL record written to the balanced manifest."""

    url: str
    label: str
    source: str


class TrainingDatasetPipeline:
    """Run download, clean, validation, merge, and feature-building stages."""

    def __init__(
        self,
        raw_dir: Path = RAW_DATA_DIR,
        processed_dir: Path = PROCESSED_DATA_DIR,
        downloader: DatasetDownloader | None = None,
        cleaner: DatasetCleaner | None = None,
        validator: DatasetValidator | None = None,
        merger: object | None = None,
        runner: DatasetRunner | None = None,
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.urls_path = self.processed_dir / "urls.csv"
        self.training_dataset_path = self.processed_dir / "processed_dataset.csv"
        self.legacy_training_dataset_path = self.processed_dir / "phishsense_dataset.csv"
        self.downloader = downloader or DatasetDownloader(raw_dir=self.raw_dir)
        self.cleaner = cleaner or DatasetCleaner(
            raw_dir=self.raw_dir,
            processed_dir=self.processed_dir,
        )
        self.validator = validator or DatasetValidator()
        self.merger = merger
        self.runner = runner
        self.downloaded_paths: dict[str, Path] = {}
        self.cleaned_paths: dict[str, Path] = {}
        self.build_stats: DatasetBuildStats | None = None

    def download_datasets(self) -> dict[str, Path]:
        """Download only the PhishTank and Tranco source files."""
        try:
            downloaded_paths = {
                "phishtank": Path(self.downloader.download_phishtank()),
                "tranco": Path(self.downloader.download_tranco()),
            }
            missing_sources = [source for source in SOURCE_ORDER if source not in downloaded_paths]
            if missing_sources:
                raise ValueError(
                    f"Downloader omitted required sources: {', '.join(missing_sources)}"
                )
            for source in SOURCE_ORDER:
                source_path = Path(downloaded_paths[source])
                if not source_path.is_file():
                    raise FileNotFoundError(
                        f"{SOURCE_NAMES[source]} download is missing: {source_path}"
                    )
                downloaded_paths[source] = source_path
                logger.info("Downloaded %s: %s", SOURCE_NAMES[source], source_path)
        except Exception as exc:
            logger.exception("Dataset download stage failed")
            raise RuntimeError(f"Dataset download stage failed: {exc}") from exc

        self.downloaded_paths = downloaded_paths
        return downloaded_paths

    def clean_datasets(self) -> dict[str, Path]:
        """Clean phishing sources; Tranco is sampled directly by rank."""
        if not self.downloaded_paths:
            raise RuntimeError("Dataset cleaning cannot run before downloads")

        cleaned_paths: dict[str, Path] = {}
        try:
            for source in PHISHING_SOURCE_QUOTAS:
                cleaned_path = Path(
                    self.cleaner.clean_source(source, self.downloaded_paths[source])
                )
                if not cleaned_path.is_file():
                    raise FileNotFoundError(
                        f"{SOURCE_NAMES[source]} cleaned file was not created: {cleaned_path}"
                    )
                cleaned_paths[source] = cleaned_path
                logger.info("Cleaned %s: %s", SOURCE_NAMES[source], cleaned_path)
        except Exception as exc:
            logger.exception("Dataset cleaning stage failed")
            raise RuntimeError(f"Dataset cleaning stage failed: {exc}") from exc

        self.cleaned_paths = cleaned_paths
        return cleaned_paths

    def validate_datasets(self) -> int:
        """Validate cleaned phishing sources before exact-quota sampling."""
        if not self.cleaned_paths:
            raise RuntimeError("Dataset validation cannot run before cleaning")

        validated_count = 0
        try:
            for source in PHISHING_SOURCE_QUOTAS:
                cleaned_path = self.cleaned_paths[source]
                with cleaned_path.open(
                    "r",
                    encoding="utf-8-sig",
                    newline="",
                ) as cleaned_file:
                    reader = csv.DictReader(cleaned_file)
                    if reader.fieldnames is None or "url" not in reader.fieldnames:
                        raise ValueError(
                            f"{SOURCE_NAMES[source]} cleaned CSV has no url column"
                        )
                    for row_number, row in enumerate(reader, start=2):
                        url = (row.get("url") or "").strip()
                        if not self.validator.validate(url):
                            raise ValueError(
                                f"Invalid URL in {SOURCE_NAMES[source]} cleaned CSV "
                                f"at row {row_number}: {url!r}"
                            )
                        validated_count += 1
            logger.info("Validated %s URLs across all cleaned datasets", validated_count)
        except Exception as exc:
            logger.exception("Dataset validation stage failed")
            raise RuntimeError(f"Dataset validation stage failed: {exc}") from exc

        return validated_count

    def merge_datasets(self) -> Path:
        """Write an exact, balanced, stratified, de-duplicated URL manifest."""
        if not self.cleaned_paths:
            raise RuntimeError("Dataset merge cannot run before cleaning and validation")

        try:
            samples = self._sample_phishing_sources()
            phishing_samples = len(samples)
            logger.info("Selected %s phishing URLs", phishing_samples)
            legitimate_samples = self._sample_tranco_sources(samples)
            logger.info("Selected %s legitimate URLs", len(legitimate_samples))
            samples.extend(legitimate_samples)
            if len(samples) != TARGET_DATASET_SIZE:
                raise RuntimeError(
                    f"Balanced sample has {len(samples)} rows; "
                    f"expected {TARGET_DATASET_SIZE}"
                )
            phishing_count = sum(sample["label"] == "1" for sample in samples)
            legitimate_count = sum(sample["label"] == "0" for sample in samples)
            if phishing_count != 25_000 or legitimate_count != 25_000:
                raise RuntimeError(
                    "Balanced dataset must contain exactly 25,000 phishing and "
                    f"25,000 legitimate URLs; got {phishing_count} and "
                    f"{legitimate_count}"
                )

            random.Random(self._sampling_seed()).shuffle(samples)
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            with self.urls_path.open("w", encoding="utf-8", newline="") as output_file:
                writer = csv.writer(output_file)
                writer.writerow(("url", "label", "source"))
                writer.writerows(
                    (sample["url"], sample["label"], sample["source"])
                    for sample in samples
                )
            logger.info("Merged dataset contains %s URLs", len(samples))
            logger.info("Wrote balanced %s-URL manifest to %s", len(samples), self.urls_path)
        except Exception as exc:
            logger.exception("Dataset merge stage failed")
            raise RuntimeError(f"Balanced URL sampling failed: {exc}") from exc

        return self.urls_path

    def _sample_phishing_sources(self) -> list[URLDatasetRow]:
        """Reservoir-sample the requested unique PhishTank URLs."""
        rng = random.Random(self._sampling_seed())
        selected: list[URLDatasetRow] = []
        selected_urls: set[str] = set()

        for source, quota in PHISHING_SOURCE_QUOTAS.items():
            input_path = self.cleaned_paths[source]
            reservoir: list[URLDatasetRow] = []
            candidate_count = 0
            seen_candidates: set[str] = set()
            with input_path.open("r", encoding="utf-8-sig", newline="") as source_file:
                for row in csv.DictReader(source_file):
                    raw_url = (row.get("url") or "").strip()
                    normalized_url = self.cleaner.normalize_url(raw_url, source)
                    if (
                        normalized_url is None
                        or not self.validator.validate(normalized_url)
                        or normalized_url in seen_candidates
                        or normalized_url in selected_urls
                    ):
                        continue
                    seen_candidates.add(normalized_url)
                    candidate_count += 1
                    sample: URLDatasetRow = {
                        "url": normalized_url,
                        "label": "1",
                        "source": SOURCE_NAMES[source],
                    }
                    if len(reservoir) < quota:
                        reservoir.append(sample)
                    else:
                        replacement = rng.randrange(candidate_count)
                        if replacement < quota:
                            reservoir[replacement] = sample

            if len(reservoir) < quota:
                raise ValueError(
                    f"{SOURCE_NAMES[source]} has {len(reservoir)} unique valid URLs; "
                    f"{quota} are required"
                )
            selected.extend(reservoir)
            selected_urls.update(sample["url"] for sample in reservoir)

        return selected

    def _sample_tranco_sources(
        self,
        selected_phishing: list[URLDatasetRow],
    ) -> list[URLDatasetRow]:
        """Sample Tranco URLs by rank while de-duplicating in a temporary DB."""
        tranco_path = self.downloaded_paths["tranco"]
        rng = random.Random(self._sampling_seed())
        quotas = [quota for _, _, quota in TRANCO_STRATA]
        reservoirs: list[list[URLDatasetRow]] = [[] for _ in TRANCO_STRATA]
        candidate_counts = [0 for _ in TRANCO_STRATA]
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=self.processed_dir) as temp_dir:
            database_path = Path(temp_dir) / "seen_urls.sqlite3"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute(
                    "CREATE TABLE seen_urls (url TEXT PRIMARY KEY) WITHOUT ROWID"
                )
                connection.executemany(
                    "INSERT OR IGNORE INTO seen_urls (url) VALUES (?)",
                    ((sample["url"],) for sample in selected_phishing),
                )

                with tranco_path.open(
                    "r",
                    encoding="utf-8-sig",
                    newline="",
                    errors="replace",
                ) as source_file:
                    for row in csv.reader(source_file):
                        if len(row) < 2:
                            continue
                        try:
                            rank = int(row[0].strip())
                        except ValueError:
                            continue
                        stratum_index = next(
                            (
                                index
                                for index, (lower, upper, _) in enumerate(TRANCO_STRATA)
                                if lower <= rank <= upper
                            ),
                            None,
                        )
                        if stratum_index is None:
                            continue

                        normalized_url = self.cleaner.normalize_url(row[1], "tranco")
                        if (
                            normalized_url is None
                            or not self.validator.validate(normalized_url)
                        ):
                            continue
                        inserted = connection.execute(
                            "INSERT OR IGNORE INTO seen_urls (url) VALUES (?)",
                            (normalized_url,),
                        )
                        if inserted.rowcount == 0:
                            continue

                        candidate_counts[stratum_index] += 1
                        sample: URLDatasetRow = {
                            "url": normalized_url,
                            "label": "0",
                            "source": SOURCE_NAMES["tranco"],
                        }
                        quota = quotas[stratum_index]
                        reservoir = reservoirs[stratum_index]
                        if len(reservoir) < quota:
                            reservoir.append(sample)
                        else:
                            replacement = rng.randrange(candidate_counts[stratum_index])
                            if replacement < quota:
                                reservoir[replacement] = sample
            finally:
                connection.close()

        for index, ((lower, upper, quota), reservoir) in enumerate(
            zip(TRANCO_STRATA, reservoirs, strict=True)
        ):
            if len(reservoir) < quota:
                raise ValueError(
                    f"Tranco ranks {lower}-{upper} contain "
                    f"{candidate_counts[index]} unique valid URLs; {quota} are required"
                )

        return [sample for reservoir in reservoirs for sample in reservoir]

    @staticmethod
    def _sampling_seed() -> int:
        """Return the reproducible sampling seed, configurable through env."""
        raw_seed = os.environ.get(
            "PHISHSENSE_DATASET_SEED",
            str(DEFAULT_SAMPLING_SEED),
        )
        try:
            return int(raw_seed)
        except ValueError as exc:
            raise ValueError("PHISHSENSE_DATASET_SEED must be an integer") from exc

    async def build_feature_dataset(self) -> DatasetBuildStats:
        """Run multimodal feature extraction and verify its output artifact."""
        runner = self.runner or DatasetRunner(
            input_path=self.urls_path,
            dataset_builder=DatasetBuilder(output_path=self.training_dataset_path),
        )
        try:
            stats = await runner.build_dataset()
            if not self.training_dataset_path.is_file():
                raise FileNotFoundError(
                    "DatasetRunner completed without creating "
                    f"{self.training_dataset_path}"
                )
            self._sync_legacy_dataset_path()
            self.build_stats = stats
            logger.info("Processed : %s", stats["processed"])
            logger.info("Succeeded : %s", stats["succeeded"])
            logger.info("Failed    : %s", stats["failed"])
            logger.info("Created multimodal dataset: %s", self.training_dataset_path)
        except Exception as exc:
            logger.exception("Multimodal dataset build stage failed")
            raise RuntimeError(f"Multimodal dataset build stage failed: {exc}") from exc

        return stats

    def _sync_legacy_dataset_path(self) -> None:
        """Keep the existing trainer input path aligned with the new output."""
        temporary_path = self.legacy_training_dataset_path.with_suffix(".csv.tmp")
        temporary_path.unlink(missing_ok=True)
        try:
            os.link(self.training_dataset_path, temporary_path)
        except OSError:
            try:
                shutil.copyfile(self.training_dataset_path, temporary_path)
            except OSError as exc:
                logger.warning("Could not update legacy training dataset: %s", exc)
                return
        try:
            os.replace(temporary_path, self.legacy_training_dataset_path)
        except OSError as exc:
            temporary_path.unlink(missing_ok=True)
            logger.warning("Could not update legacy training dataset: %s", exc)

    async def run(self) -> TrainingDatasetPipelineResult:
        """Execute every dataset preparation stage in the required order."""
        logger.info("\n%s\nStarting Dataset Preparation Pipeline\n%s", "=" * 50, "=" * 50)

        logger.info("Downloading datasets...")
        self.download_datasets()

        logger.info("Cleaning datasets...")
        self.clean_datasets()

        logger.info("Validating datasets...")
        self.validate_datasets()
        logger.info("All datasets validated")

        logger.info("Building balanced dataset...")
        self.merge_datasets()
        logger.info("urls.csv created")

        logger.info("Starting feature extraction...")
        stats = await self.build_feature_dataset()

        logger.info("processed_dataset.csv created")
        logger.info("Dataset Preparation Pipeline completed successfully")
        return {
            "urls_path": str(self.urls_path),
            "training_dataset_path": str(self.training_dataset_path),
            "processed": stats["processed"],
            "succeeded": stats["succeeded"],
            "failed": stats["failed"],
        }


async def main() -> None:
    """Run the standalone dataset preparation pipeline."""
    pipeline = TrainingDatasetPipeline()
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())