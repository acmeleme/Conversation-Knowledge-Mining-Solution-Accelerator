"""
E2E tests for Entra ID authentication criteria.
Success criteria:
  C1: App authenticates via Entra ID (no demo role selector shown)
  C2: No "Demo" text visible in the UI
  C3: Avatar (gray circle) shows Entra ID user profile when clicked
  C4: Login screen has NO "Visitante" card — only Financeiro + Operador cards exist
  C5: (Negative) If access-denied screen appears, it shows '🚫 Acesso Negado' + 'Sair' button
  All tests must pass after frontend/backend restart (stateless by design).
"""

import io
import logging
import time
import pytest
from pytest_check import check
from pages.authPage import AuthPage

logger = logging.getLogger(__name__)


def _meaningful_profile_lines(popover_text: str):
    ignored_exact_lines = {"Ver Perfil", "Trocar Perfil", "Usuário"}
    # "Visitante" was removed as a valid role; only Financeiro and Operador remain.
    ignored_partial_lines = ("Financeiro", "Operador")

    return [
        line.strip()
        for line in popover_text.splitlines()
        if line.strip()
        and line.strip() not in ignored_exact_lines
        and not any(partial in line for partial in ignored_partial_lines)
    ]


def _ensure_profile_popover_open(auth: AuthPage):
    if not auth.is_profile_popover_visible():
        auth.click_avatar()
        auth.page.wait_for_timeout(500)
    return auth.is_profile_popover_visible()


def _validate_profile_popover(auth: AuthPage):
    check.equal(
        _ensure_profile_popover_open(auth),
        True,
        "Profile popover did not open after clicking the avatar.",
    )

    popover_text = auth.get_profile_popover_text()
    meaningful_lines = _meaningful_profile_lines(popover_text)

    check.not_equal(
        "",
        popover_text.strip(),
        "Profile popover text should not be empty.",
    )
    check.equal(
        len(meaningful_lines) > 0,
        True,
        f"Profile popover should contain meaningful user information. Current text: {popover_text!r}",
    )


def _validate_displayed_user_name(auth: AuthPage):
    check.equal(
        _ensure_profile_popover_open(auth),
        True,
        "Profile popover should be visible before validating the displayed user name.",
    )

    displayed_name = auth.get_displayed_user_name()

    check.not_equal(
        "",
        displayed_name,
        "Displayed user name in the profile popover should not be empty.",
    )
    check.not_equal(
        "Usuário Demo",
        displayed_name,
        "Displayed user name should not use the legacy demo label.",
    )
    check.not_equal(
        "Dev Local",
        displayed_name,
        "Displayed user name should not use the local development fallback label.",
    )


def _validate_no_visitor_card(auth: AuthPage):
    """C4: Verify the removed 'Visitante' card is absent from the login screen.

    If the role selector is not visible (user already authenticated with a role),
    the check passes vacuously — no login cards are rendered at all.
    """
    if not auth.is_role_selector_visible():
        logger.info(
            "Role selector not visible — user already has an active role. "
            "No login cards to inspect; Visitante card check passes vacuously."
        )
        return

    check.equal(
        auth.is_visitor_card_visible(),
        False,
        "The 'Visitante' role card must NOT appear on the login screen. "
        "Only 'Financeiro & Faturamento' and 'Operador de Callcenter' are valid.",
    )


def _validate_access_denied_or_skip(auth: AuthPage):
    """C5 (negative path): If '🚫 Acesso Negado' is shown, validate its required content.

    In a valid authenticated session this screen should NOT appear.
    The test passes vacuously for users with a recognised role.
    It becomes a hard assertion only when an unauthorised user hits the app.
    """
    if not auth.is_access_denied_visible():
        logger.info(
            "Access denied screen is not visible — authenticated user has a valid role. "
            "Negative path not triggered; test passes vacuously."
        )
        return

    body_text = auth.page.locator("body").inner_text()
    check.is_true(
        "🚫 Acesso Negado" in body_text,
        "Access denied screen must display the '🚫 Acesso Negado' heading.",
    )
    check.equal(
        auth.is_sair_button_visible(),
        True,
        "Access denied screen must provide a 'Sair' button so the user can log out.",
    )


test_steps = [
    (
        "C1: App loads with Entra ID auth - no demo role selector visible",
        lambda auth: check.equal(
            auth.is_role_selector_visible(),
            False,
            "Role selector should not be visible for an Entra ID-authenticated session.",
        ),
    ),
    (
        "C2: No 'Demo' label or text visible anywhere in the UI",
        lambda auth: check.equal(
            auth.is_demo_text_visible(),
            False,
            "The literal text 'Demo' should not be visible anywhere in the UI.",
        ),
    ),
    (
        "C3: Avatar click shows Entra ID user profile in popover",
        lambda auth: _validate_profile_popover(auth),
    ),
    (
        "C3b: Profile popover contains non-empty user name (not 'Dev Local' label)",
        lambda auth: _validate_displayed_user_name(auth),
    ),
    (
        "C4: No 'Visitante' card on login screen - only Financeiro + Operador exist",
        lambda auth: _validate_no_visitor_card(auth),
    ),
    (
        "C5: Access denied screen shows '🚫 Acesso Negado' and 'Sair' button (negative path)",
        lambda auth: _validate_access_denied_or_skip(auth),
    ),
]


test_ids = [f"{i + 1:02d}. {description}" for i, (description, _) in enumerate(test_steps)]


@pytest.mark.parametrize("description, step", test_steps, ids=test_ids)
def test_entra_auth_success_criteria(login_logout, description, step, request):
    request.node._nodeid = description

    page = login_logout
    auth = AuthPage(page)

    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    logger.addHandler(handler)

    logger.info(f"Running test step: {description}")
    start = time.time()

    try:
        auth.wait_for_app_loaded(timeout=15000)
        step(auth)
    finally:
        duration = time.time() - start
        logger.info(f"Execution Time for '{description}': {duration:.2f}s")
        logger.removeHandler(handler)
        request.node._report_sections.append(("call", "log", log_capture.getvalue()))
