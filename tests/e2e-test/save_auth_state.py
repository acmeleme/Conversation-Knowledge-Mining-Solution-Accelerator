"""
One-time interactive login to capture Entra ID auth state for CI/headless E2E runs.

Usage:
    python save_auth_state.py

What it does:
1. Opens a visible Chrome browser and navigates to the app URL.
2. Waits up to 120 seconds for you to complete the Entra ID login.
3. Saves cookies + localStorage to auth_state.json.
4. Set PLAYWRIGHT_STORAGE_STATE=auth_state.json in .env to enable headless E2E runs.

Auth state typically lasts ~24 hours; re-run when it expires.
"""

import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

URL = os.getenv("url", "https://app-callcenter100.azurewebsites.net")
OUTPUT = Path(__file__).parent / "auth_state.json"
WAIT_MS = int(os.getenv("PLAYWRIGHT_LOGIN_WAIT_MS", "120000"))

print(f"Navigating to {URL}")
print(f"You have {WAIT_MS // 1000} seconds to complete the Entra ID login.")
print(f"Auth state will be saved to: {OUTPUT}\n")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    context = browser.new_context(no_viewport=True)
    page = context.new_page()

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(WAIT_MS)

    context.storage_state(path=str(OUTPUT))
    browser.close()

print(f"\nAuth state saved to: {OUTPUT}")
print("Update your .env:")
print(f"  PLAYWRIGHT_STORAGE_STATE={OUTPUT}")
print("  PLAYWRIGHT_HEADLESS=true")
