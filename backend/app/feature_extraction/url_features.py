"""Handcrafted phishing-related features extracted from URLs."""

import ipaddress
import math
import re
from urllib.parse import SplitResult, urlsplit


class URLFeatureExtractor:
    """Extract lexical and structural features from a URL."""

    _SUSPICIOUS_KEYWORDS = (
        "account",
        "auth",
        "banking",
        "billing",
        "confirm",
        "login",
        "password",
        "paypal",
        "secure",
        "sign-in",
        "signin",
        "support",
        "update",
        "verify",
        "wallet",
    )

    def extract(self, url: str) -> dict[str, int | float | bool]:
        """Return URL, hostname, entropy, and keyword features."""
        parsed = self._parse_url(url)
        domain = parsed.hostname or ""
        labels = [label for label in domain.rstrip(".").split(".") if label]
        is_ip_address = self._detect_ip_address(domain)

        try:
            has_port = parsed.port is not None
        except ValueError:
            has_port = False

        return {
            "url_length": len(url),
            "domain_length": len(domain),
            "path_length": len(parsed.path),
            "query_length": len(parsed.query),
            "fragment_length": len(parsed.fragment),
            "num_dots": url.count("."),
            "num_hyphens": url.count("-"),
            "num_underscores": url.count("_"),
            "num_slashes": url.count("/"),
            "num_digits": sum(character.isdigit() for character in url),
            "num_special_chars": self._count_special_characters(url),
            "has_https": parsed.scheme.lower() == "https",
            "has_ip_address": is_ip_address,
            "num_subdomains": max(0, len(labels) - 2) if not is_ip_address else 0,
            "has_port": has_port,
            "has_query": bool(parsed.query),
            "has_fragment": bool(parsed.fragment),
            "domain_entropy": self._calculate_entropy(domain),
            "url_entropy": self._calculate_entropy(url),
            "suspicious_keywords": self._count_keywords(url),
        }

    def _parse_url(self, url: str) -> SplitResult:
        """Parse a URL, treating a scheme-less hostname as an authority."""
        normalized_url = url
        if "://" not in url and not url.startswith("//"):
            normalized_url = f"//{url}"
        return urlsplit(normalized_url)

    def _calculate_entropy(self, value: str) -> float:
        """Calculate Shannon entropy in bits per character."""
        if not value:
            return 0.0

        length = len(value)
        frequencies = {character: value.count(character) for character in set(value)}
        return -sum(
            (frequency / length) * math.log2(frequency / length)
            for frequency in frequencies.values()
        )

    def _count_special_characters(self, value: str) -> int:
        """Count characters that are not letters or digits."""
        return sum(not character.isalnum() for character in value)

    def _detect_ip_address(self, hostname: str) -> bool:
        """Return whether a hostname is a valid IPv4 or IPv6 address."""
        if not hostname:
            return False
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            return False
        return True

    def _count_keywords(self, value: str) -> int:
        """Count case-insensitive occurrences of suspicious URL keywords."""
        lowered_value = value.lower()
        return sum(
            len(re.findall(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lowered_value))
            for keyword in self._SUSPICIOUS_KEYWORDS
        )