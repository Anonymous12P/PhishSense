"""Build multimodal training data by processing merged URL records."""

import asyncio
import csv
import json
import logging
import os
import time
from pathlib import Path
from typing import TypedDict

from app.core.logger import LOGGER_NAME
from app.dataset.constants import PROCESSED_DATA_DIR
from app.feature_extraction.dom_features import DOMFeatureExtractor
from app.feature_extraction.url_features import URLFeatureExtractor
from app.feature_extraction.visual_features import VisualFeatureExtractor
from app.ml.dataset_builder import DatasetBuilder
from app.services.website_capture import WebsiteCaptureService


logger = logging.getLogger(LOGGER_NAME)
URL_DATASET_PATH = PROCESSED_DATA_DIR / "urls.csv"
DEFAULT_WORKER_COUNT = 20
CHECKPOINT_INTERVAL = 500
PROGRESS_INTERVAL = 100
QUEUE_MULTIPLIER = 2


class DatasetBuildStats(TypedDict):
    """Counts for one dataset-building run."""

    processed: int
    succeeded: int
    failed: int


class DatasetRunner:
    """Capture and extract multimodal features for each labeled URL."""

    def __init__(
        self,
        input_path: Path = URL_DATASET_PATH,
        dataset_builder: DatasetBuilder | None = None,
        website_capture_service: WebsiteCaptureService | None = None,
        url_feature_extractor: URLFeatureExtractor | None = None,
        dom_feature_extractor: DOMFeatureExtractor | None = None,
        visual_feature_extractor: VisualFeatureExtractor | None = None,
    ) -> None:
        self.input_path = Path(input_path)
        self.dataset_builder = dataset_builder or DatasetBuilder()
        self.website_capture_service = website_capture_service or WebsiteCaptureService()
        self.url_feature_extractor = url_feature_extractor or URLFeatureExtractor()
        self.dom_feature_extractor = dom_feature_extractor or DOMFeatureExtractor()
        self.visual_feature_extractor = visual_feature_extractor or VisualFeatureExtractor()
        self.processed = 0
        self.succeeded = 0
        self.failed = 0
        self.worker_count = self._configured_worker_count()
        self.checkpoint_path = self.dataset_builder.output_path.with_suffix(
            ".checkpoint.json"
        )
        self.processed_urls: set[str] = set()
        self.failed_urls: dict[str, str] = {}
        self.last_processed_row = 0
        self._run_processed = 0
        self._started_at = 0.0
        self._total_rows = 0
        self._semaphore: asyncio.Semaphore | None = None

    def _empty_dom_features(self) -> dict[str, int | bool]:
        """Return zeroed DOM features when webpage capture is unavailable."""
        return {
            "form_count": 0,
            "login_forms": 0,
            "password_fields": 0,
            "hidden_inputs": 0,
            "empty_action_forms": 0,
            "external_action_forms": 0,
            "total_links": 0,
            "external_links": 0,
            "internal_links": 0,
            "ip_links": 0,
            "suspicious_link_text": 0,
            "script_count": 0,
            "external_scripts": 0,
            "inline_scripts": 0,
            "obfuscated_js": 0,
            "iframe_count": 0,
            "hidden_iframes": 0,
            "meta_refresh": False,
            "favicon_present": False,
            "image_count": 0,
            "external_images": 0,
            "mixed_content": False,
            "suspicious_js_events": 0,
        }

    @staticmethod
    def _configured_worker_count() -> int:
        """Read the worker count from the environment, defaulting to six."""
        raw_value = os.getenv("PHISHSENSE_DATASET_WORKERS", str(DEFAULT_WORKER_COUNT))
        try:
            worker_count = int(raw_value)
        except ValueError as exc:
            raise ValueError(
                "PHISHSENSE_DATASET_WORKERS must be a positive integer"
            ) from exc
        if worker_count < 1:
            raise ValueError("PHISHSENSE_DATASET_WORKERS must be a positive integer")
        return worker_count

    def _empty_visual_features(
        self,
    ) -> dict[str, list[float] | int | str | bool]:
        """Return a zeroed CLIP embedding when no screenshot is available."""
        return {
            "embedding": [0.0] * 512,
            "embedding_size": 512,
            "model": "ViT-B-32",
            "image_loaded": False,
        }

    async def build_dataset(self) -> DatasetBuildStats:
        """Build the dataset concurrently, checkpointing every 100 rows."""
        self._total_rows = self._count_input_rows()
        checkpoint = self._load_checkpoint()
        self.dataset_builder.start(resume=checkpoint is not None)
        self._restore_checkpoint(checkpoint)
        checkpoint_urls = set(self.processed_urls)
        self.processed_urls.update(self.dataset_builder.known_urls)
        recovered_urls = self.processed_urls - checkpoint_urls
        self.processed += len(recovered_urls)
        self.succeeded += len(recovered_urls)
        self._run_processed = 0
        self._started_at = time.perf_counter()
        self._semaphore = asyncio.Semaphore(self.worker_count)

        if len(self.processed_urls) >= self._total_rows:
            self.dataset_builder.flush()
            self._save_checkpoint()
            self._log_progress()
            return self._stats()

        queue: asyncio.Queue[tuple[int, dict[str, str | None]] | None] = asyncio.Queue(
            maxsize=self.worker_count * QUEUE_MULTIPLIER
        )
        tasks: list[asyncio.Task[None]] = []
        capture_started = False

        try:
            await self.website_capture_service.start()
            capture_started = True
            tasks = [
                asyncio.create_task(self._worker(queue))
                for _ in range(self.worker_count)
            ]
            producer = asyncio.create_task(self._produce_rows(queue))
            tasks.append(producer)
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            try:
                self.dataset_builder.flush()
                self._save_checkpoint()
            finally:
                if capture_started:
                    await self.website_capture_service.close()

        logger.info(
            "Dataset build complete: processed=%s succeeded=%s failed=%s",
            self.processed,
            self.succeeded,
            self.failed,
        )
        return self._stats()

    def _count_input_rows(self) -> int:
        """Count rows in a streaming pass and validate the input schema."""
        with self.input_path.open("r", encoding="utf-8-sig", newline="") as source_file:
            reader = csv.DictReader(source_file)
            required_columns = {"url", "label", "source"}
            if reader.fieldnames is None or not required_columns.issubset(reader.fieldnames):
                raise ValueError("Input dataset must contain url,label,source columns")
            return sum(1 for _ in reader)

    async def _produce_rows(
        self,
        queue: asyncio.Queue[tuple[int, dict[str, str | None]] | None],
    ) -> None:
        """Stream unprocessed input rows into the bounded worker queue."""
        with self.input_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as source_file:
            reader = csv.DictReader(source_file)
            for row_number, row in enumerate(reader, start=1):
                url = (row.get("url") or "").strip()
                if url in self.processed_urls:
                    continue
                await queue.put((row_number, row))

        for _ in range(self.worker_count):
            await queue.put(None)

    async def _worker(
        self,
        queue: asyncio.Queue[tuple[int, dict[str, str | None]] | None],
    ) -> None:
        """Process queued rows independently without stopping on row errors."""
        while True:
            work_item = await queue.get()
            try:
                if work_item is None:
                    return
                row_number, row = work_item
                await self._process_row(row_number, row)
            except Exception as exc:
                url = (work_item[1].get("url") or "").strip() if work_item else ""
                row_number = work_item[0] if work_item else 0
                reason = self._concise_reason(exc)
                self._record_failure(url, reason, row_number)
                logger.warning("Skipping %s: %s", url or "invalid URL", reason)
            finally:
                queue.task_done()

    async def _process_row(
        self,
        row_number: int,
        row: dict[str, str | None],
    ) -> None:
        """Extract one row, substituting defaults when capture or modalities fail."""
        url = (row.get("url") or "").strip()
        label = int(row.get("label") or "")
        source = (row.get("source") or "").strip()
        if not url or not source or label not in (0, 1):
            raise ValueError("Input row has an invalid URL, label, or source")

        url_features = await asyncio.to_thread(
            self.url_feature_extractor.extract,
            url,
        )
        failure_reason: str | None = None
        capture_result = None
        try:
            if self._semaphore is None:
                raise RuntimeError("Dataset workers have not been initialized")
            async with self._semaphore:
                capture_result = await self.website_capture_service.capture(url)
        except Exception as exc:
            failure_reason = self._concise_reason(exc)
            dom_features = self._empty_dom_features()
            visual_features = self._empty_visual_features()
            logger.warning(
                "Skipping capture for %s: %s; using default DOM and visual features",
                url,
                failure_reason,
            )
        else:
            try:
                dom_features = await asyncio.to_thread(
                    self.dom_feature_extractor.extract,
                    capture_result["html"],
                    capture_result["final_url"],
                )
            except Exception as exc:
                failure_reason = self._concise_reason(exc)
                dom_features = self._empty_dom_features()
                logger.warning(
                    "Using default DOM features for %s: %s",
                    url,
                    failure_reason,
                )

            try:
                visual_features = await asyncio.to_thread(
                    self.visual_feature_extractor.extract,
                    capture_result["screenshot_path"],
                )
            except Exception as exc:
                failure_reason = failure_reason or self._concise_reason(exc)
                visual_features = self._empty_visual_features()
                logger.warning(
                    "Using default visual features for %s: %s",
                    url,
                    self._concise_reason(exc),
                )
            try:
                Path(capture_result["screenshot_path"]).unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(
                    "Could not remove screenshot for %s: %s",
                    url,
                    self._concise_reason(exc),
                )

        self.dataset_builder.append_sample(
            url,
            label,
            source,
            url_features,
            dom_features,
            visual_features,
        )
        self._complete_row(row_number, url, failure_reason)

    def _complete_row(
        self,
        row_number: int,
        url: str,
        failure_reason: str | None,
    ) -> None:
        """Update counters and checkpoint/progress at the configured interval."""
        self.processed += 1
        self._run_processed += 1
        self.last_processed_row = max(self.last_processed_row, row_number)
        self.processed_urls.add(url)
        if failure_reason is None:
            self.succeeded += 1
        else:
            self.failed += 1
            self.failed_urls[url] = failure_reason

        self._report_progress_if_due()

    def _record_failure(self, url: str, reason: str, row_number: int) -> None:
        """Count a row-level failure and retain its concise reason for resume."""
        self.processed += 1
        self._run_processed += 1
        self.failed += 1
        self.failed_urls[url] = reason
        if url:
            self.processed_urls.add(url)
        self.last_processed_row = max(self.last_processed_row, row_number)
        self._report_progress_if_due()

    def _report_progress_if_due(self) -> None:
        """Flush checkpoints every 500 rows and log progress every 100."""
        if self._run_processed % CHECKPOINT_INTERVAL == 0:
            logger.info("Saving checkpoint...")
            self.dataset_builder.flush()
            self._save_checkpoint()
        if self._run_processed % PROGRESS_INTERVAL == 0:
            self._log_progress()

    def _load_checkpoint(self) -> dict[str, object] | None:
        """Load a compatible checkpoint or return None for a fresh run."""
        if not self.checkpoint_path.is_file():
            return None
        try:
            with self.checkpoint_path.open("r", encoding="utf-8") as checkpoint_file:
                checkpoint = json.load(checkpoint_file)
            if (
                checkpoint.get("input_csv") != str(self.input_path.resolve())
                or checkpoint.get("output_csv")
                != str(self.dataset_builder.output_path.resolve())
                or not self.dataset_builder.output_path.is_file()
            ):
                return None
            return checkpoint
        except (OSError, json.JSONDecodeError, AttributeError) as exc:
            logger.warning("Ignoring invalid dataset checkpoint: %s", exc)
            return None

    def _restore_checkpoint(self, checkpoint: dict[str, object] | None) -> None:
        """Restore completed URL and counter state from a compatible checkpoint."""
        self.processed_urls.clear()
        self.failed_urls.clear()
        self.last_processed_row = 0
        self.processed = 0
        self.succeeded = 0
        self.failed = 0
        if checkpoint is None:
            return

        raw_processed_urls = checkpoint.get("processed_urls", [])
        if isinstance(raw_processed_urls, list):
            self.processed_urls.update(
                url for url in raw_processed_urls if isinstance(url, str)
            )
        raw_failed_urls = checkpoint.get("failed_urls", [])
        if isinstance(raw_failed_urls, list):
            self.failed_urls.update(
                {
                    item["url"]: item["reason"]
                    for item in raw_failed_urls
                    if isinstance(item, dict)
                    and isinstance(item.get("url"), str)
                    and isinstance(item.get("reason"), str)
                }
            )
        self.last_processed_row = self._checkpoint_integer(
            checkpoint.get("last_processed_row"),
            0,
        )
        self.processed = self._checkpoint_integer(
            checkpoint.get("processed"),
            len(self.processed_urls),
        )
        self.succeeded = self._checkpoint_integer(checkpoint.get("succeeded"), 0)
        self.failed = self._checkpoint_integer(
            checkpoint.get("failed"),
            len(self.failed_urls),
        )

    @staticmethod
    def _checkpoint_integer(value: object, default: int) -> int:
        """Read a non-negative integer from untrusted checkpoint JSON."""
        if isinstance(value, int) and value >= 0:
            return value
        return default

    def _save_checkpoint(self) -> None:
        """Atomically persist progress after flushing the dataset output."""
        self.dataset_builder.flush()
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.checkpoint_path.with_suffix(
            self.checkpoint_path.suffix + ".tmp"
        )
        checkpoint = {
            "last_processed_row": self.last_processed_row,
            "processed_urls": sorted(self.processed_urls),
            "output_csv": str(self.dataset_builder.output_path.resolve()),
            "input_csv": str(self.input_path.resolve()),
            "failed_urls": [
                {"url": url, "reason": reason}
                for url, reason in self.failed_urls.items()
            ],
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
        }
        with temporary_path.open("w", encoding="utf-8") as checkpoint_file:
            json.dump(checkpoint, checkpoint_file, ensure_ascii=False)
            checkpoint_file.flush()
            os.fsync(checkpoint_file.fileno())
        temporary_path.replace(self.checkpoint_path)

    def _log_progress(self) -> None:
        """Log counts, throughput, and estimated remaining time."""
        elapsed = max(time.perf_counter() - self._started_at, 0.001)
        speed = self._run_processed / elapsed
        remaining = max(self._total_rows - self.processed, 0)
        eta_seconds = remaining / speed if speed > 0 else 0.0
        logger.info(
            "Processed: %s / %s\nSucceeded: %s\nFailed: %s\n"
            "Current speed: %.1f URLs/sec\nEstimated remaining time: %s",
            self.processed,
            self._total_rows,
            self.succeeded,
            self.failed,
            speed,
            self._format_duration(eta_seconds),
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format a remaining-time estimate for progress logs."""
        total_seconds = max(int(seconds), 0)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds_left = divmod(remainder, 60)
        if hours:
            return f"{hours}h {minutes}m"
        if minutes:
            return f"{minutes}m {seconds_left}s"
        return f"{seconds_left}s"

    @staticmethod
    def _concise_reason(error: Exception) -> str:
        """Return a single-line failure reason suitable for logs/checkpoints."""
        message = str(error).splitlines()[0].strip() if str(error) else type(error).__name__
        return message[:240]

    def _stats(self) -> DatasetBuildStats:
        """Return a detached snapshot of the current run counters."""
        return {
            "processed": self.processed,
            "succeeded": self.succeeded,
            "failed": self.failed,
        }