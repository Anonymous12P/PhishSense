"""Validation helpers for public phishing and legitimate URL datasets."""

import ipaddress
from urllib.parse import urlsplit


class DatasetValidator:
    """Validate that candidate records are syntactically valid web URLs."""

    def validate(self, url: str) -> bool:
        """Return whether a URL has an HTTP(S) scheme and valid host syntax."""
        if not url or url != url.strip() or any(character.isspace() for character in url):
            return False

        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            if parsed.scheme.lower() not in {"http", "https"} or not hostname:
                return False
            parsed.port
        except ValueError:
            return False

        if hostname.startswith(".") or hostname.endswith("."):
            return False

        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            try:
                ascii_hostname = hostname.encode("idna").decode("ascii")
            except UnicodeError:
                return False
            labels = ascii_hostname.split(".")
            if any(
                not label
                or len(label) > 63
                or label.startswith("-")
                or label.endswith("-")
                or not all(character.isalnum() or character == "-" for character in label)
                for label in labels
            ):
                return False

        return True