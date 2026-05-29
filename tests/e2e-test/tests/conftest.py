from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
from config.constants import *
from slugify import slugify
from pages.loginPage import LoginPage
from dotenv import load_dotenv
import os
from py.xml import html # type: ignore
import io
import logging
from bs4 import BeautifulSoup
import atexit

@pytest.fixture(scope="session")
def login_logout():
    load_dotenv()
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
    storage_state_path = os.getenv("PLAYWRIGHT_STORAGE_STATE", "")

    with sync_playwright() as p:
        launch_args = [] if headless else ["--start-maximized"]
        browser = p.chromium.launch(headless=headless, args=launch_args)

        if storage_state_path and os.path.exists(storage_state_path):
            # CI mode: reuse saved auth state (cookies + localStorage)
            context = browser.new_context(
                no_viewport=None,
                storage_state=storage_state_path,
            )
        else:
            # Interactive mode: open browser and wait for manual Entra ID login
            context = browser.new_context(no_viewport=True)

        context.set_default_timeout(150000)
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded")

        if not (storage_state_path and os.path.exists(storage_state_path)):
            wait_ms = int(os.getenv("PLAYWRIGHT_LOGIN_WAIT_MS", "60000"))
            page.wait_for_timeout(wait_ms)

        yield page
        browser.close()

log_streams = {}

@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    # Prepare StringIO for capturing logs
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)

    logger = logging.getLogger()
    logger.addHandler(handler)

    # Save handler and stream
    log_streams[item.nodeid] = (handler, stream)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()

    handler, stream = log_streams.get(item.nodeid, (None, None))

    if handler and stream:
        # Make sure logs are flushed
        handler.flush()
        log_output = stream.getvalue()

        # Only remove the handler, don't close the stream yet
        logger = logging.getLogger()
        logger.removeHandler(handler)

        # Store the log output on the report object for HTML reporting
        report.description = f"<pre>{log_output.strip()}</pre>"

        # Clean up references
        log_streams.pop(item.nodeid, None)
    else:
        report.description = ""

def pytest_collection_modifyitems(items):
    for item in items:
        if hasattr(item, 'callspec'):
            prompt = item.callspec.params.get("prompt")
            if prompt:
                item._nodeid = prompt  # This controls how the test name appears in the report

def rename_duration_column():
    report_path = os.path.abspath("report.html")  # or your report filename
    if not os.path.exists(report_path):
        print("Report file not found, skipping column rename.")
        return

    with open(report_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    # Find and rename the header
    headers = soup.select('table#results-table thead th')
    for th in headers:
        if th.text.strip() == 'Duration':
            th.string = 'Execution Time'
            #print("Renamed 'Duration' to 'Execution Time'")
            break
    else:
        print("'Duration' column not found in report.")

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

# Register this function to run after everything is done
atexit.register(rename_duration_column)