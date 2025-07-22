### ---------- credits_per_major.py ---------- ###
import requests
from bs4 import BeautifulSoup
import re
import json

BASE_URL = "https://catalog.uic.edu"
START_URL = f"{BASE_URL}/ucat/colleges-depts/"

def get_all_college_dept_links():
    response = requests.get(START_URL)
    soup = BeautifulSoup(response.text, "html.parser")

    links = set()
    for a in soup.find_all("a", href=True):
        href = a['href']
        if href.startswith("/ucat/colleges-depts/") and not href.endswith("index.html"):
            links.add(BASE_URL + href)

    return sorted(links)

def extract_degrees_and_credits(url):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for table in soup.find_all("table"):
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if not any("hours" in h or "credits" in h for h in headers):
                continue

            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                major_text = cells[0].get_text(" ", strip=True)
                credit_text = cells[-1].get_text(" ", strip=True)

                credit_match = re.search(r"\b(\d{2,3})\b", credit_text)
                if credit_match:
                    major = re.sub(r"\s+", " ", major_text)
                    major = major.replace("—", "-").strip()
                    major = re.sub(r"\s+[ab]$", "", major)  # Remove trailing footnote letters

                    credits = int(credit_match.group(1))
                    results.append((major, credits))

        return results

    except Exception as e:
        print(f"[ERROR] {url}: {e}")
        return []

def main():
    all_links = get_all_college_dept_links()
    degree_data = {}

    for url in all_links:
        results = extract_degrees_and_credits(url)
        for major, credits in results:
            name = major.lower()

            if not major.strip():
                continue
            if credits < 120:
                continue
            if any(x in name for x in ["minor", "certificate", "concentration", "track", "endorsement", "university writing requirement"]):
                continue

            if major not in degree_data:
                degree_data[major] = credits
                print(f"✅ {major}: {credits}")
            else:
                print(f"⚠️ Duplicate ignored: {major}")

    with open("data/all_uic_degrees.json", "w") as f:
        json.dump(degree_data, f, indent=2)

    print(f"\n🎉 Done. Extracted {len(degree_data)} majors.")

if __name__ == "__main__":
    main()
