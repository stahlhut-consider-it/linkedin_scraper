import getpass
import os
import random
import time
from pathlib import Path

import undetected_chromedriver as uc
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
    """Jitter the mouse around the page with curved moves and slight overshoot."""
    if driver is None:
        return

    if move_count <= 0:
        move_count = random.randint(2, 5)

    def _clamp(val, upper):
        return max(1, min(upper - 1, int(val)))

    def _bezier_curve(p0, p1, p2, p3, steps):
        pts = []
        for i in range(steps + 1):
            t = i / float(steps)
            mt = 1 - t
            x = (
                mt * mt * mt * p0[0]
                + 3 * mt * mt * t * p1[0]
                + 3 * mt * t * t * p2[0]
                + t * t * t * p3[0]
            )
            y = (
                mt * mt * mt * p0[1]
                + 3 * mt * mt * t * p1[1]
                + 3 * mt * t * t * p2[1]
                + t * t * t * p3[1]
            )
            pts.append((int(x), int(y)))
        return pts

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

    # Start the cursor from a random point to vary entry paths.
    start_x = random.randint(1, max(width - 1, 1))
    start_y = random.randint(1, max(height - 1, 1))
    try:
        ActionChains(driver).move_to_element_with_offset(body, start_x, start_y).perform()
    except Exception:
        return

    for _ in range(move_count):
        try:
            end_x = random.randint(1, max(width - 1, 1))
            end_y = random.randint(1, max(height - 1, 1))

            dx = end_x - start_x
            dy = end_y - start_y
            overshoot_factor = 1 + random.uniform(0.05, 0.2)
            overshoot_x = _clamp(start_x + dx * overshoot_factor, width)
            overshoot_y = _clamp(start_y + dy * overshoot_factor, height)

            ctrl1 = (
                _clamp(start_x + dx * random.uniform(0.2, 0.35) + random.randint(-25, 25), width),
                _clamp(start_y + dy * random.uniform(0.2, 0.35) + random.randint(-25, 25), height),
            )
            ctrl2 = (
                _clamp(start_x + dx * random.uniform(0.55, 0.75) + random.randint(-30, 30), width),
                _clamp(start_y + dy * random.uniform(0.55, 0.75) + random.randint(-30, 30), height),
            )

            main_steps = random.randint(6, 12)
            back_steps = random.randint(3, 6)
            path = _bezier_curve((start_x, start_y), ctrl1, ctrl2, (overshoot_x, overshoot_y), main_steps)

            settle_ctrl1 = (
                _clamp(overshoot_x + (end_x - overshoot_x) * random.uniform(0.25, 0.45) + random.randint(-15, 15), width),
                _clamp(overshoot_y + (end_y - overshoot_y) * random.uniform(0.25, 0.45) + random.randint(-15, 15), height),
            )
            settle_ctrl2 = (
                _clamp(overshoot_x + (end_x - overshoot_x) * random.uniform(0.55, 0.75) + random.randint(-12, 12), width),
                _clamp(overshoot_y + (end_y - overshoot_y) * random.uniform(0.55, 0.75) + random.randint(-12, 12), height),
            )
            settle_path = _bezier_curve((overshoot_x, overshoot_y), settle_ctrl1, settle_ctrl2, (end_x, end_y), back_steps)

            full_path = path[1:] + settle_path  # skip the starting point to avoid duplicates
            chain = ActionChains(driver)
            for px, py in full_path:
                chain.move_to_element_with_offset(body, px, py)
                if random.random() < 0.2:
                    chain.pause(random.uniform(0.4, 0.9))
                else:
                    chain.pause(random.uniform(0.05, 0.18))
            chain.perform()
            start_x, start_y = end_x, end_y
            time.sleep(random.uniform(0.05, 0.3))
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
    # Spread the wait into chunks with jitter and occasional navigation noise.
    total_sleep = random.uniform(min_seconds, max_seconds)
    chunks = random.randint(1, 3)
    for _ in range(chunks):
        if driver:
            _random_mouse_movements(driver, move_count=random.randint(1, 3))
            if random.random() < 0.25:
                _random_navigation_actions(driver)
        segment = max(0.05, total_sleep / chunks * random.uniform(0.6, 1.4))
        time.sleep(segment)


def human_like_scroll(driver, target_ratio=1.0):
    """Scroll in a non-linear, human style with small backtracks and overshoot."""
    if driver is None:
        return

    try:
        total_height = int(
            driver.execute_script(
                "return Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);"
            )
            or 0
        )
        viewport_height = int(
            driver.execute_script(
                "return window.innerHeight || document.documentElement.clientHeight || 0;"
            )
            or 0
        )
        current_y = int(
            driver.execute_script(
                "return window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop || 0;"
            )
            or 0
        )
    except Exception:
        try:
            driver.execute_script(
                f"window.scrollTo(0, document.body.scrollHeight*{float(target_ratio)});"
            )
        except Exception:
            pass
        return

    if total_height <= 0 or viewport_height <= 0:
        return

    target_ratio = max(0.0, min(1.0, target_ratio))
    max_scroll_target = max(total_height - viewport_height, 0)
    target_y = max(0, min(int(total_height * target_ratio), max_scroll_target))
    travel = target_y - current_y
    if travel == 0:
        return

    steps = random.randint(5, 8)
    positions = []
    for i in range(steps):
        progress = (i + 1) / steps
        wobble = random.uniform(-0.15, 0.18)
        pos = current_y + travel * progress * (1 + wobble)
        positions.append(max(0, min(max_scroll_target, int(pos))))

    direction = 1 if travel > 0 else -1
    if len(positions) > 2:
        backtrack = positions[-1] - direction * random.randint(40, 120)
        backtrack = max(0, min(max_scroll_target, backtrack))
        positions.insert(-1, backtrack)

    overshoot_pixels = max(60, int(abs(travel) * random.uniform(0.05, 0.18)))
    overshoot = target_y + direction * overshoot_pixels
    overshoot = max(0, min(max_scroll_target, overshoot))
    settle = target_y - direction * random.randint(-35, 35)
    settle = max(0, min(max_scroll_target, settle))

    positions.extend([overshoot, settle, target_y])

    cleaned = []
    for pos in positions:
        if cleaned and cleaned[-1] == pos:
            continue
        cleaned.append(pos)

    for pos in cleaned:
        try:
            driver.execute_script("window.scrollTo(0, arguments[0]);", pos)
        except Exception:
            break
        time.sleep(random.uniform(0.12, 0.5))


def _random_navigation_actions(driver):
    """Occasional navigation-like noise to mimic users (tab peek, resize, selection, idle)."""
    if driver is None:
        return

    try:
        roll = random.random()

        if roll < 0.2:
            # Slight viewport resize.
            size = driver.get_window_size()
            width = size.get("width", 1200)
            height = size.get("height", 900)
            width = max(900, min(1600, width + random.randint(-80, 120)))
            height = max(700, min(1100, height + random.randint(-60, 90)))
            driver.set_window_size(width, height)
            time.sleep(random.uniform(0.2, 0.5))
            return

        if roll < 0.4:
            # Briefly select some text.
            script = """
            const nodes = Array.from(document.querySelectorAll('p, span, div')).filter(n => (n.innerText || '').trim().length > 20);
            if (!nodes.length) return false;
            const candidates = nodes.slice(0, Math.min(nodes.length, 25));
            const target = candidates[Math.floor(Math.random() * candidates.length)];
            const range = document.createRange();
            range.selectNodeContents(target);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            return true;
            """
            driver.execute_script(script)
            time.sleep(random.uniform(0.2, 0.7))
            return

        if roll < 0.55:
            # Tab peek: open a blank tab briefly, then return.
            current = driver.current_window_handle
            driver.switch_to.new_window("tab")
            driver.get("about:blank")
            time.sleep(random.uniform(0.2, 0.6))
            driver.close()
            driver.switch_to.window(current)
            time.sleep(random.uniform(0.1, 0.3))
            return

        # Idle/no-op pause.
        time.sleep(random.uniform(0.25, 0.9))
    except Exception:
        # Best-effort; ignore failures.
        return


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
    options = uc.ChromeOptions()

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
