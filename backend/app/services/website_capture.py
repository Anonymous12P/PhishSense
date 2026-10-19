"""Load webpages with Chromium and collect artifacts for scan analysis."""

import time
from pathlib import Path
from typing import TypedDict
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

from playwright.async_api import (
    Browser,
    Error as PlaywrightError,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)


class WebsiteCaptureResult(TypedDict):
    """Collected page metadata and artifacts returned by a capture."""

    final_url: str
    title: str
    html: str
    status_code: int | None
    response_headers: dict[str, str]
    favicon_url: str | None
    page_load_time: float
    screenshot_path: str


class WebsiteCaptureError(RuntimeError):
    """Raised when Chromium cannot capture a requested website."""


class WebsiteCaptureService:
    """Capture webpage metadata and a full-page screenshot using Chromium."""

    def __init__(
        self,
        timeout_ms: int = 10_000,
        screenshot_dir: Path | None = None,
    ) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be greater than zero")

        self.timeout_ms = timeout_ms
        self.screenshot_dir = screenshot_dir or (
            Path(__file__).resolve().parents[3] / "storage" / "screenshots"
        )
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    async def start(self) -> None:
        """Launch Chromium once for reuse across concurrent captures."""
        if self._browser is not None and self._browser.is_connected():
            return

        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch()
        except PlaywrightError as exc:
            await self.close()
            raise WebsiteCaptureError(
                "Could not launch Chromium for website capture"
            ) from exc

    async def close(self) -> None:
        """Close the shared browser and Playwright driver if they are running."""
        browser = self._browser
        playwright = self._playwright
        self._browser = None
        self._playwright = None
        try:
            if browser is not None:
                await browser.close()
        finally:
            if playwright is not None:
                await playwright.stop()

    async def capture(self, url: str) -> WebsiteCaptureResult:
        """Navigate to a valid HTTP(S) URL and return its page artifacts."""
        self._validate_url(url)
        owns_browser = self._browser is None or not self._browser.is_connected()
        if owns_browser:
            await self.start()

        browser = self._browser
        if browser is None:
            raise WebsiteCaptureError("Chromium browser is not available")

        context = None
        try:
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            page.set_default_timeout(self.timeout_ms)
            page.set_default_navigation_timeout(self.timeout_ms)
            started_at = time.perf_counter()
            try:
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout_ms,
                )
            except PlaywrightTimeoutError as exc:
                raise TimeoutError(
                    f"Navigation timed out after {self.timeout_ms} ms"
                ) from exc
            except PlaywrightError as exc:
                raise self._navigation_error(exc) from exc

            status_code = response.status if response is not None else None
            if status_code is not None and status_code >= 400:
                raise WebsiteCaptureError(f"HTTP error {status_code}")

            page_load_time = time.perf_counter() - started_at
            final_url = page.url
            title = await page.title()
            html = await page.content()
            response_headers = dict(response.headers) if response is not None else {}
            favicon_href = await page.evaluate(
                """() => {
                    const icon = document.querySelector(
                        'link[rel~="icon"], link[rel="shortcut icon"]'
                    );
                    return icon ? icon.href : null;
                }"""
            )
            favicon_url = urljoin(final_url, favicon_href) if favicon_href else None

            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = self.screenshot_dir / f"{uuid4().hex}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)

            return WebsiteCaptureResult(
                final_url=final_url,
                title=title,
                html=html,
                status_code=status_code,
                response_headers=response_headers,
                favicon_url=favicon_url,
                page_load_time=page_load_time,
                screenshot_path=str(screenshot_path),
            )
        finally:
            try:
                if context is not None:
                    await context.close()
            finally:
                if owns_browser:
                    await self.close()

    @staticmethod
    def _validate_url(url: str) -> None:
        """Reject malformed URLs and non-HTTP(S) schemes before launch."""
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme.lower() in {"http", "https"}
                and parsed.hostname is not None
            )
            if valid:
                parsed.port
        except ValueError as exc:
            raise ValueError("A valid HTTP or HTTPS URL is required") from exc

        if not valid:
            raise ValueError("A valid HTTP or HTTPS URL is required")

    @staticmethod
    def _navigation_error(error: PlaywrightError) -> WebsiteCaptureError:
        """Translate common Chromium network errors into clear capture errors."""
        message = str(error)
        normalized_message = message.lower()
        if any(
            marker in normalized_message
            for marker in ("name_not_resolved", "dns", "name resolution")
        ):
            return WebsiteCaptureError(f"DNS resolution failed: {message}")
        if any(
            marker in normalized_message
            for marker in ("cert_", "ssl", "certificate")
        ):
            return WebsiteCaptureError(f"SSL validation failed: {message}")
        return WebsiteCaptureError(f"Website navigation failed: {message}")