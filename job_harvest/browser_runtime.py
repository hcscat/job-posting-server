from __future__ import annotations

import os
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency at runtime
    sync_playwright = None


COMMON_BROWSER_PATHS = (
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
)


def browser_runtime_available() -> bool:
    return sync_playwright is not None


def resolve_browser_executable() -> str | None:
    env_path = os.getenv("JOB_HARVEST_BROWSER_EXECUTABLE", "").strip()
    if env_path and Path(env_path).exists():
        return env_path
    for candidate in COMMON_BROWSER_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


class BrowserSession:
    def __init__(self, *, user_agent: str, headless: bool, timeout_seconds: int) -> None:
        self._user_agent = user_agent
        self._headless = headless
        self._timeout_ms = timeout_seconds * 1000
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def __enter__(self) -> "BrowserSession":
        if sync_playwright is None:
            raise RuntimeError("Playwright is not installed.")
        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, object] = {"headless": self._headless}
        executable = resolve_browser_executable()
        if executable:
            launch_kwargs["executable_path"] = executable
        self.browser = self._playwright.chromium.launch(**launch_kwargs)
        self.context = self.browser.new_context(user_agent=self._user_agent, locale="ko-KR")
        self.page = self.context.new_page()
        self.page.set_default_timeout(self._timeout_ms)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.page is not None:
            self.page.close()
        if self.context is not None:
            self.context.close()
        if self.browser is not None:
            self.browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def goto_html(self, url: str, wait_ms: int = 3000) -> tuple[str, int]:
        response = self.page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
        if wait_ms > 0:
            self.page.wait_for_timeout(wait_ms)
        status_code = response.status if response is not None else 0
        return self.page.content(), status_code

    def fetch_text(self, url: str, init: dict[str, object] | None = None) -> str:
        return self.page.evaluate(
            """async ({ targetUrl, options }) => {
                const response = await fetch(targetUrl, {
                    credentials: "include",
                    ...(options || {}),
                });
                return await response.text();
            }""",
            {"targetUrl": url, "options": init or {}},
        )
