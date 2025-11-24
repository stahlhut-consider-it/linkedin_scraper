import asyncio
import getpass
import os
import random
import time
import math
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
import json

import zendriver as zd
from zendriver import cdp

from . import constants as c
from .by import By

COOKIE_ENV_KEY = "LINKEDIN_LI_AT_FILE"
HEADLESS_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


def __prompt_email_password() -> tuple[str, str]:
    user = input("Email: ")
    password = getpass.getpass(prompt="Password: ")
    return user, password


async def start_browser(config: Optional[zd.Config] = None, **kwargs) -> zd.Browser:
    """Thin wrapper around zendriver.start with sensible defaults."""
    if config is None:
        config = build_browser_config(**kwargs)
    return await zd.start(config)


def build_browser_config(
    headless: bool = False,
    user_data_dir: Optional[str] = None,
    browser_executable_path: Optional[str] = None,
    browser_args: Optional[Sequence[str]] = None,
    lang: Optional[str] = None,
) -> zd.Config:
    config = zd.Config(
        user_data_dir=user_data_dir,
        headless=headless,
        browser_executable_path=browser_executable_path,
        browser_args=list(browser_args) if browser_args else None,
        lang=lang,
    )
    if config.browser_args is None:
        config.browser_args = []
    if "--disable-blink-features=AutomationControlled" not in config.browser_args:
        config.browser_args.append("--disable-blink-features=AutomationControlled")
    if headless:
        ua = HEADLESS_USER_AGENT
        config.user_agent = ua
        if config.browser_args is None:
            config.browser_args = []
        config.browser_args.append(f"--user-agent={ua}")
        config.browser_args.append("--window-size=1280,900")
    return config


# Backwards-compat alias for callers expecting the old Selenium helper name.
def build_chrome_options(headless: bool = False) -> zd.Config:
    return build_browser_config(headless=headless)


async def _viewport_size(tab: zd.Tab) -> tuple[int, int]:
    result = await tab.evaluate(
        "[Math.max(document.documentElement.clientWidth, window.innerWidth || 0),"
        " Math.max(document.documentElement.clientHeight, window.innerHeight || 0)]"
    )
    try:
        width = int(result[0] or 0)
        height = int(result[1] or 0)
        return width, height
    except Exception:
        return 0, 0


async def _random_mouse_movements(tab: Optional[zd.Tab], move_count: int = 0) -> None:
    """Jitter the mouse around the page using curved (Bezier) mouse paths."""
    if tab is None:
        return

    if move_count <= 0:
        move_count = random.randint(2, 5)

    width, height = await _viewport_size(tab)
    if width <= 0 or height <= 0:
        return

    start_x = random.randint(1, max(width - 1, 1))
    start_y = random.randint(1, max(height - 1, 1))
    await tab.mouse_move(start_x, start_y, steps=3)

    def _bezier_points(sx: int, sy: int, ex: int, ey: int, segments: int = 12) -> list[tuple[int, int]]:
        """Generate points along a cubic Bezier curve clamped to the viewport."""
        if segments <= 0:
            return []
        dx = ex - sx
        dy = ey - sy
        distance = math.hypot(dx, dy) or 1.0
        curve_mag = distance * random.uniform(0.1, 0.35)
        norm_x = dx / distance
        norm_y = dy / distance
        orth_x = -norm_y
        orth_y = norm_x
        cp1 = (
            sx + dx * 0.3 + orth_x * curve_mag * random.uniform(0.5, 1.2),
            sy + dy * 0.3 + orth_y * curve_mag * random.uniform(0.5, 1.2),
        )
        cp2 = (
            sx + dx * 0.7 - orth_x * curve_mag * random.uniform(0.5, 1.2),
            sy + dy * 0.7 - orth_y * curve_mag * random.uniform(0.5, 1.2),
        )
        points: list[tuple[int, int]] = []
        for i in range(1, segments + 1):
            t = i / segments
            inv = 1 - t
            x = inv**3 * sx + 3 * inv**2 * t * cp1[0] + 3 * inv * t**2 * cp2[0] + t**3 * ex
            y = inv**3 * sy + 3 * inv**2 * t * cp1[1] + 3 * inv * t**2 * cp2[1] + t**3 * ey
            clamped_x = max(1, min(int(round(x)), max(width - 1, 1)))
            clamped_y = max(1, min(int(round(y)), max(height - 1, 1)))
            points.append((clamped_x, clamped_y))
        return points

    current_x, current_y = start_x, start_y
    for _ in range(move_count):
        end_x = random.randint(1, max(width - 1, 1))
        end_y = random.randint(1, max(height - 1, 1))
        segments = random.randint(8, 16)
        path = _bezier_points(current_x, current_y, end_x, end_y, segments=segments)
        for x, y in path:
            try:
                await tab.mouse_move(x, y, steps=1)
            except Exception:
                break
            await tab.sleep(random.uniform(0.01, 0.05))
        current_x, current_y = end_x, end_y
        await tab.sleep(random.uniform(0.05, 0.3))


async def reject_cookies(
    tab: Optional[zd.Tab], timeout: float = 12, retries: int = 2, retry_delay: float = 1.5
) -> bool:
    """Wrapper that retries cookie rejection a few times."""
    if tab is None:
        return False

    for attempt in range(retries + 1):
        if await _dismiss_cookie_banner(tab, timeout=timeout):
            return True
        if attempt < retries:
            await tab.sleep(retry_delay)
    return False


async def human_delay(
    tab: Optional[zd.Tab] = None, min_seconds: float = 5, max_seconds: float = 20
) -> None:
    """Insert a long, randomized pause and optional mouse jitter to look human."""
    if max_seconds < min_seconds:
        max_seconds = min_seconds

    total_sleep = random.uniform(min_seconds, max_seconds)
    chunks = random.randint(1, 3)
    for _ in range(chunks):
        if tab:
            await _random_mouse_movements(tab, move_count=random.randint(1, 3))
        segment = max(0.05, total_sleep / chunks * random.uniform(0.6, 1.4))
        await asyncio.sleep(segment)


async def human_like_scroll(tab: zd.Tab, target_ratio: float = 1.0) -> None:
    """Scroll in a non-linear, human style with small pauses."""
    if tab is None:
        return
    ratio = max(0.0, min(1.0, float(target_ratio)))
    try:
        await tab.evaluate(f"window.scrollTo(0, document.body.scrollHeight*{ratio});")
    except Exception:
        pass
    await tab.sleep(random.uniform(0.15, 0.5))


async def page_has_loaded(tab: zd.Tab) -> bool:
    try:
        state = await tab.evaluate("document.readyState")
        return state == "complete"
    except Exception:
        return False


async def _click_first_matching(tab: zd.Tab, selectors: Iterable[str], wait_time: float) -> bool:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + wait_time
    selectors = list(selectors)
    while loop.time() < deadline:
        for selector in selectors:
            try:
                elems = await tab.xpath(selector, timeout=0)
            except Exception:
                elems = []
            for elem in elems:
                try:
                    await elem.click()
                    return True
                except Exception:
                    continue
        await tab.sleep(0.2)
    return False


async def _click_by_text_labels(tab: zd.Tab, labels: Sequence[str], timeout: float) -> bool:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    labels = [lbl.lower() for lbl in labels]
    while loop.time() < deadline:
        for label in labels:
            try:
                btn = await tab.find(label, best_match=True, timeout=1)
                if btn:
                    await btn.click()
                    return True
            except Exception:
                continue
        await tab.sleep(0.25)
    return False


def _selectors_for_labels(labels: Sequence[str]) -> list[str]:
    normalized_text = "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜß', 'abcdefghijklmnopqrstuvwxyzäöüß')"
    normalized_aria = "translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜß', 'abcdefghijklmnopqrstuvwxyzäöüß')"
    selectors: list[str] = []
    for label in labels:
        selectors.extend(
            [
                f"//button[contains({normalized_text}, '{label}')]",
                f"//span[contains({normalized_text}, '{label}')]/ancestor::button[1]",
                f"//button[contains({normalized_aria}, '{label}')]",
            ]
        )
    return selectors


async def _dismiss_cookie_banner(tab: zd.Tab, timeout: float = 12) -> bool:
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

    dismiss_selectors = [
        "//button[@id='artdeco-global-alert-container__action-dismiss']",
        "//button[contains(@aria-label, 'dismiss') or contains(@aria-label, 'schließen') or contains(@aria-label, 'close')]",
        "//button[contains(@data-test-modal-close-btn, '')]",
    ]

    if await _click_by_text_labels(tab, reject_labels, timeout):
        return True

    if await _click_first_matching(tab, reject_selectors, timeout):
        return True

    if await _click_first_matching(tab, dismiss_selectors, 2):
        return True

    if await _click_first_matching(tab, manage_selectors, 3):
        if await _click_first_matching(tab, reject_selectors, 6):
            return True

    try:
        labels_json = json.dumps(reject_labels)
        script = """
        const labels = {labels};
        const nodes = Array.from(document.querySelectorAll('button, [role="button"], a'));
        for (const node of nodes) {{
            const text = (node.innerText || node.textContent || '').toLowerCase();
            if (labels.some(lbl => text.includes(lbl))) {{
                node.click();
                return true;
            }}
        }}
        return false;
        """.format(labels=labels_json)
        js_clicked = await tab.evaluate(script, await_promise=True)
        if js_clicked:
            return True
    except Exception:
        pass

    return False


def _cookie_path(path_hint: Optional[str] = None) -> Path:
    env_path = os.getenv(COOKIE_ENV_KEY)
    if path_hint:
        return Path(path_hint).expanduser()
    if env_path:
        return Path(env_path).expanduser()
    return Path.home() / ".linkedin_li_at.cookie"


def _load_cookie_from_disk(path: Path) -> Optional[str]:
    try:
        if path.is_file():
            value = path.read_text().strip()
            return value or None
    except Exception:
        return None
    return None


def _persist_cookie_value(value: str, path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value.strip())
        return True
    except Exception:
        return False


def _delete_cookie_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


async def _clear_li_at_cookie(browser: Optional[zd.Browser]) -> None:
    """Best-effort removal of a bad li_at cookie to break redirect loops."""
    if not browser:
        return
    try:
        await browser.cookies.delete(name="li_at", domain=".linkedin.com", path="/")
        return
    except Exception:
        pass
    try:
        await browser.cookies.delete_all()
        return
    except Exception:
        pass
    try:
        await browser.cookies.set_all(
            [
                cdp.network.CookieParam(
                    name="li_at",
                    value="",
                    domain=".linkedin.com",
                    path="/",
                    expires=0,
                )
            ]
        )
    except Exception:
        pass


async def _read_li_at_from_driver(tab: zd.Tab) -> Optional[str]:
    try:
        browser = tab.browser
        if not browser:
            return None
        cookies = await browser.cookies.get_all()
        for cookie in cookies:
            if getattr(cookie, "name", "") == "li_at" and getattr(cookie, "value", None):
                return cookie.value
    except Exception:
        return None
    return None


async def _is_logged_in(tab: zd.Tab, timeout: float = 10) -> bool:
    try:
        await wait_for_element(tab, By.CLASS_NAME, c.VERIFY_LOGIN_ID, timeout=timeout)
        return True
    except asyncio.TimeoutError:
        pass
    try:
        await wait_for_element(tab, By.CSS_SELECTOR, "input[placeholder*='Search']", timeout=timeout)
        return True
    except asyncio.TimeoutError:
        pass
    return False


async def login(
    tab: zd.Tab,
    email: Optional[str] = None,
    password: Optional[str] = None,
    cookie: Optional[str] = None,
    timeout: float = 10,
    cookie_path: Optional[str] = None,
) -> None:
    browser = tab.browser
    cookie_file = _cookie_path(cookie_path)
    cookie = cookie or _load_cookie_from_disk(cookie_file)
    if cookie and browser:
        if await _login_with_cookie(browser, tab, cookie, timeout=timeout):
            _persist_cookie_value(cookie, cookie_file)
            return
        # Failed cookie login: clear stored cookie and browser state so we can fall back safely.
        _delete_cookie_file(cookie_file)
        await _clear_li_at_cookie(browser)

    if not email or not password:
        email, password = __prompt_email_password()

    await tab.get("https://www.linkedin.com/login")
    await reject_cookies(tab, timeout=timeout, retries=2, retry_delay=1)
    await human_delay(tab)
    element = await wait_for_element(tab, By.ID, "username", timeout=10)
    await human_delay(tab)

    email_elem = element
    await email_elem.send_keys(email)
    await human_delay(tab)

    password_elem = await wait_for_element(tab, By.ID, "password", timeout=10)
    await password_elem.send_keys(password)
    await password_elem.send_keys("\r\n")
    await human_delay(tab)

    await reject_cookies(tab, timeout=timeout, retries=2, retry_delay=1)
    await human_delay(tab)

    if await _is_logged_in(tab, timeout=timeout):
        new_cookie = await _read_li_at_from_driver(tab)
        if new_cookie:
            _persist_cookie_value(new_cookie, cookie_file)


async def _login_with_cookie(
    browser: zd.Browser, tab: zd.Tab, cookie: str, timeout: float = 10
) -> bool:
    try:
        await tab.get("https://www.linkedin.com/")
        await human_delay(tab)
        await browser.cookies.set_all(
            [
                cdp.network.CookieParam(
                    name="li_at",
                    value=cookie,
                    domain=".linkedin.com",
                    path="/",
                )
            ]
        )
        await tab.get("https://www.linkedin.com/feed/")
        await human_delay(tab)
        await reject_cookies(tab, timeout=timeout, retries=2, retry_delay=1)
        return await _is_logged_in(tab, timeout=timeout)
    except Exception:
        return False


async def find_element(target: zd.Tab | zd.Element, by: str, value: str):
    if by == By.XPATH:
        return await _find_by_xpath(target, value)
    selector = _css_selector(by, value)
    if selector is None:
        return None
    if isinstance(target, zd.Tab):
        try:
            return await target.query_selector(selector)
        except Exception:
            return None
    try:
        return await target.query_selector(selector)
    except Exception:
        return None


async def find_elements(target: zd.Tab | zd.Element, by: str, value: str) -> List[zd.Element]:
    if by == By.XPATH:
        return await _find_all_by_xpath(target, value)
    selector = _css_selector(by, value)
    if selector is None:
        return []
    if isinstance(target, zd.Tab):
        try:
            items = await target.query_selector_all(selector)
            return items if isinstance(items, list) else []
        except Exception:
            return []
    try:
        items = await target.query_selector_all(selector)
        return items if isinstance(items, list) else []
    except Exception:
        return []


async def wait_for_element(
    target: zd.Tab | zd.Element,
    by: str = By.CLASS_NAME,
    name: str = "pv-top-card",
    timeout: float = 10,
) -> zd.Element:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        elem = await find_element(target, by, name)
        if elem:
            return elem
        await asyncio.sleep(0.25)
    raise asyncio.TimeoutError(f"Timeout waiting for element by {by}={name}")


async def wait_for_all_elements(
    target: zd.Tab | zd.Element,
    by: str = By.CLASS_NAME,
    name: str = "pv-top-card",
    timeout: float = 10,
) -> List[zd.Element]:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        elems = await find_elements(target, by, name)
        if elems:
            return elems
        await asyncio.sleep(0.25)
    raise asyncio.TimeoutError(f"Timeout waiting for elements by {by}={name}")


def _css_selector(by: str, value: str) -> Optional[str]:
    if by == By.CSS_SELECTOR:
        return value
    if by == By.CLASS_NAME:
        return f".{value}"
    if by == By.ID:
        return f"#{value}"
    if by == By.TAG_NAME:
        return value
    if by == By.NAME:
        return f"[name='{value}']"
    return None


async def _find_by_xpath(target: zd.Tab | zd.Element, xpath: str):
    results = await _find_all_by_xpath(target, xpath)
    return results[0] if results else None


async def _find_all_by_xpath(target: zd.Tab | zd.Element, xpath: str) -> List[zd.Element]:
    if isinstance(target, zd.Tab):
        try:
            return await target.xpath(xpath, timeout=1.5)
        except Exception:
            return []

    if xpath in ("*", "./*"):
        try:
            await target.update()
            return target.children
        except Exception:
            return []

    if xpath == "..":
        try:
            await target.update()
            return [target.parent] if target.parent else []
        except Exception:
            return []

    parent_tab = getattr(target, "tab", None)
    if parent_tab:
        try:
            candidates = await parent_tab.xpath(xpath, timeout=1.5)
        except Exception:
            candidates = []
        filtered: List[zd.Element] = []
        for cand in candidates:
            try:
                if await _is_descendant(cand, target):
                    filtered.append(cand)
            except Exception:
                continue
        return filtered
    return []


async def _is_descendant(node: zd.Element, ancestor: zd.Element) -> bool:
    try:
        await node.update()
        await ancestor.update()
    except Exception:
        return False
    current: Optional[zd.Element] = node
    hops = 0
    while current and hops < 15:
        if current.backend_node_id == ancestor.backend_node_id:
            return True
        current = current.parent
        hops += 1
    return False
