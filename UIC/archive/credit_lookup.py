import os
import json
import requests
from bs4 import BeautifulSoup
import re

CACHE_FILE = "data/credit_cache.json"

# Load or initialize the cache
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        credit_cache = json.load(f)
else:
    credit_cache = {}

def get_credit_from_uic_catalog(subject, course_num):
    import os
    import json
    import re
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException

    CACHE_FILE = "data/credit_cache.json"
    key = f"{subject} {course_num}"

    # Load or init cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            credit_cache = json.load(f)
    else:
        credit_cache = {}

    if key in credit_cache and credit_cache[key] != "???":
        return credit_cache[key]

    # Set up headless Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print(f"[ERROR] Could not start ChromeDriver: {e}")
        credit_cache[key] = "???"
        with open(CACHE_FILE, "w") as f:
            json.dump(credit_cache, f, indent=2)
        return "???"

    try:
        url = f"https://catalog.uic.edu/search/?P={subject}%20{course_num}"
        driver.get(url)

        # Wait for <h3> elements to load
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.TAG_NAME, "h3"))
        )

        h3_tags = driver.find_elements(By.TAG_NAME, "h3")
        for tag in h3_tags:
            text = tag.text.strip()
            if f"{subject} {course_num}" in text:
                match = re.search(r"(\d+(?:\.\d+)?)\s+hours", text, re.IGNORECASE)
                if match:
                    credit = match.group(1)
                    credit_cache[key] = credit
                    with open(CACHE_FILE, "w") as f:
                        json.dump(credit_cache, f, indent=2)
                    print(f"✅ {key}: {credit}")
                    driver.quit()
                    return credit

    except TimeoutException:
        print(f"[TIMEOUT] {key} took too long to load")
    except Exception as e:
        print(f"[ERROR] {key}: {e}")
    finally:
        driver.quit()

    credit_cache[key] = "???"
    with open(CACHE_FILE, "w") as f:
        json.dump(credit_cache, f, indent=2)
    print(f"❌ {key}: ???")
    return "???"
