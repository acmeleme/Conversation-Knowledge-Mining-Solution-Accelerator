import time
from base.base import BasePage


class AuthPage(BasePage):
    APP_READY_SELECTORS = [
        "//button[@title='Send Question']",
        "//textarea[@placeholder='Ask a question...']",
        "//span[normalize-space()='Satisfied']",
    ]

    ROLE_SELECTOR_SELECTORS = [
        "text=Selecione seu perfil",
        "text=Modo Demonstração",
        ".login-demo-badge",
        ".login-card",
    ]

    PROFILE_MENU_BUTTONS = ["Ver Perfil", "Trocar Perfil"]
    NON_NAME_LINES = {
        "Ver Perfil",
        "Trocar Perfil",
        "Usuário",
        "Dev Local",
        "Local Dev",
    }
    # "Visitante" role was removed; only Financeiro and Operador are valid roles.
    ROLE_LABEL_PARTS = ("Financeiro", "Operador")

    VISITOR_CARD_TEXT = "Visitante"
    ACCESS_DENIED_TEXT = "🚫 Acesso Negado"

    def __init__(self, page):
        super().__init__(page)
        self.page = page

    def wait_for_app_loaded(self, timeout=30000):
        deadline = time.time() + (timeout / 1000)

        while time.time() < deadline:
            for selector in self.APP_READY_SELECTORS:
                locator = self.page.locator(selector)
                if locator.count() > 0 and locator.first.is_visible():
                    return
            self.page.wait_for_timeout(250)

        raise AssertionError("Main application did not load within the expected timeout.")

    def is_demo_text_visible(self) -> bool:
        self.wait_for_app_loaded(timeout=15000)
        page_text = self.page.locator("body").inner_text().strip()
        return "Demo" in page_text

    def is_role_selector_visible(self) -> bool:
        for selector in self.ROLE_SELECTOR_SELECTORS:
            locator = self.page.locator(selector)
            if locator.count() > 0 and locator.first.is_visible():
                return True
        return False

    def click_avatar(self):
        candidates = [
            self.page.locator("div[style*='cursor: pointer'] [role='img']"),
            self.page.locator("div[style*='cursor: pointer']"),
            self.page.locator("[role='img']"),
        ]

        for locator in candidates:
            if locator.count() > 0 and locator.first.is_visible():
                locator.first.click(force=True)
                return

        raise AssertionError("Could not find a clickable avatar in the application header.")

    def _profile_popover_surface(self):
        surface = self.page.locator("div").filter(
            has=self.page.get_by_role("button", name="Ver Perfil")
        ).filter(
            has=self.page.get_by_role("button", name="Trocar Perfil")
        ).filter(
            has=self.page.locator("[role='img']")
        )
        return surface.first

    def get_profile_popover_text(self) -> str:
        if not self.is_profile_popover_visible():
            return ""
        return self._profile_popover_surface().inner_text().strip()

    def is_profile_popover_visible(self) -> bool:
        for button_name in self.PROFILE_MENU_BUTTONS:
            button = self.page.get_by_role("button", name=button_name)
            if button.count() == 0 or not button.first.is_visible():
                return False
        return True

    def get_displayed_user_name(self) -> str:
        popover_text = self.get_profile_popover_text()
        if not popover_text:
            return ""

        lines = [line.strip() for line in popover_text.splitlines() if line.strip()]
        for line in lines:
            if line in self.NON_NAME_LINES:
                continue
            if any(role_label in line for role_label in self.ROLE_LABEL_PARTS):
                continue
            return line

        return ""

    def is_visitor_card_visible(self) -> bool:
        """Return True if the removed 'Visitante' role card is still visible (should be False)."""
        # Check via CSS class used in LoginPage cards
        by_class = self.page.locator(".login-card").filter(has_text=self.VISITOR_CARD_TEXT)
        if by_class.count() > 0 and by_class.first.is_visible():
            return True
        # Fallback: text present in body ONLY when role selection screen is active
        body_text = self.page.locator("body").inner_text()
        if "Selecione seu perfil" in body_text and self.VISITOR_CARD_TEXT in body_text:
            return True
        return False

    def is_access_denied_visible(self) -> bool:
        """Return True if the '🚫 Acesso Negado' screen is currently displayed."""
        locator = self.page.locator(f"text={self.ACCESS_DENIED_TEXT}")
        return locator.count() > 0 and locator.first.is_visible()

    def is_sair_button_visible(self) -> bool:
        """Return True if a 'Sair' (logout) button is visible on the current screen."""
        candidates = [
            self.page.get_by_role("button", name="Sair"),
            self.page.locator("button").filter(has_text="Sair"),
        ]
        for locator in candidates:
            if locator.count() > 0 and locator.first.is_visible():
                return True
        return False
