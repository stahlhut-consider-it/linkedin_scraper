import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is importable when running the sample directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from linkedin_scraper import Person, actions


async def main():
    load_dotenv()
    email = os.getenv("LINKEDIN_USER")
    password = os.getenv("LINKEDIN_PASSWORD")

    config = actions.build_browser_config(headless=True)
    browser = await actions.start_browser(config)
    tab = await browser.get("https://www.linkedin.com/")
    await actions.login(tab, email, password)

    person = Person("https://www.linkedin.com/in/adrian0350", contacts=[], driver=tab, scrape=False, close_on_complete=False)
    await person.scrape_async(close_on_complete=False)

    print("Person: " + person.name)
    print("Person contacts: ")
    for contact in person.contacts:
        print("Contact: " + contact.name + " - " + contact.occupation + " -> " + contact.url)

    await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())
