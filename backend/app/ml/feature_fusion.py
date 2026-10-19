"""Combine URL, DOM, and visual features in a stable model input order."""

from collections.abc import Mapping
from numbers import Real
from typing import Any


URL_FEATURE_ORDER = (
    "url_length",
    "domain_length",
    "path_length",
    "query_length",
    "fragment_length",
    "num_dots",
    "num_hyphens",
    "num_underscores",
    "num_slashes",
    "num_digits",
    "num_special_chars",
    "has_https",
    "has_ip_address",
    "num_subdomains",
    "has_port",
    "has_query",
    "has_fragment",
    "domain_entropy",
    "url_entropy",
    "suspicious_keywords",
)
DOM_FEATURE_ORDER = (
    "form_count",
    "login_forms",
    "password_fields",
    "hidden_inputs",
    "empty_action_forms",
    "external_action_forms",
    "total_links",
    "external_links",
    "internal_links",
    "ip_links",
    "suspicious_link_text",
    "script_count",
    "external_scripts",
    "inline_scripts",
    "obfuscated_js",
    "iframe_count",
    "hidden_iframes",
    "meta_refresh",
    "favicon_present",
    "image_count",
    "external_images",
    "mixed_content",
    "suspicious_js_events",
)
EMBEDDING_SIZE = 512
EMBEDDING_FEATURE_ORDER = tuple(
    f"embedding_{index}" for index in range(EMBEDDING_SIZE)
)
FEATURE_ORDER = URL_FEATURE_ORDER + DOM_FEATURE_ORDER + EMBEDDING_FEATURE_ORDER


class FeatureFusion:
    """Create a fixed-order numeric vector from multimodal features."""

    feature_order = FEATURE_ORDER

    def fuse(
        self,
        url_features: Mapping[str, Any],
        dom_features: Mapping[str, Any],
        visual_features: Mapping[str, Any],
    ) -> list[float]:
        """Merge URL and DOM features, then append the CLIP embedding."""
        embedding = visual_features.get("embedding")
        if not isinstance(embedding, (list, tuple)) or len(embedding) != EMBEDDING_SIZE:
            actual_size = len(embedding) if isinstance(embedding, (list, tuple)) else None
            raise ValueError(
                f"CLIP embedding must contain {EMBEDDING_SIZE} values; got {actual_size}"
            )

        values: list[float] = []
        values.extend(self._ordered_values(url_features, URL_FEATURE_ORDER))
        values.extend(self._ordered_values(dom_features, DOM_FEATURE_ORDER))
        values.extend(self._numeric_values(embedding, EMBEDDING_FEATURE_ORDER))
        return values

    def _ordered_values(
        self,
        features: Mapping[str, Any],
        names: tuple[str, ...],
    ) -> list[float]:
        """Read required named values in declared order, ignoring extra keys."""
        missing = [name for name in names if name not in features]
        if missing:
            raise ValueError(f"Missing required features: {', '.join(missing)}")
        return self._numeric_values([features[name] for name in names], names)

    def _numeric_values(
        self,
        values: list[Any] | tuple[Any, ...],
        names: tuple[str, ...],
    ) -> list[float]:
        """Convert numeric and boolean features to model-ready floats."""
        converted: list[float] = []
        for name, value in zip(names, values, strict=True):
            if isinstance(value, bool):
                converted.append(float(value))
            elif isinstance(value, Real):
                converted.append(float(value))
            else:
                raise ValueError(f"Feature {name!r} must be numeric or boolean")
        return converted