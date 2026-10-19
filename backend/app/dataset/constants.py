"""Shared dataset source URLs, paths, labels, and CSV field names."""

import os
from pathlib import Path


DATASET_DIR = Path(__file__).resolve().parents[2] / "datasets"
RAW_DATA_DIR = DATASET_DIR / "raw"
PROCESSED_DATA_DIR = DATASET_DIR / "processed"

PHISHTANK_URL = os.environ.get(
    "PHISHTANK_DATASET_URL",
    "https://data.phishtank.com/data/online-valid.csv",
)
OPENPHISH_URL = os.environ.get(
    "OPENPHISH_DATASET_URL",
    "https://openphish.com/feed.txt",
)
TRANCO_URL = os.environ.get(
    "TRANCO_DATASET_URL",
    "https://tranco-list.eu/top-1m.csv.zip",
)

DATASET_LABELS = {
    "phishtank": (1, "PhishTank"),
    "openphish": (1, "OpenPhish"),
    "tranco": (0, "Tranco"),
}
CSV_FIELDS = ("url", "label", "source")
