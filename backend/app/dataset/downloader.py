"""Download public URL datasets into the configured raw data directory."""

import logging
import shutil
import urllib.request
import zipfile
from pathlib import Path

from app.core.logger import LOGGER_NAME
from app.dataset.constants import (
    OPENPHISH_URL,
    PHISHTANK_URL,
    RAW_DATA_DIR,
    TRANCO_URL,
)

logger = logging.getLogger(LOGGER_NAME)


class DatasetDownloader:
    """Fetch PhishTank, OpenPhish, and Tranco dataset files."""

    def __init__(
        self,
        raw_dir: Path = RAW_DATA_DIR,
        phishtank_url: str = PHISHTANK_URL,
        openphish_url: str = OPENPHISH_URL,
        tranco_url: str = TRANCO_URL,
        timeout: float = 60.0,
    ) -> None:
        self.raw_dir = Path(raw_dir)
        self.phishtank_url = phishtank_url
        self.openphish_url = openphish_url
        self.tranco_url = tranco_url
        self.timeout = timeout

    def download_phishtank(self) -> Path:
        destination = self.raw_dir / "phishtank.csv"

        if destination.exists() and destination.stat().st_size > 0:
            logger.info("Using existing PhishTank dataset: %s", destination)
            return destination

        return self._download(self.phishtank_url, "phishtank.csv")

    def download_openphish(self) -> Path:
        destination = self.raw_dir / "openphish.txt"

        if destination.exists() and destination.stat().st_size > 0:
            logger.info("Using existing OpenPhish dataset: %s", destination)
            return destination

        return self._download(self.openphish_url, "openphish.txt")

    def download_tranco(self) -> Path:
        csv_path = self.raw_dir / "tranco.csv"

        if csv_path.exists() and csv_path.stat().st_size > 0:
            logger.info("Using existing Tranco dataset: %s", csv_path)
            return csv_path

        archive_path = self._download(
            self.tranco_url,
            "tranco-top-1m.csv.zip",
        )

        try:
            with zipfile.ZipFile(archive_path) as archive:
                csv_members = [
                    member
                    for member in archive.infolist()
                    if not member.is_dir()
                    and member.filename.lower().endswith(".csv")
                ]

                if not csv_members:
                    raise ValueError("Tranco archive contains no CSV file")

                with archive.open(csv_members[0]) as source, csv_path.open("wb") as target:
                    shutil.copyfileobj(source, target)

        except (OSError, zipfile.BadZipFile) as exc:
            raise ValueError(
                "Downloaded Tranco file is not a valid CSV archive"
            ) from exc

        logger.info("Extracted Tranco dataset to %s", csv_path)
        return csv_path

    def download_all(self) -> dict[str, Path]:
        return {
            "phishtank": self.download_phishtank(),
            "openphish": self.download_openphish(),
            "tranco": self.download_tranco(),
        }

    def _download(self, url: str, filename: str) -> Path:
        self.raw_dir.mkdir(parents=True, exist_ok=True)

        destination = self.raw_dir / filename
        temporary_path = destination.with_suffix(destination.suffix + ".part")

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                with temporary_path.open("wb") as output:
                    shutil.copyfileobj(response, output)

            temporary_path.replace(destination)

        except Exception:
            temporary_path.unlink(missing_ok=True)
            logger.exception("Dataset download failed for %s", url)
            raise

        logger.info("Downloaded dataset source to %s", destination)
        return destination