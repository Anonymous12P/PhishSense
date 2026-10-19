"""Handcrafted phishing-related structural features from captured HTML."""

import ipaddress
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag


class DOMFeatureExtractor:
    """Extract structural and security indicators from webpage HTML."""

    _SUSPICIOUS_TERMS = (
        "account",
        "bank",
        "billing",
        "confirm",
        "login",
        "password",
        "secure",
        "sign in",
        "signin",
        "update",
        "verify",
        "wallet",
    )
    _OBFUSCATION_PATTERNS = (
        re.compile(r"\beval\s*\(", re.IGNORECASE),
        re.compile(r"\bunescape\s*\(", re.IGNORECASE),
        re.compile(r"\b(?:atob|btoa)\s*\(", re.IGNORECASE),
        re.compile(r"\bString\s*\.\s*fromCharCode\s*\(", re.IGNORECASE),
        re.compile(r"[A-Za-z0-9+/]{120,}={0,2}"),
    )

    def extract(self, html: str, base_url: str) -> dict[str, int | bool]:
        """Parse HTML and return counts and flags relevant to phishing."""
        soup = BeautifulSoup(html or "", "lxml")
        origin = self._origin(base_url)

        forms = soup.find_all("form")
        links = soup.find_all("a", href=True)
        scripts = soup.find_all("script")
        iframes = soup.find_all("iframe")
        images = soup.find_all("img", src=True)

        link_targets = [str(link.get("href", "")) for link in links]
        script_targets = [str(script.get("src", "")) for script in scripts if script.get("src")]
        image_targets = [str(image.get("src", "")) for image in images]

        return {
            "form_count": len(forms),
            "login_forms": self._count_login_forms(forms),
            "password_fields": len(
                soup.find_all("input", attrs={"type": re.compile(r"^password$", re.IGNORECASE)})
            ),
            "hidden_inputs": len(
                soup.find_all("input", attrs={"type": re.compile(r"^hidden$", re.IGNORECASE)})
            ),
            "empty_action_forms": sum(
                not str(form.get("action", "")).strip() for form in forms
            ),
            "external_action_forms": sum(
                self._is_external(str(form.get("action", "")), base_url, origin)
                for form in forms
                if str(form.get("action", "")).strip()
            ),
            "total_links": len(links),
            "external_links": sum(
                self._is_external(target, base_url, origin) for target in link_targets
            ),
            "internal_links": sum(
                self._is_internal(target, base_url, origin)
                for target in link_targets
            ),
            "ip_links": sum(self._has_ip_host(target, base_url) for target in link_targets),
            "suspicious_link_text": self._count_suspicious_link_text(links),
            "script_count": len(scripts),
            "external_scripts": sum(
                self._is_external(target, base_url, origin) for target in script_targets
            ),
            "inline_scripts": sum(not script.get("src") for script in scripts),
            "obfuscated_js": self._count_obfuscated_scripts(scripts),
            "iframe_count": len(iframes),
            "hidden_iframes": sum(self._is_hidden(iframe) for iframe in iframes),
            "meta_refresh": self._has_meta_refresh(soup),
            "favicon_present": self._has_favicon(soup),
            "image_count": len(images),
            "external_images": sum(
                self._is_external(target, base_url, origin) for target in image_targets
            ),
            "mixed_content": self._has_mixed_content(soup, base_url),
            "suspicious_js_events": self._count_js_events(soup),
        }

    def _count_login_forms(self, forms: list[Tag]) -> int:
        """Count forms with a password control or login-related identifiers."""
        count = 0
        for form in forms:
            has_password = form.find(
                "input", attrs={"type": re.compile(r"^password$", re.IGNORECASE)}
            ) is not None
            identifiers = " ".join(
                str(form.get(attribute, ""))
                for attribute in ("id", "name", "class", "autocomplete")
            ).lower()
            if has_password or any(
                marker in identifiers for marker in ("login", "signin", "sign-in", "auth")
            ):
                count += 1
        return count

    def _count_suspicious_link_text(self, links: list[Tag]) -> int:
        """Count links whose visible text contains a suspicious term."""
        return sum(
            any(
                term in link.get_text(" ", strip=True).lower()
                for term in self._SUSPICIOUS_TERMS
            )
            for link in links
        )

    def _count_obfuscated_scripts(self, scripts: list[Tag]) -> int:
        """Count scripts containing common obfuscation indicators."""
        return sum(
            any(
                pattern.search(script.get_text())
                for pattern in self._OBFUSCATION_PATTERNS
            )
            for script in scripts
        )

    def _is_hidden(self, element: Tag) -> bool:
        """Detect hidden elements from attributes, styles, or zero dimensions."""
        if element.has_attr("hidden") or str(element.get("aria-hidden", "")).lower() == "true":
            return True

        style = str(element.get("style", "")).lower().replace(" ", "")
        if "display:none" in style or "visibility:hidden" in style:
            return True

        return any(
            str(element.get(dimension, "")).strip().lower() in {"0", "0px"}
            for dimension in ("width", "height")
        )

    def _has_meta_refresh(self, soup: BeautifulSoup) -> bool:
        """Return whether the document contains a refresh meta directive."""
        return any(
            str(meta.get("http-equiv", "")).strip().lower() == "refresh"
            for meta in soup.find_all("meta")
        )

    def _has_favicon(self, soup: BeautifulSoup) -> bool:
        """Return whether the document declares an icon link."""
        for link in soup.find_all("link", href=True):
            rel = link.get("rel", [])
            rel_values = rel if isinstance(rel, list) else str(rel).split()
            if any("icon" in str(value).lower() for value in rel_values):
                return True
        return False

    def _has_mixed_content(self, soup: BeautifulSoup, base_url: str) -> bool:
        """Detect HTTP resources referenced by an HTTPS page."""
        if urlsplit(base_url).scheme.lower() != "https":
            return False

        resource_attributes = (
            ("script", "src"),
            ("img", "src"),
            ("iframe", "src"),
            ("link", "href"),
            ("audio", "src"),
            ("video", "src"),
            ("source", "src"),
            ("form", "action"),
        )
        return any(
            urlsplit(urljoin(base_url, str(element.get(attribute, "")))).scheme.lower()
            == "http"
            for name, attribute in resource_attributes
            for element in soup.find_all(name)
            if element.get(attribute)
        )

    def _count_js_events(self, soup: BeautifulSoup) -> int:
        """Count inline JavaScript event-handler attributes in the document."""
        return sum(
            1
            for element in soup.find_all(True)
            for attribute in element.attrs
            if re.fullmatch(r"on[a-z]+", str(attribute), re.IGNORECASE)
        )

    def _is_external(
        self,
        target: str,
        base_url: str,
        origin: tuple[str, str, int | None] | None,
    ) -> bool:
        """Return whether a web URL resolves to an origin other than the page."""
        if origin is None:
            return False
        try:
            target_origin = self._origin(urljoin(base_url, target))
        except ValueError:
            return False
        if target_origin is None:
            return False
        return target_origin != origin

    def _is_internal(
        self,
        target: str,
        base_url: str,
        origin: tuple[str, str, int | None] | None,
    ) -> bool:
        """Return whether a web URL resolves to the page's own origin."""
        if origin is None:
            return False
        return self._origin(urljoin(base_url, target)) == origin

    def _has_ip_host(self, target: str, base_url: str) -> bool:
        """Return whether a link resolves to an IPv4 or IPv6 host."""
        try:
            hostname = urlsplit(urljoin(base_url, target)).hostname
            if hostname is None:
                return False
            ipaddress.ip_address(hostname)
        except ValueError:
            return False
        return True

    def _origin(self, url: str) -> tuple[str, str, int | None] | None:
        """Return normalized scheme, host, and port for an absolute URL."""
        try:
            parsed = urlsplit(url)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                return None
            scheme = parsed.scheme.lower()
            port = parsed.port
            if port is None:
                port = 443 if scheme == "https" else 80
            return scheme, parsed.hostname.lower(), port
        except ValueError:
            return None