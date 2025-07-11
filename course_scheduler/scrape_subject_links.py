import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

BASE_URLS = {
    "fall": "https://webcs7.osss.uic.edu/schedule-of-classes/static/schedules/fall-2024/",
    "spring": "https://webcs7.osss.uic.edu/schedule-of-classes/static/schedules/spring-2025/",
}

CS_URLS = {
    "fall": BASE_URLS["fall"] + "CS.html",
    "spring": BASE_URLS["spring"] + "CS.html"
}

OUTPUTS = {
    "offering": [],
    "timing": {},
    "prereq": [],
    "master": {}
}


def load_master_course_list():
    with open("data/mastercourselist_cs.txt") as f:
        for line in f:
            code, credits = line.strip().split("\t")
            OUTPUTS["master"][code.replace("___", " ")] = credits


def minutes_from_monday(time_str, days_str):
    day_map = {'M': 0, 'T': 1, 'W': 2, 'R': 3, 'F': 4}
    if "ARRANGED" in time_str.upper() or not days_str.strip():
        return []

    try:
        start, end = [datetime.strptime(t.strip(), '%I:%M %p') for t in time_str.split('-')]
        return [
            [
                day_map[d] * 1440 + start.hour * 60 + start.minute,
                day_map[d] * 1440 + end.hour * 60 + end.minute
            ]
            for d in days_str if d in day_map
        ]
    except Exception as e:
        print(f"Error parsing time or days: {e} — '{time_str}' / '{days_str}'")
        return []


def parse_course_table(url, term):
    print(f"[INFO] Fetching {term.capitalize()} CS page...")
    soup = BeautifulSoup(requests.get(url).text, "html.parser")
    courses = soup.find_all("div", class_="course")
    print(f"[INFO] Found {len(courses)} course blocks for {term}")

    for course in courses:
        text = course.get_text(" ", strip=True)
        match = re.search(r"(CS\s+\d{3})", text)
        if not match:
            continue
        code = match.group(1)
        code_title = text[:60]

        OUTPUTS["prereq"].append(f"{code}\t???")

        rows = course.find_all('tr')
        found_lecture = False

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 6:
                continue

            course_type = cols[1].text.strip()
            if not course_type.startswith("LEC"):
                continue

            crn = cols[0].text.strip()
            time = cols[2].text.strip()
            days = cols[3].text.strip()
            room = cols[4].text.strip()
            building = cols[5].text.strip()
            instructor = cols[6].text.strip()
            location = f"{building} {room}".strip()
            section_id = crn[-3:]

            print(f"[MATCH] Looking for {code.replace(' ', '___')}")

            credits = OUTPUTS["master"].get(code.replace(" ", "___"), "???")


            OUTPUTS["offering"].append([
                code, code_title, crn, section_id, instructor, days, time,
                location, credits, "open", term
            ])

            mins = minutes_from_monday(time, days)
            for pair in mins:
                OUTPUTS["timing"][f"{code}-{section_id}"] = pair

            found_lecture = True

        # Optional: print only if course has a lecture
        if found_lecture:
            print(f"[DEBUG] Sections for {code_title}: {int(found_lecture)}")


def write_outputs():
    with open("courseoffering_cs.txt", "w") as f:
        for row in OUTPUTS["offering"]:
            f.write("\t".join(row) + "\n")

    with open("coursetiming_cs.txt", "w") as f:
        for key, pair in OUTPUTS["timing"].items():
            f.write(f"{key}\t{pair[0]}\t{pair[1]}\n")

    with open("prerequisites_cs.txt", "w") as f:
        for row in OUTPUTS["prereq"]:
            f.write(row + "\n")


    print(f"[INFO] Wrote {len(OUTPUTS['offering'])} to courseoffering_cs.txt")
    print(f"[INFO] Wrote {len(OUTPUTS['timing'])} to coursetiming_cs.txt")
    print(f"[INFO] Wrote {len(OUTPUTS['prereq'])} to prerequisites_cs.txt")
    print(f"[INFO] Wrote {len(OUTPUTS['master'])} to mastercourselist_cs.txt")


if __name__ == "__main__":
    load_master_course_list()
    for term in ["fall", "spring"]:
        url = CS_URLS[term]
        parse_course_table(url, term)
    write_outputs()
