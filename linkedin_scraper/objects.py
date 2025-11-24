import asyncio
import random
from dataclasses import dataclass
from typing import Optional

import zendriver as zd

from . import actions
from . import constants as c
from .by import By


@dataclass
class Contact:
    name: str = None
    occupation: str = None
    url: str = None


@dataclass
class Institution:
    institution_name: str = None
    linkedin_url: str = None
    website: str = None
    industry: str = None
    type: str = None
    headquarters: str = None
    company_size: int = None
    founded: int = None


@dataclass
class Experience(Institution):
    from_date: str = None
    to_date: str = None
    description: str = None
    position_title: str = None
    duration: str = None
    location: str = None


@dataclass
class Education(Institution):
    from_date: str = None
    to_date: str = None
    description: str = None
    degree: str = None


@dataclass
class Interest(Institution):
    title = None


@dataclass
class Accomplishment(Institution):
    category = None
    title = None


@dataclass
class Scraper:
    driver: Optional[zd.Tab] = None
    browser: Optional[zd.Browser] = None
    loop: Optional[asyncio.AbstractEventLoop] = None
    _owns_browser: bool = False
    WAIT_FOR_ELEMENT_TIMEOUT = 10
    TOP_CARD = "pv-top-card"
    HUMAN_DELAY_MIN = 1
    HUMAN_DELAY_MAX = 8

    def _has_running_loop(self) -> bool:
        try:
            loop = asyncio.get_running_loop()
            return loop.is_running()
        except RuntimeError:
            return False

    def _run(self, coro):
        if self.loop and self.loop.is_running():
            # Execute on existing loop; block until done.
            return asyncio.run_coroutine_threadsafe(coro, self.loop).result()
        if not self.loop:
            self.loop = asyncio.new_event_loop()
        return self.loop.run_until_complete(coro)

    def human_pause(self, min_seconds=None, max_seconds=None):
        """Pause with random mouse jitter to mimic slower human interactions."""
        min_seconds = min_seconds or self.HUMAN_DELAY_MIN
        max_seconds = max_seconds or self.HUMAN_DELAY_MAX
        self._run(actions.human_delay(self.driver, min_seconds=min_seconds, max_seconds=max_seconds))

    def wait(self, duration):
        min_seconds = max(duration, self.HUMAN_DELAY_MIN)
        max_seconds = max(self.HUMAN_DELAY_MAX, min_seconds)
        self.human_pause(min_seconds=min_seconds, max_seconds=max_seconds)

    def focus(self):
        if self.driver:
            try:
                self._run(self.driver.bring_to_front())
            except Exception:
                pass

    def mouse_click(self, elem):
        self.human_pause()
        try:
            self._run(elem.click())
        except Exception:
            pass

    def wait_for_element_to_load(self, by=By.CLASS_NAME, name="pv-top-card", base=None):
        base = base or self.driver
        return self._run(
            actions.wait_for_element(base, by=by, name=name, timeout=self.WAIT_FOR_ELEMENT_TIMEOUT)
        )

    def wait_for_all_elements_to_load(self, by=By.CLASS_NAME, name="pv-top-card", base=None):
        base = base or self.driver
        return self._run(
            actions.wait_for_all_elements(
                base, by=by, name=name, timeout=self.WAIT_FOR_ELEMENT_TIMEOUT
            )
        )


    def is_signed_in(self):
        try:
            self._run(
                actions.wait_for_element(
                    self.driver, by=By.CLASS_NAME, name=c.VERIFY_LOGIN_ID, timeout=self.WAIT_FOR_ELEMENT_TIMEOUT
                )
            )
            return True
        except Exception:
            pass
        return False

    def scroll_to_half(self):
        self._run(actions.human_like_scroll(self.driver, target_ratio=0.5))
        self.human_pause()

    def scroll_to_bottom(self):
        self._run(actions.human_like_scroll(self.driver, target_ratio=1.0))
        self.human_pause()

    def scroll_class_name_element_to_page_percent(self, class_name:str, page_percent:float):
        if not self.driver:
            return
        try:
            self._run(
                self.driver.evaluate(
                    f'elem = document.getElementsByClassName("{class_name}")[0];'
                    f' if (elem) {{ elem.scrollTo(0, elem.scrollHeight*{float(page_percent)}); }}'
                )
            )
        except Exception:
            pass
        self.human_pause()

    def __find_element_by_class_name__(self, class_name):
        try:
            self._run(actions.find_element(self.driver, By.CLASS_NAME, class_name))
            return True
        except:
            pass
        return False

    def __find_element_by_xpath__(self, tag_name):
        try:
            self._run(actions.find_element(self.driver, By.XPATH, tag_name))
            return True
        except:
            pass
        return False

    def __find_enabled_element_by_xpath__(self, tag_name):
        try:
            elem = self._run(actions.find_element(self.driver, By.XPATH, tag_name))
            return bool(elem)
        except:
            pass
        return False

    @classmethod
    def __find_first_available_element__(cls, *args):
        for elem in args:
            if elem:
                return elem[0]
