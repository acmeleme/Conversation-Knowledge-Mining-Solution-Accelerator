"""
Local E2E + Resilience tests for Entra ID authentication.

These tests are self-contained: a Python mock HTTP server serves the React
build and simulates Azure EasyAuth (/.auth/me), so no live Azure deployment
is required.  Tests pass after frontend/backend restart by design.

Success criteria:
  C1: No demo role selector visible (app auto-auths via /.auth/me)
  C2: No "Demo" text visible anywhere in the UI
  C3: Avatar shows real Entra ID user (name from /.auth/me claims)
  C4: No "Visitante" card on login screen
  C5: No "Acesso Negado" screen for a valid authenticated user

Resilience criteria:
  R1: Auth persists after page reload
  R2: Re-auth works after localStorage cleared + reload
  R3: Fresh browser context auto-auths (stateless)
"""

from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from pytest_check import check

from pages.authPage import AuthPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MOCK_PORT = 8765
MOCK_HOST = "127.0.0.1"
APP_URL = f"http://{MOCK_HOST}:{MOCK_PORT}"

# Path to the React SPA build (served by the mock server)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BUILD_DIR = _REPO_ROOT / "src" / "App" / "build"

# Mock Entra ID principal returned by /.auth/me
MOCK_AUTH_ME = [
    {
        "user_id": "rodrigoleme@microsoft.com",
        "user_claims": [
            {"typ": "name", "val": "Rodrigo Leme"},
            {"typ": "preferred_username", "val": "rodrigoleme@microsoft.com"},
            {
                "typ": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                "val": "00000000-0000-0000-0000-mock-entra-id",
            },
        ],
        "identity_provider": "aad",
    }
]
EXPECTED_USER_NAME = "Rodrigo Leme"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mock HTTP server
# ---------------------------------------------------------------------------

class MockAppHandler(BaseHTTPRequestHandler):
    """Serves the React SPA and mocks all Azure EasyAuth / API endpoints."""

    def log_message(self, fmt, *args):  # suppress server logs during tests
        pass

    def _send_json(self, data, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path: Path):
        ext = file_path.suffix.lower()
        mime = {
            ".html": "text/html; charset=utf-8",
            ".js":   "application/javascript",
            ".css":  "text/css",
            ".json": "application/json",
            ".png":  "image/png",
            ".svg":  "image/svg+xml",
            ".ico":  "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf":  "font/ttf",
        }.get(ext, "application/octet-stream")

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _spa_fallback(self):
        index = BUILD_DIR / "index.html"
        if index.exists():
            self._send_file(index)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        # EasyAuth endpoints (both absolute and relative URL patterns)
        if path in ("/.auth/me", "/APP_API_BASE_URL/.auth/me"):
            self._send_json(MOCK_AUTH_ME)
            return

        if path in ("/.auth/refresh", "/APP_API_BASE_URL/.auth/refresh"):
            self._send_json({"status": "ok"})
            return

        # API stubs — return empty data so no static "Demo" content appears
        if "history/list" in path:
            self._send_json([])
            return

        if "fetchChartData" in path or "chart" in path.lower():
            self._send_json({"data": []})
            return

        if "fetchFilterData" in path or "filter" in path.lower():
            self._send_json({})
            return

        if "layoutConfig" in path or "layout" in path.lower():
            self._send_json({})
            return

        if "fetchConversation" in path or "conversation" in path.lower():
            self._send_json([])
            return

        # Static assets from the React build
        # Strip leading "/"
        rel = path.lstrip("/")

        # Try exact match in build dir first
        candidate = BUILD_DIR / rel
        if rel and candidate.exists() and candidate.is_file():
            self._send_file(candidate)
            return

        # SPA fallback: any unknown path → index.html
        self._spa_fallback()

    def do_POST(self):
        path = urlparse(self.path).path
        # Consume body to avoid broken-pipe errors
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)

        if "chat" in path or "message" in path:
            self._send_json({"answer": "mock answer", "data_points": [], "thoughts": ""})
            return

        self._send_json({"status": "ok"})


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mock_server():
    """Start the mock HTTP server in a background thread for all tests in this module."""
    server = HTTPServer((MOCK_HOST, MOCK_PORT), MockAppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Mock server running at {APP_URL}")
    yield server
    server.shutdown()
    logger.info("Mock server stopped.")


@pytest.fixture(scope="module")
def browser_module():
    """Launch a single browser for the whole module."""
    with sync_playwright() as p:
        browser: Browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def authed_page(mock_server, browser_module):
    """
    Single authenticated page shared across C1–C5 tests.
    The mock server provides /.auth/me so EasyAuth works without Azure.
    """
    context: BrowserContext = browser_module.new_context()
    context.set_default_timeout(30_000)
    page: Page = context.new_page()
    page.goto(APP_URL, wait_until="domcontentloaded")

    auth = AuthPage(page)
    auth.wait_for_app_loaded(timeout=20_000)

    yield page

    context.close()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _open_popover_if_needed(auth: AuthPage):
    if not auth.is_profile_popover_visible():
        auth.click_avatar()
        auth.page.wait_for_timeout(600)


# ---------------------------------------------------------------------------
# C1–C5: Core success criteria
# ---------------------------------------------------------------------------

class TestEntraAuthCriteria:
    """C1–C5: Core authentication and UI criteria."""

    def test_c1_no_demo_role_selector(self, authed_page):
        """C1: App auto-auths via Entra ID — demo role selector must not appear."""
        auth = AuthPage(authed_page)
        result = auth.is_role_selector_visible()
        check.equal(result, False, "Demo role selector must not be visible for Entra ID session.")
        logger.info(f"C1 role_selector_visible={result}")

    def test_c2_no_demo_text(self, authed_page):
        """C2: No 'Demo' text visible anywhere in the UI."""
        auth = AuthPage(authed_page)
        # Wait a moment for any async rendering
        authed_page.wait_for_timeout(500)
        result = auth.is_demo_text_visible()
        check.equal(result, False, "The literal text 'Demo' must not appear in the UI.")
        logger.info(f"C2 demo_text_visible={result}")

    def test_c3_avatar_shows_entra_user(self, authed_page):
        """C3: Avatar popover shows the Entra ID user name (not Dev Local fallback)."""
        auth = AuthPage(authed_page)
        _open_popover_if_needed(auth)

        visible = auth.is_profile_popover_visible()
        check.is_true(visible, "Profile popover must open after clicking the avatar.")

        displayed = auth.get_displayed_user_name()
        logger.info(f"C3 displayed_name={displayed!r}")

        check.not_equal(displayed, "", "Displayed user name must not be empty.")
        check.not_equal(displayed, "Dev Local", "Must not show local dev fallback.")
        check.not_equal(displayed, "Usuário Demo", "Must not show legacy demo label.")
        check.is_true(
            EXPECTED_USER_NAME in displayed or displayed == EXPECTED_USER_NAME,
            f"Expected '{EXPECTED_USER_NAME}' in popover, got {displayed!r}",
        )

    def test_c4_no_visitante_card(self, authed_page):
        """C4: No 'Visitante' card on login screen."""
        auth = AuthPage(authed_page)
        if not auth.is_role_selector_visible():
            logger.info("C4: Role selector not visible (Entra ID session). Passes vacuously.")
            return
        result = auth.is_visitor_card_visible()
        check.equal(result, False, "'Visitante' card must not appear on login screen.")

    def test_c5_no_access_denied(self, authed_page):
        """C5: No 'Acesso Negado' screen for a valid authenticated user."""
        auth = AuthPage(authed_page)
        result = auth.is_access_denied_visible()
        check.equal(result, False, "Authenticated users with valid role must not see 'Acesso Negado'.")
        logger.info(f"C5 access_denied_visible={result}")


# ---------------------------------------------------------------------------
# R1–R3: Resilience tests
# ---------------------------------------------------------------------------

class TestResilience:
    """R1–R3: Resilience — auth survives restarts, clears, and fresh contexts."""

    def test_r1_reload_preserves_auth(self, mock_server, browser_module):
        """R1: Auth state persists after page reload (simulates frontend restart)."""
        context = browser_module.new_context()
        context.set_default_timeout(30_000)
        page = context.new_page()
        try:
            page.goto(APP_URL, wait_until="domcontentloaded")
            auth = AuthPage(page)
            auth.wait_for_app_loaded(timeout=20_000)

            # Reload simulates frontend restart
            page.reload(wait_until="domcontentloaded")
            auth.wait_for_app_loaded(timeout=20_000)

            result = auth.is_role_selector_visible()
            check.equal(result, False, "R1: After reload, Entra ID session must still be active.")
            logger.info(f"R1 role_selector_visible_after_reload={result}")
        finally:
            context.close()

    def test_r2_localStorage_clear_reauths(self, mock_server, browser_module):
        """R2: Clearing localStorage and reloading re-authenticates via /.auth/me."""
        context = browser_module.new_context()
        context.set_default_timeout(30_000)
        page = context.new_page()
        try:
            page.goto(APP_URL, wait_until="domcontentloaded")
            auth = AuthPage(page)
            auth.wait_for_app_loaded(timeout=20_000)

            # Clear all local storage (simulates cache wipe)
            page.evaluate("() => { try { localStorage.clear(); } catch(e) {} }")
            page.reload(wait_until="domcontentloaded")
            auth.wait_for_app_loaded(timeout=20_000)

            result = auth.is_role_selector_visible()
            check.equal(result, False, "R2: After localStorage clear + reload, EasyAuth must re-authenticate.")

            demo_visible = auth.is_demo_text_visible()
            check.equal(demo_visible, False, "R2: No 'Demo' text after re-auth.")
            logger.info(f"R2 role_selector={result} demo_text={demo_visible}")
        finally:
            context.close()

    def test_r3_fresh_context_authed(self, mock_server, browser_module):
        """R3: A brand-new browser context auto-auths (stateless — no shared state)."""
        context = browser_module.new_context()
        context.set_default_timeout(30_000)
        page = context.new_page()
        try:
            page.goto(APP_URL, wait_until="domcontentloaded")
            auth = AuthPage(page)
            auth.wait_for_app_loaded(timeout=20_000)

            result = auth.is_role_selector_visible()
            check.equal(result, False, "R3: Fresh context must auto-auth via Entra ID (EasyAuth is stateless).")

            demo_visible = auth.is_demo_text_visible()
            check.equal(demo_visible, False, "R3: No 'Demo' text in fresh context.")
            logger.info(f"R3 role_selector={result} demo_text={demo_visible}")
        finally:
            context.close()
