import getpass
import random
import time
from . import constants as c
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

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


def human_delay(driver=None, min_seconds=5, max_seconds=20):
    """Insert a long, randomized pause and optional mouse jitter to look human."""
    if max_seconds < min_seconds:
        max_seconds = min_seconds
    _random_mouse_movements(driver)
    time.sleep(random.uniform(min_seconds, max_seconds))


def page_has_loaded(driver):
    page_state = driver.execute_script('return document.readyState;')
    return page_state == 'complete'


def _dismiss_cookie_banner(driver, timeout=5):
    """Try to close the LinkedIn cookie banner so navigation works."""
    selectors = [
        # Buttons are usually labelled “Accept” / “Reject”
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'accept')]",
        "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'reject')]",
        # Some variants expose an aria-label
        "//button[@aria-label='Accept cookies']",
    ]

    for selector in selectors:
        try:
            btn = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
            btn.click()
            return True
        except Exception:
            continue
    return False

def login(driver, email=None, password=None, cookie = None, timeout=10):
    if cookie is not None:
        return _login_with_cookie(driver, cookie)
  
    if not email or not password:
        email, password = __prompt_email_password()
  
    driver.get("https://www.linkedin.com/login")
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

    _dismiss_cookie_banner(driver, timeout=timeout)
    human_delay(driver)

    try:
        WebDriverWait(driver, timeout).until(
            EC.any_of(
                EC.presence_of_element_located((By.CLASS_NAME, c.VERIFY_LOGIN_ID)),
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']")),
                EC.url_contains("/feed"),
                EC.url_contains("/in/")
            )
        )
    except TimeoutException:
        # Nav selectors on LinkedIn can change; continue even if we didn't spot them in time.
        pass
  
def _login_with_cookie(driver, cookie):
    driver.get("https://www.linkedin.com/login")
    human_delay(driver)
    driver.add_cookie({
      "name": "li_at",
      "value": cookie
    })
    human_delay(driver)
