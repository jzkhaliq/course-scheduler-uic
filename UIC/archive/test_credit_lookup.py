import requests
from bs4 import BeautifulSoup
import re

subject = "CS"
course_num = "113"
url = f"https://catalog.uic.edu/search/?P={subject}%20{course_num}"

headers = {'User-Agent': 'Mozilla/5.0'}
resp = requests.get(url, headers=headers, timeout=10)
resp.raise_for_status()

soup = BeautifulSoup(resp.text, "html.parser")

course_blocks = soup.select("div.searchresult")

found = False

for block in course_blocks:
    text = block.get_text(" ", strip=True)

    if f"{subject} {course_num}" not in text:
        continue

    print("=== BLOCK FOUND ===")
    print(text)
    print()

    match = re.search(
        r"(\d+(?:\.\d+)?)(?:\s+to\s+\d+(?:\.\d+)?)?\s+(?:graduate\s+|undergraduate\s+)?hours?\.?",
        text,
        re.IGNORECASE
    )

    if match:
        print(f"✅ Found credit: {match.group(1)}")
        found = True
        break

if not found:
    print("❌ No match found.")
