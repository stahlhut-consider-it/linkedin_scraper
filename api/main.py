"""FastAPI app that wraps the linkedin_scraper with session management."""

import asyncio
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import zendriver as zd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from linkedin_scraper import Person, actions

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin_scraper.api")


def _env_bool(name: str, default: bool = True) -> bool:
    """Parse truthy/falsey environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() not in {"0", "false", "no", "off"}


class ScrapeRequest(BaseModel):
    linkedin_url: HttpUrl


class SessionUnavailableError(Exception):
    """Raised when the browser is busy logging in or restarting."""


class SessionManager:
    def __init__(self, *, headless: bool = True) -> None:
        self.headless = headless
        self.browser: Optional[zd.Browser] = None
        self.tab: Optional[zd.Tab] = None
        self.available: bool = False
        self.lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.refresh_task: Optional[asyncio.Task] = None
        self.refresh_min_seconds = 30 * 60
        self.refresh_max_seconds = 90 * 60

    @property
    def is_available(self) -> bool:
        return self.available and self.tab is not None

    async def start(self) -> None:
        try:
            await self._reset_and_login()
        except Exception:
            logger.exception("Failed to log into LinkedIn on startup.")
            raise
        self.refresh_task = asyncio.create_task(self._refresh_loop())

    async def _reset_and_login(self) -> None:
        async with self.lock:
            self.available = False
            await self._stop_browser()
            logger.info("Logging into LinkedIn...")
            await self._start_browser_and_login()
            self.available = True
            logger.info("Logged in; API ready.")

    async def _start_browser_and_login(self) -> None:
        config = actions.build_browser_config(headless=self.headless)
        browser = await actions.start_browser(config)
        tab = await browser.get("https://www.linkedin.com/")
        tab = await actions.login(tab, timeout=20)
        self.browser = tab.browser or browser
        self.tab = tab

    async def _stop_browser(self) -> None:
        if self.browser:
            try:
                await self.browser.stop()
            except Exception as exc:
                logger.warning("Error while stopping browser: %s", exc)
        self.browser = None
        self.tab = None

    async def refresh_session(self) -> None:
        await self._reset_and_login()

    async def _refresh_loop(self) -> None:
        while not self.stop_event.is_set():
            wait_seconds = random.randint(self.refresh_min_seconds, self.refresh_max_seconds)
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=wait_seconds)
                break
            except asyncio.TimeoutError:
                pass
            try:
                logger.info("Refreshing LinkedIn session...")
                await self.refresh_session()
            except Exception:
                self.available = False
                logger.exception("Failed to refresh session; API paused until next attempt.")

    async def scrape_profile(self, linkedin_url: str) -> str:
        if not self.is_available:
            raise SessionUnavailableError("Anmeldung läuft – bitte kurz warten.")
        async with self.lock:
            if not self.is_available or not self.tab:
                raise SessionUnavailableError("Anmeldung läuft – bitte kurz warten.")
            person = Person(linkedin_url, driver=self.tab, scrape=False, close_on_complete=False)
            await person.scrape_async(close_on_complete=False)
            return str(person)

    async def stop(self) -> None:
        self.stop_event.set()
        if self.refresh_task:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
        async with self.lock:
            self.available = False
            await self._stop_browser()


class DailyRateLimiter:
    def __init__(self, limit: int = 50) -> None:
        self.limit = limit
        self.count = 0
        self.tz = datetime.now().astimezone().tzinfo or timezone.utc
        self._reset_at = self._next_reset_at()
        self.lock = asyncio.Lock()
        self.stop_event = asyncio.Event()
        self.reset_task: Optional[asyncio.Task] = None

    def _now(self) -> datetime:
        return datetime.now(tz=self.tz)

    def _next_reset_at(self, *, now: Optional[datetime] = None) -> datetime:
        now = now or self._now()
        tomorrow = (now + timedelta(days=1)).date()
        return datetime.combine(tomorrow, datetime.min.time(), tzinfo=self.tz)

    def _reset_if_due(self, *, now: Optional[datetime] = None) -> None:
        now = now or self._now()
        if now >= self._reset_at:
            self.count = 0
            self._reset_at = self._next_reset_at(now=now)

    async def start(self) -> None:
        self.reset_task = asyncio.create_task(self._reset_loop())

    async def stop(self) -> None:
        self.stop_event.set()
        if self.reset_task:
            self.reset_task.cancel()
            try:
                await self.reset_task
            except asyncio.CancelledError:
                pass

    async def _reset_loop(self) -> None:
        while not self.stop_event.is_set():
            now = self._now()
            wait_seconds = max((self._reset_at - now).total_seconds(), 0)
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=wait_seconds)
                break
            except asyncio.TimeoutError:
                pass
            async with self.lock:
                self._reset_if_due()

    async def try_acquire(self) -> Tuple[bool, datetime]:
        async with self.lock:
            self._reset_if_due()
            if self.count >= self.limit:
                return False, self._reset_at
            self.count += 1
            return True, self._reset_at

    async def refund(self) -> None:
        async with self.lock:
            self._reset_if_due()
            if self.count > 0:
                self.count -= 1

    async def snapshot(self) -> dict:
        async with self.lock:
            self._reset_if_due()
            return {
                "limit": self.limit,
                "used": self.count,
                "remaining": max(self.limit - self.count, 0),
                "next_reset_at": self._reset_at.isoformat(),
            }


app = FastAPI(title="LinkedIn Scraper API", version="0.1.0")
session_manager = SessionManager(headless=_env_bool("LINKEDIN_SCRAPER_HEADLESS", False))
rate_limiter = DailyRateLimiter(limit=50)


@app.on_event("startup")
async def on_startup() -> None:
    await session_manager.start()
    await rate_limiter.start()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await rate_limiter.stop()
    await session_manager.stop()


@app.post("/scrape")
async def scrape_profile(payload: ScrapeRequest) -> dict:
    allowed, reset_at = await rate_limiter.try_acquire()
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Tageslimit erreicht: maximal 50 Profile pro Tag.",
                "next_reset_at": reset_at.isoformat(),
            },
        )
    try:
        output = await session_manager.scrape_profile(str(payload.linkedin_url))
    except SessionUnavailableError as exc:
        await rate_limiter.refund()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception:
        await rate_limiter.refund()
        logger.exception("Unexpected scraping error.")
        raise HTTPException(status_code=500, detail="Scraping failed. Check server logs.")
    return {"output": output}


@app.get("/status")
async def status() -> dict:
    limiter_state = await rate_limiter.snapshot()
    return {"available": session_manager.is_available, "rate_limit": limiter_state}
