"""Generate normalized CLIP embeddings from captured webpage screenshots."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, TypedDict

import numpy as np
import torch
from PIL import Image, UnidentifiedImageError


logger = logging.getLogger(__name__)

_MODEL_NAME = "ViT-B-32"
_PRETRAINED_WEIGHTS = "laion2b_s34b_b79k"
_EMBEDDING_SIZE = 512
_SUPPORTED_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


class VisualFeatureResult(TypedDict):
    """CLIP embedding and metadata returned for an image."""

    embedding: list[float]
    embedding_size: int
    model: str
    image_loaded: bool


class MissingScreenshotError(FileNotFoundError):
    """Raised when the requested screenshot does not exist."""


class UnsupportedImageFormatError(ValueError):
    """Raised when the screenshot format is unsupported by the extractor."""


class CorruptedScreenshotError(ValueError):
    """Raised when the screenshot cannot be decoded as an image."""


class VisualModelLoadError(RuntimeError):
    """Raised when the configured CLIP model cannot be loaded."""


@lru_cache(maxsize=2)
def _load_model(device_name: str) -> tuple[Any, Callable[[Image.Image], Any]]:
    """Load and cache one CLIP model and preprocessing transform per device."""
    try:
        import open_clip

        model, _, preprocess = open_clip.create_model_and_transforms(
            _MODEL_NAME,
            pretrained=_PRETRAINED_WEIGHTS,
        )
        model = model.to(torch.device(device_name))
        model.eval()
        return model, preprocess
    except Exception as exc:
        raise VisualModelLoadError(
            f"Could not load {_MODEL_NAME} with {_PRETRAINED_WEIGHTS} on {device_name}"
        ) from exc


class VisualFeatureExtractor:
    """Load a shared CLIP model and extract normalized image embeddings."""

    def extract(self, screenshot_path: str) -> VisualFeatureResult:
        """Return a normalized CLIP image embedding for a screenshot file."""
        image_path = Path(screenshot_path)
        if not image_path.is_file():
            raise MissingScreenshotError(f"Screenshot does not exist: {screenshot_path}")
        if image_path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
            raise UnsupportedImageFormatError(
                f"Unsupported screenshot format: {image_path.suffix or '<none>'}"
            )

        try:
            with Image.open(image_path) as source_image:
                if source_image.format not in {
                    "BMP",
                    "GIF",
                    "JPEG",
                    "PNG",
                    "TIFF",
                    "WEBP",
                }:
                    raise UnsupportedImageFormatError(
                        f"Unsupported screenshot format: {source_image.format}"
                    )
                image = source_image.convert("RGB")
        except UnidentifiedImageError as exc:
            raise CorruptedScreenshotError(
                f"Screenshot is not a readable image: {screenshot_path}"
            ) from exc
        except OSError as exc:
            raise CorruptedScreenshotError(
                f"Screenshot could not be decoded: {screenshot_path}"
            ) from exc

        device_name = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            model, preprocess = _load_model(device_name)
        except VisualModelLoadError:
            if device_name != "cuda":
                raise
            logger.warning("CLIP model failed to load on CUDA; falling back to CPU")
            device_name = "cpu"
            model, preprocess = _load_model(device_name)

        try:
            image_tensor = preprocess(image).unsqueeze(0).to(torch.device(device_name))
            with torch.inference_mode():
                image_features = model.encode_image(image_tensor)
                image_features = image_features / image_features.norm(
                    dim=-1,
                    keepdim=True,
                ).clamp_min(1e-12)
            embedding_array = (
                image_features.squeeze(0)
                .detach()
                .to(device="cpu", dtype=torch.float32)
                .numpy()
            )
        except Exception as exc:
            raise RuntimeError("Could not generate a CLIP screenshot embedding") from exc

        embedding = np.asarray(embedding_array, dtype=np.float32).reshape(-1)
        if embedding.size != _EMBEDDING_SIZE:
            raise RuntimeError(
                f"Expected {_EMBEDDING_SIZE} embedding values, received {embedding.size}"
            )

        return VisualFeatureResult(
            embedding=embedding.tolist(),
            embedding_size=int(embedding.size),
            model=_MODEL_NAME,
            image_loaded=True,
        )