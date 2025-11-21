import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Ensure the project root is importable when the script runs directly
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from linkedin_scraper import Person, actions

load_dotenv()  # pull values from a .env file into environment variables at runtime

driver_path = Path(os.getenv("CHROMEDRIVER_PATH", "./chromedriver")).expanduser()
if not driver_path.is_file():
    # Fallback to webdriver-manager to fetch a matching ChromeDriver
    driver_path = Path(ChromeDriverManager().install())

service = Service(str(driver_path))
driver = webdriver.Chrome(service=service)

email = os.getenv("LINKEDIN_USER")
password = os.getenv("LINKEDIN_PASSWORD")
actions.login(driver, email, password) # if email and password isnt given, it'll prompt in terminal
person = Person("https://www.linkedin.com/in/t-koch/", driver=driver)

print(person)
