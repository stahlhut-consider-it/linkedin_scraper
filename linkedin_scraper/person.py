import asyncio
import os
from typing import Any, Dict, List, Optional

import zendriver as zd

from . import actions
from . import constants as c
from .by import By
from .objects import Accomplishment, Contact, Education, Experience, Interest, Scraper


class Person(Scraper):
    __TOP_CARD = "main"
    __WAIT_FOR_ELEMENT_TIMEOUT = 5

    def __init__(
        self,
        linkedin_url: Optional[str] = None,
        name: Optional[str] = None,
        about: Optional[str] = None,
        experiences: Optional[List[Experience]] = None,
        educations: Optional[List[Education]] = None,
        interests: Optional[List[Interest]] = None,
        accomplishments: Optional[List[Accomplishment]] = None,
        company: Optional[str] = None,
        job_title: Optional[str] = None,
        contacts: Optional[List[Contact]] = None,
        driver: Optional[zd.Tab | zd.Browser] = None,
        get: bool = True,
        scrape: bool = True,
        close_on_complete: bool = True,
        time_to_wait_after_login: int = 0,
        headless: bool = False,
    ):
        self.linkedin_url = linkedin_url
        self.name = name
        self.about = about or []
        self.experiences = experiences or []
        self.educations = educations or []
        self.interests = interests or []
        self.accomplishments = accomplishments or []
        self.also_viewed_urls: List[str] = []
        self.contacts = contacts or []

        self._external_loop: Optional[asyncio.AbstractEventLoop] = None
        try:
            self._external_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._external_loop = None

        # Only create our own loop when none is running already.
        if self._external_loop is None:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        else:
            self.loop = None

        self._pending_nav: Optional[asyncio.Task] = None
        self._pending_scrape: Optional[asyncio.Task] = None

        if isinstance(driver, zd.Browser):
            self.browser = driver
            if get and linkedin_url:
                if self._external_loop:
                    self._pending_nav = asyncio.create_task(self.browser.get(linkedin_url))
                    self.driver = None
                else:
                    self.driver = self._run(self.browser.get(linkedin_url or "about:blank"))
            else:
                self.driver = None
            self._owns_browser = False
        elif isinstance(driver, zd.Tab):
            self.driver = driver
            self.browser = driver.browser
            self._owns_browser = False
            if get and linkedin_url:
                if self._external_loop:
                    self._pending_nav = asyncio.create_task(self.browser.get(linkedin_url))
                else:
                    self.driver = self._run(self.browser.get(linkedin_url))
        else:
            if self._external_loop:
                raise RuntimeError(
                    "Person cannot start a browser while an event loop is already running. "
                    "Start a browser with actions.start_browser() and pass the tab into Person."
                )
            config = actions.build_browser_config(headless=headless)
            self.browser = self._run(actions.start_browser(config))
            self._owns_browser = True
            target_url = linkedin_url or "about:blank"
            self.driver = self._run(self.browser.get(target_url)) if get else None

        if self.driver and get and linkedin_url and not self._external_loop:
            self._run(actions.reject_cookies(self.driver, timeout=15, retries=2, retry_delay=2))

        if scrape and self.driver:
            if self._external_loop:
                self._pending_scrape = asyncio.create_task(
                    self.scrape_async(close_on_complete=close_on_complete)
                )
            else:
                self.scrape(close_on_complete=close_on_complete)

    def add_about(self, about):
        self.about.append(about)

    def add_experience(self, experience):
        self.experiences.append(experience)

    def add_education(self, education):
        self.educations.append(education)

    def add_interest(self, interest):
        self.interests.append(interest)

    def add_accomplishment(self, accomplishment):
        self.accomplishments.append(accomplishment)

    def add_location(self, location):
        self.location = location

    def add_contact(self, contact):
        self.contacts.append(contact)

    async def _ensure_navigation(self):
        if self._pending_nav:
            try:
                self.driver = await self._pending_nav
            except Exception:
                # If navigation failed, keep existing driver reference.
                self.driver = self.driver or None
            self._pending_nav = None

    async def _is_signed_in_async(self) -> bool:
        try:
            await actions.wait_for_element(
                self.driver,
                by=By.CLASS_NAME,
                name=c.VERIFY_LOGIN_ID,
                timeout=self.WAIT_FOR_ELEMENT_TIMEOUT,
            )
            return True
        except Exception:
            pass
        try:
            await actions.wait_for_element(
                self.driver,
                by=By.CSS_SELECTOR,
                name="input[placeholder*='Search']",
                timeout=self.WAIT_FOR_ELEMENT_TIMEOUT,
            )
            return True
        except Exception:
            pass
        return False

    def scrape(self, close_on_complete: bool = True):
        if not self.driver:
            return
        if self._external_loop:
            # Schedule in the running loop; caller can await the task if needed.
            self._pending_scrape = asyncio.create_task(
                self.scrape_async(close_on_complete=close_on_complete)
            )
            return self._pending_scrape
        if self.is_signed_in():
            self._run(self._scrape_logged_in(close_on_complete=close_on_complete))
        else:
            print("you are not logged in!")
            if close_on_complete and self._owns_browser and self.browser:
                self._run(self.browser.stop())

    async def scrape_async(self, close_on_complete: bool = True):
        if not self.driver and self._pending_nav:
            await self._ensure_navigation()
        if not self.driver:
            return
        # If a navigation was scheduled, wait for it.
        await self._ensure_navigation()

        if await self._is_signed_in_async():
            await self._scrape_logged_in(close_on_complete=close_on_complete)
        else:
            print("you are not logged in!")
            if close_on_complete and self._owns_browser and self.browser:
                await self.browser.stop()

    async def _scrape_logged_in(self, close_on_complete: bool = True):
        driver = self.driver
        if not driver:
            return

        await actions.wait_for_element(
            driver,
            by=By.TAG_NAME,
            name=self.__TOP_CARD,
            timeout=self.__WAIT_FOR_ELEMENT_TIMEOUT,
        )
        try:
            await driver.bring_to_front()
        except Exception:
            pass
        await actions.human_delay(driver, min_seconds=2, max_seconds=4)

        await self._collect_name_and_location()
        await actions.human_delay(driver, min_seconds=1, max_seconds=2.5)

        self.open_to_work = await self._is_open_to_work()

        await self._collect_about()
        await driver.evaluate(
            "window.scrollTo(0, Math.ceil(document.body.scrollHeight/2));"
        )
        await actions.human_delay(driver, min_seconds=1, max_seconds=2.5)
        await driver.evaluate(
            "window.scrollTo(0, Math.ceil(document.body.scrollHeight/1.5));"
        )
        await actions.human_delay(driver, min_seconds=1, max_seconds=2.5)

        await self._collect_experiences()
        await actions.human_delay(driver, min_seconds=1, max_seconds=2.5)

        await self._collect_educations()
        await actions.human_delay(driver, min_seconds=1, max_seconds=2.5)

        await driver.get(self.linkedin_url)
        await actions.human_delay(driver, min_seconds=1, max_seconds=2.5)

        await self._collect_interests()
        await self._collect_accomplishments()
        await self._collect_contacts()

        if close_on_complete and self._owns_browser and self.browser:
            await self.browser.stop()

    async def _is_open_to_work(self) -> bool:
        try:
            return bool(
                await self.driver.evaluate(
                    """
                    const badge = document.querySelector('.pv-top-card-profile-picture img');
                    return badge && badge.title && badge.title.includes('#OPEN_TO_WORK');
                    """
                )
            )
        except Exception:
            return False

    async def _collect_experiences(self):
        if not self.linkedin_url or not self.driver:
            return
        url = os.path.join(self.linkedin_url, "details/experience")
        await self.driver.get(url)
        await actions.human_delay(self.driver, min_seconds=1, max_seconds=2.5)
        try:
            await self.driver.bring_to_front()
        except Exception:
            pass
        await actions.human_like_scroll(self.driver, target_ratio=0.5)
        await actions.human_like_scroll(self.driver, target_ratio=1.0)

        script = """
        (() => {
            function parseTimes(str) {
                if (!str) return {from: null, to: null, duration: null};
                const parts = str.split("·");
                const datePart = (parts[0] || "").trim();
                const duration = parts.length > 1 ? (parts[1] || "").trim() : null;
                const segments = datePart.split(" ").filter(Boolean);
                const from = segments.slice(0, 2).join(" ") || null;
                const to = segments.length > 3 ? segments.slice(3).join(" ").trim() || null : null;
                return {from, to, duration};
            }
            const items = Array.from(document.querySelectorAll("li.pvs-list__paged-list-item"));
            const result = [];
            for (const item of items) {
                const entity = item.querySelector("div[data-view-name='profile-component-entity']");
                if (!entity) continue;
                const blocks = Array.from(entity.children || []);
                const logoBlock = blocks[0];
                const details = blocks[1];
                const companyLink = logoBlock?.querySelector("a")?.href || null;
                const detailsBlocks = details ? Array.from(details.children || []) : [];
                const summaryDetails = detailsBlocks[0] || null;
                const summaryText = detailsBlocks[1] || null;
                const outerWrapper = summaryDetails?.querySelector(":scope > *");
                const outerPositions = outerWrapper ? Array.from(outerWrapper.children || []) : [];
                let positionTitle = "";
                let company = "";
                let workTimes = "";
                let location = "";
                if (outerPositions.length === 4) {
                    positionTitle = (outerPositions[0].innerText || "").trim();
                    company = (outerPositions[1].innerText || "").trim();
                    workTimes = (outerPositions[2].innerText || "").trim();
                    location = (outerPositions[3].innerText || "").trim();
                } else if (outerPositions.length === 3) {
                    if ((outerPositions[2].innerText || "").includes("·")) {
                        positionTitle = (outerPositions[0].innerText || "").trim();
                        company = (outerPositions[1].innerText || "").trim();
                        workTimes = (outerPositions[2].innerText || "").trim();
                    } else {
                        company = (outerPositions[0].innerText || "").trim();
                        workTimes = (outerPositions[1].innerText || "").trim();
                        location = (outerPositions[2].innerText || "").trim();
                    }
                } else if (outerPositions.length) {
                    company = (outerPositions[0].innerText || "").trim();
                    workTimes = outerPositions.length > 1 ? (outerPositions[1].innerText || "").trim() : "";
                }
                const parsed = parseTimes(workTimes);
                const innerContainer = summaryText?.querySelector(".pvs-list__container");
                if (innerContainer) {
                    const innerItems = Array.from(innerContainer.querySelectorAll("li.pvs-list__paged-list-item"));
                    for (const inner of innerItems) {
                        const anchors = inner.querySelector("a");
                        const children = anchors ? Array.from(anchors.children || []) : [];
                        const tEl = children[0];
                        const wEl = children[1];
                        const locEl = children[2];
                        const innerTimes = parseTimes(wEl ? (wEl.innerText || "") : "");
                        result.push({
                            position_title: tEl ? (tEl.innerText || "").trim() : positionTitle,
                            institution_name: company,
                            location: locEl ? (locEl.innerText || "").trim() : location,
                            from_date: innerTimes.from,
                            to_date: innerTimes.to,
                            duration: innerTimes.duration,
                            description: (inner.innerText || "").trim(),
                            linkedin_url: companyLink,
                        });
                    }
                    continue;
                }
                result.push({
                    position_title: positionTitle,
                    institution_name: company,
                    location,
                    from_date: parsed.from,
                    to_date: parsed.to,
                    duration: parsed.duration,
                    description: summaryText ? (summaryText.innerText || "").trim() : "",
                    linkedin_url: companyLink,
                });
            }
            return result;
        })();
        """
        experiences: List[Dict[str, Any]] = await self.driver.evaluate(script, await_promise=True)
        for item in experiences or []:
            experience = Experience(
                position_title=item.get("position_title"),
                from_date=item.get("from_date"),
                to_date=item.get("to_date"),
                duration=item.get("duration"),
                location=item.get("location"),
                description=item.get("description"),
                institution_name=item.get("institution_name"),
                linkedin_url=item.get("linkedin_url"),
            )
            self.add_experience(experience)

    async def _collect_educations(self):
        if not self.linkedin_url or not self.driver:
            return
        url = os.path.join(self.linkedin_url, "details/education")
        await self.driver.get(url)
        await actions.human_delay(self.driver, min_seconds=1, max_seconds=2.5)
        try:
            await self.driver.bring_to_front()
        except Exception:
            pass
        await actions.human_like_scroll(self.driver, target_ratio=0.5)
        await actions.human_like_scroll(self.driver, target_ratio=1.0)

        script = """
        (() => {
            const items = Array.from(document.querySelectorAll("li.pvs-list__paged-list-item"));
            const result = [];
            for (const item of items) {
                const entity = item.querySelector("div[data-view-name='profile-component-entity']");
                if (!entity) continue;
                const blocks = Array.from(entity.children || []);
                const logoBlock = blocks[0];
                const details = blocks[1];
                const institutionLink = logoBlock?.querySelector("a")?.href || null;
                const detailsBlocks = details ? Array.from(details.children || []) : [];
                const summaryDetails = detailsBlocks[0] || null;
                const summaryText = detailsBlocks[1] || null;
                const outerWrapper = summaryDetails?.querySelector(":scope > *");
                const outerPositions = outerWrapper ? Array.from(outerWrapper.children || []) : [];
                const institution_name = outerPositions[0] ? (outerPositions[0].innerText || "").trim() : "";
                const degree = outerPositions[1] ? (outerPositions[1].innerText || "").trim() : null;
                let from_date = null;
                let to_date = null;
                if (outerPositions.length > 2) {
                    try {
                        const times = (outerPositions[2].innerText || "").trim().split(" ");
                        const dashIndex = times.indexOf("-");
                        if (dashIndex > 0) {
                            from_date = times[dashIndex-1];
                        }
                        if (dashIndex >= 0 && dashIndex < times.length - 1) {
                            to_date = times[times.length - 1];
                        }
                    } catch (e) {}
                }
                result.push({
                    institution_name,
                    degree,
                    from_date,
                    to_date,
                    description: summaryText ? (summaryText.innerText || "").trim() : "",
                    linkedin_url: institutionLink,
                });
            }
            return result;
        })();
        """
        educations: List[Dict[str, Any]] = await self.driver.evaluate(script, await_promise=True)
        for item in educations or []:
            education = Education(
                from_date=item.get("from_date"),
                to_date=item.get("to_date"),
                description=item.get("description"),
                degree=item.get("degree"),
                institution_name=item.get("institution_name"),
                linkedin_url=item.get("linkedin_url"),
            )
            self.add_education(education)

    async def _collect_name_and_location(self):
        if not self.driver:
            return
        data = await self.driver.evaluate(
            """
            (() => {
                const root = document.querySelector('main .mt2.relative') || document.querySelector('main');
                return {
                    name: root ? (root.querySelector('h1')?.innerText || '').trim() : '',
                    location: root ? (root.querySelector('.text-body-small.inline.t-black--light.break-words')?.innerText || '').trim() : ''
                };
            })();
            """
        )
        if data:
            self.name = data.get("name") or self.name
            self.location = data.get("location") or getattr(self, "location", None)

    async def _collect_about(self):
        if not self.driver:
            return
        about = await self.driver.evaluate(
            """
            (() => {
                const aboutSection = document.getElementById('about');
                if (!aboutSection) return null;
                const container = aboutSection.closest('section') || aboutSection.parentElement;
                const target = container?.querySelector('.display-flex') || container;
                return target?.innerText?.trim() || null;
            })();
            """
        )
        self.about = about

    async def _collect_interests(self):
        if not self.driver:
            return
        try:
            interest_titles = await self.driver.evaluate(
                """
                (() => {
                    const container = document.querySelector('.pv-profile-section.pv-interests-section.artdeco-container-card') ||
                                       document.querySelector('[id*=interests]');
                    const items = Array.from(container?.querySelectorAll('.pv-interest-entity, li.artdeco-list__item') || []);
                    return items.map(el => {
                        const target = el.querySelector('h3') || el.querySelector('span') || el;
                        return (target.innerText || '').trim();
                    }).filter(Boolean);
                })();
                """
            )
            for title in interest_titles or []:
                self.add_interest(Interest(title))
        except Exception:
            pass

    async def _collect_accomplishments(self):
        if not self.driver:
            return
        try:
            accomplishments = await self.driver.evaluate(
                """
                (() => {
                    const acc = document.querySelector('.pv-profile-section.pv-accomplishments-section.artdeco-container-card');
                    if (!acc) return [];
                    const result = [];
                    const blocks = acc.querySelectorAll('.pv-accomplishments-block__content.break-words');
                    blocks.forEach(block => {
                        const category = block.querySelector('h3')?.innerText?.trim() || '';
                        block.querySelectorAll('ul li').forEach(li => {
                            result.push({category, title: (li.innerText || '').trim()});
                        });
                    });
                    return result;
                })();
                """
            )
            for item in accomplishments or []:
                self.add_accomplishment(Accomplishment(item.get("category"), item.get("title")))
        except Exception:
            pass

    async def _collect_contacts(self):
        if not self.driver:
            return
        try:
            await self.driver.get("https://www.linkedin.com/mynetwork/invite-connect/connections/")
            await actions.human_delay(self.driver, min_seconds=1, max_seconds=2.5)
            contacts = await self.driver.evaluate(
                """
                (() => {
                    const cards = Array.from(document.querySelectorAll('.mn-connections .mn-connection-card'));
                    return cards.map(card => {
                        return {
                            url: card.querySelector('.mn-connection-card__link')?.href || null,
                            name: card.querySelector('.mn-connection-card__name')?.innerText?.trim() || '',
                            occupation: card.querySelector('.mn-connection-card__occupation')?.innerText?.trim() || ''
                        };
                    }).filter(item => item.name);
                })();
                """
            )
            for item in contacts or []:
                self.add_contact(
                    Contact(name=item.get("name"), occupation=item.get("occupation"), url=item.get("url"))
                )
        except Exception:
            pass

    @property
    def company(self):
        if self.experiences:
            return (
                self.experiences[0].institution_name
                if self.experiences[0].institution_name
                else None
            )
        else:
            return None

    @property
    def job_title(self):
        if self.experiences:
            return (
                self.experiences[0].position_title
                if self.experiences[0].position_title
                else None
            )
        else:
            return None

    def __repr__(self):
        return "<Person {name}\n\nAbout\n{about}\n\nExperience\n{exp}\n\nEducation\n{edu}\n\nInterest\n{int}\n\nAccomplishments\n{acc}\n\nContacts\n{conn}>".format(
            name=self.name,
            about=self.about,
            exp=self.experiences,
            edu=self.educations,
            int=self.interests,
            acc=self.accomplishments,
            conn=self.contacts,
        )
