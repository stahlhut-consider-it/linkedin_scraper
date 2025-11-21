from dataclasses import dataclass
from typing import Optional
import random

from selenium.webdriver.remote.webdriver import WebDriver

from . import actions
from . import constants as c

from selenium import webdriver
from selenium.common.exceptions import NoAlertPresentException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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
    driver: Optional[WebDriver] = None
    WAIT_FOR_ELEMENT_TIMEOUT = 10
    TOP_CARD = "pv-top-card"
    HUMAN_DELAY_MIN = 1
    HUMAN_DELAY_MAX = 8

    def human_pause(self, min_seconds=None, max_seconds=None):
        """Pause with random mouse jitter to mimic slower human interactions."""
        min_seconds = min_seconds or self.HUMAN_DELAY_MIN
        max_seconds = max_seconds or self.HUMAN_DELAY_MAX
        actions.human_delay(self.driver, min_seconds=min_seconds, max_seconds=max_seconds)

    def wait(self, duration):
        min_seconds = max(duration, self.HUMAN_DELAY_MIN)
        max_seconds = max(self.HUMAN_DELAY_MAX, min_seconds)
        self.human_pause(min_seconds=min_seconds, max_seconds=max_seconds)

    def focus(self):
        self.driver.execute_script('alert("Focus window")')
        try:
            WebDriverWait(self.driver, 2).until(EC.alert_is_present())
            self.driver.switch_to.alert.accept()
        except (NoAlertPresentException, TimeoutException):
            pass

    def mouse_click(self, elem):
        self.human_pause()
        action = webdriver.ActionChains(self.driver)
        # Hover with small offsets to look less robotic before caller clicks the element.
        try:
            bounds = elem.size or {}
            max_x = max(1, int(bounds.get("width", 4)))
            max_y = max(1, int(bounds.get("height", 4)))
            offset_x = random.randint(-min(6, max_x // 3), min(6, max_x // 3))
            offset_y = random.randint(-min(6, max_y // 3), min(6, max_y // 3))
        except Exception:
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-3, 3)

        hover_pause = random.uniform(0.12, 0.35)
        settle_pause = random.uniform(0.05, 0.2)
        action.move_to_element(elem).pause(hover_pause).move_by_offset(offset_x, offset_y).pause(settle_pause).perform()

    def wait_for_element_to_load(self, by=By.CLASS_NAME, name="pv-top-card", base=None):
        base = base or self.driver
        return WebDriverWait(base, self.WAIT_FOR_ELEMENT_TIMEOUT).until(
            EC.presence_of_element_located(
                (
                    by,
                    name
                )
            )
        )

    def wait_for_all_elements_to_load(self, by=By.CLASS_NAME, name="pv-top-card", base=None):
        base = base or self.driver
        return WebDriverWait(base, self.WAIT_FOR_ELEMENT_TIMEOUT).until(
            EC.presence_of_all_elements_located(
                (
                    by,
                    name
                )
            )
        )


    def is_signed_in(self):
        try:
            WebDriverWait(self.driver, self.WAIT_FOR_ELEMENT_TIMEOUT).until(
                EC.presence_of_element_located(
                    (
                        By.CLASS_NAME,
                        c.VERIFY_LOGIN_ID,
                    )
                )
            )

            self.driver.find_element(By.CLASS_NAME, c.VERIFY_LOGIN_ID)
            return True
        except Exception as e:
            pass
        return False

    def scroll_to_half(self):
        actions.human_like_scroll(self.driver, target_ratio=0.5)
        self.human_pause()

    def scroll_to_bottom(self):
        actions.human_like_scroll(self.driver, target_ratio=1.0)
        self.human_pause()

    def scroll_class_name_element_to_page_percent(self, class_name:str, page_percent:float):
        self.driver.execute_script(
            f'elem = document.getElementsByClassName("{class_name}")[0]; elem.scrollTo(0, elem.scrollHeight*{str(page_percent)});'
        )
        self.human_pause()

    def __find_element_by_class_name__(self, class_name):
        try:
            self.driver.find_element(By.CLASS_NAME, class_name)
            return True
        except:
            pass
        return False

    def __find_element_by_xpath__(self, tag_name):
        try:
            self.driver.find_element(By.XPATH,tag_name)
            return True
        except:
            pass
        return False

    def __find_enabled_element_by_xpath__(self, tag_name):
        try:
            elem = self.driver.find_element(By.XPATH,tag_name)
            return elem.is_enabled()
        except:
            pass
        return False

    @classmethod
    def __find_first_available_element__(cls, *args):
        for elem in args:
            if elem:
                return elem[0]
