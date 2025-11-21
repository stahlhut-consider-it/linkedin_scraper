import getpass
import os
import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from . import constants as c

COOKIE_ENV_KEY = "LINKEDIN_LI_AT_FILE"

def __prompt_email_password():
  u = input("Email: ")
  p = getpass.getpass(prompt="Password: ")
  return (u, p)


def _random_mouse_movements(driver, move_count=0):
    """Jitter the mouse around the page to mimic human behavior."""
    if driver is None:
        return

    if move_count <= 0:
        move_count = random.randint(2, 5)

    try:
        body = driver.find_element(By.TAG_NAME, "body")
        width, height = driver.execute_script(
            "return [Math.max(document.documentElement.clientWidth, window.innerWidth || 0), "
            "Math.max(document.documentElement.clientHeight, window.innerHeight || 0)];"
        )
        width = int(width or 0)
        height = int(height or 0)
    except Exception:
        return

    if width <= 0 or height <= 0:
        return

    for _ in range(move_count):
        try:
            x_offset = random.randint(1, max(width - 1, 1))
            y_offset = random.randint(1, max(height - 1, 1))
            (
                ActionChains(driver)
                .move_to_element_with_offset(body, x_offset, y_offset)
                .pause(random.uniform(0.25, 0.75))
                .perform()
            )
        except Exception:
            # Best-effort jitter; ignore failures so scraping can proceed.
            break


def reject_cookies(driver, timeout=12, retries=2, retry_delay=1.5):
    """Wrapper that retries cookie rejection a few times."""
    if driver is None:
        return False

    for attempt in range(retries + 1):
        if _dismiss_cookie_banner(driver, timeout=timeout):
            return True
        if attempt < retries:
            time.sleep(retry_delay)
    return False


def human_delay(driver=None, min_seconds=5, max_seconds=20):
    """Insert a long, randomized pause and optional mouse jitter to look human."""
    if max_seconds < min_seconds:
        max_seconds = min_seconds
    if driver:
        reject_cookies(driver, timeout=2, retries=0)
    _random_mouse_movements(driver)
    time.sleep(random.uniform(min_seconds, max_seconds))


def page_has_loaded(driver):
    page_state = driver.execute_script('return document.readyState;')
    return page_state == 'complete'


def _dismiss_cookie_banner(driver, timeout=12):
    """Try to close the LinkedIn cookie banner so navigation works."""

    def _click_first_matching(selectors, wait_time):
        deadline = time.time() + wait_time
        while time.time() < deadline:
            for selector in selectors:
                for btn in driver.find_elements(By.XPATH, selector):
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            btn.click()
                            return True
                    except Exception:
                        continue
            time.sleep(0.2)
        return False

    def _selectors_for_labels(labels):
        # Normalize strings to lowercase (supports basic German characters too).
        normalized_text = "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜß', 'abcdefghijklmnopqrstuvwxyzäöüß')"
        normalized_aria = "translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜß', 'abcdefghijklmnopqrstuvwxyzäöüß')"
        selectors = []
        for label in labels:
            selectors.extend(
                [
                    f"//button[contains({normalized_text}, '{label}')]",
                    f"//span[contains({normalized_text}, '{label}')]/ancestor::button[1]",
                    f"//button[contains({normalized_aria}, '{label}')]",
                ]
            )
        return selectors

    # Prefer explicit rejection in English or German to avoid accepting cookies accidentally.
    reject_labels = [
        "reject",
        "reject all",
        "decline",
        "decline all",
        "refuse",
        "ablehnen",
        "alle ablehnen",
        "nicht zustimmen",
        "keine zustimmung",
        "nur notwendige",
        "nur erforderliche",
        "nur notwendige cookies",
        "essential only",
        "only essential",
        "necessary only",
        "strictly necessary",
        "reject non-essential",
    ]
    reject_labels = list(dict.fromkeys(reject_labels))
    reject_selectors = _selectors_for_labels(reject_labels)

    manage_labels = [
        "manage preferences",
        "manage settings",
        "manage choices",
        "präferenzen verwalten",
        "einstellungen verwalten",
        "auswahl verwalten",
    ]
    manage_selectors = _selectors_for_labels(manage_labels)

    # Fallback close buttons for variants that expose only a dismiss action.
    dismiss_selectors = [
        "//button[@id='artdeco-global-alert-container__action-dismiss']",
        "//button[contains(@aria-label, 'dismiss') or contains(@aria-label, 'schließen') or contains(@aria-label, 'close')]",
        "//button[contains(@data-test-modal-close-btn, '')]",
    ]

    if _click_first_matching(reject_selectors, timeout):
        return True

    if _click_first_matching(dismiss_selectors, 2):
        return True

    # Some variants hide reject behind a manage/preferences dialog.
    if _click_first_matching(manage_selectors, 3):
        if _click_first_matching(reject_selectors, 6):
            return True

    # Try inside common consent iframes.
    try:
        frames = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'consent') or contains(@id, 'cmp') or contains(@id, 'sp_message')]")
        for frame in frames:
            try:
                driver.switch_to.frame(frame)
                if _click_first_matching(reject_selectors, 3):
                    driver.switch_to.default_content()
                    return True
                if _click_first_matching(dismiss_selectors, 2):
                    driver.switch_to.default_content()
                    return True
            finally:
                try:
                    driver.switch_to.default_content()
                except Exception:
                    pass
    except Exception:
        try:
            driver.switch_to.default_content()
        except Exception:
            pass

    # JS-based sweep over common clickable elements to find label text when DOM is dynamic.
    try:
        script = """
        const labels = arguments[0];
        const nodes = Array.from(document.querySelectorAll('button, [role="button"], a'));
        for (const node of nodes) {
            const text = (node.innerText || node.textContent || '').toLowerCase();
            if (labels.some(lbl => text.includes(lbl))) {
                node.click();
                return true;
            }
        }
        return false;
        """
        if driver.execute_script(script, reject_labels):
            return True
    except Exception:
        pass

    # Broader fall-back: scan all visible buttons for a reject label.
    try:
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            label_text = " ".join(
                [btn.text or "", btn.get_attribute("aria-label") or ""]
            ).lower()
            if any(term in label_text for term in reject_labels):
                if btn.is_enabled():
                    btn.click()
                    return True
    except Exception:
        pass

    # We intentionally avoid auto-accepting cookies. If nothing was clicked, signal failure.
    return False


def _cookie_path(path_hint=None):
    env_path = os.getenv(COOKIE_ENV_KEY)
    if path_hint:
        return Path(path_hint).expanduser()
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".linkedin_li_at.cookie"


def _load_cookie_from_disk(path):
    try:
        if path.is_file():
            value = path.read_text().strip()
            return value or None
    except Exception:
        return None
    return None


def _persist_cookie_value(value, path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value.strip())
        return True
    except Exception:
        return False


def _read_li_at_from_driver(driver):
    try:
        for ckie in driver.get_cookies():
            if ckie.get("name") == "li_at" and ckie.get("value"):
                return ckie.get("value")
    except Exception:
        return None
    return None


def _is_logged_in(driver, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            EC.any_of(
                EC.presence_of_element_located((By.CLASS_NAME, c.VERIFY_LOGIN_ID)),
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']")),
                EC.url_contains("/feed"),
                EC.url_contains("/in/")
            )
        )
        return True
    except TimeoutException:
        return False


def login(driver, email=None, password=None, cookie=None, timeout=10, cookie_path=None):
    cookie_file = _cookie_path(cookie_path)
    cookie = cookie or _load_cookie_from_disk(cookie_file)
    if cookie:
        if _login_with_cookie(driver, cookie, timeout=timeout):
            _persist_cookie_value(cookie, cookie_file)
            return
  
    if not email or not password:
        email, password = __prompt_email_password()
  
    driver.get("https://www.linkedin.com/login")
    reject_cookies(driver, timeout=timeout, retries=2, retry_delay=1)
    human_delay(driver)
    element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))
    human_delay(driver)
  
    email_elem = driver.find_element(By.ID,"username")
    email_elem.send_keys(email)
    human_delay(driver)
  
    password_elem = driver.find_element(By.ID,"password")
    password_elem.send_keys(password)
    password_elem.submit()
    human_delay(driver)
  
    if driver.current_url == 'https://www.linkedin.com/checkpoint/lg/login-submit':
        remember = driver.find_element(By.ID,c.REMEMBER_PROMPT)
        if remember:
            human_delay(driver)
            remember.submit()

    reject_cookies(driver, timeout=timeout, retries=2, retry_delay=1)
    human_delay(driver)

    if _is_logged_in(driver, timeout=timeout):
        new_cookie = _read_li_at_from_driver(driver)
        if new_cookie:
            _persist_cookie_value(new_cookie, cookie_file)
  
def _login_with_cookie(driver, cookie, timeout=10):
    try:
        driver.get("https://www.linkedin.com/")
        human_delay(driver)
        driver.add_cookie({
          "name": "li_at",
          "value": cookie
        })
        driver.get("https://www.linkedin.com/feed/")
        human_delay(driver)
        reject_cookies(driver, timeout=timeout, retries=2, retry_delay=1)
        return _is_logged_in(driver, timeout=timeout)
    except Exception:
        return False


def build_chrome_options(headless=False):
    """Return Chrome options tuned to reduce prompts/trackers and look less automated."""
    options = webdriver.ChromeOptions()

    prefs = {
        # Block noisy prompts that can trigger additional banners.
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.media_stream": 2,
        # Lean towards fewer tracking cookies without blocking first-party auth cookies.
        "profile.block_third_party_cookies": True,
        "intl.accept_languages": "en-US,en",
    }
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--lang=en-US")

    if headless:
        options.add_argument("--headless=new")

    return options
