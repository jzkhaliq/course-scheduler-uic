import requests
import os
from collections import defaultdict
from bs4 import BeautifulSoup
import re

# Term codes
terms = {
    "Fall": "420248",
    "Spring": "420251"
}

all_courses = []  # to collect all fall + spring courses

subject = "Computer Science"
subject_code = "CSC"

base_url = "https://apps.uis.edu/dynamic-course-schedule/api/course"
output_dir = os.path.join("uis", "data", subject_code)
os.makedirs(output_dir, exist_ok=True)


# Master course data
offerings = defaultdict(lambda: {"fall": 0, "spring": 0})
timings = defaultdict(list)

def normalize_code(subject, number):
    total_len = 8
    joined = subject + number
    underscores_needed = total_len - len(joined)
    return subject + ("_" * underscores_needed) + number

# Convert times
def time_to_minutes(tstr):
    tstr = tstr.strip()
    parts = tstr.replace("AM", " AM").replace("PM", " PM").split()
    hh, mm = map(int, parts[0].split(":"))
    if "PM" in parts[1] and hh != 12:
        hh += 12
    if "AM" in parts[1] and hh == 12:
        hh = 0
    return hh * 60 + mm

day_abbrevs = {
    "Monday": "M", "Tuesday": "T", "Wednesday": "W",
    "Thursday": "R", "Friday": "F", "Saturday": "S", "Sunday": "U"
}

# Fetch courses for each term
for term_name, term_code in terms.items():
    print(f"\n📅 Fetching {term_name} courses...")

    params = {
        "filter[term_cd]": term_code,
        "filter[crs_subj_desc]": subject,
        "page": 1,
        "limit": 100
    }

    while True:
        response = requests.get(base_url, params=params)
        data = response.json()
        results = data.get("data", [])
        
        if not results:
            break

        print(f"✅ {term_name} Page {params['page']}: {len(results)} courses")
        params["page"] += 1

        all_courses.extend(results)

        for course in results:
            code = f"{subject_code}___{course['crs_nbr'].zfill(3)}"
            offerings[code][term_name.lower()] = 1

            crn = course.get("crn", "00000")
            meeting_days = course.get("meeting_days", "").strip()
            meeting_time = course.get("meeting_time", "").strip()

            if not meeting_time or not meeting_days:
                continue

            try:
                start, end = meeting_time.split("-")
                start_min = time_to_minutes(start)
                end_min = time_to_minutes(end)
            except:
                continue

            days = [day_abbrevs.get(d.strip()) for d in meeting_days.split(",") if d.strip() in day_abbrevs]
            if not days:
                continue

            for d in days:
                offset = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4, "S": 5, "U": 6}[d]
                base = offset * 24 * 60
                timings[code].append((crn, base + start_min, base + end_min))

# --------------- COURSE OFFERING ---------------
valid_courses = []

with open(f"{output_dir}/courseoffering_{subject_code}.txt", "w") as f:
    for code in sorted(offerings):
        fall = offerings[code]["fall"]
        spring = offerings[code]["spring"]
        if fall + spring == 2:
            continue  # ❌ skip if offered in both

        subject, number = code.split("___")
        norm_code = normalize_code(subject, number)

        f.write(f"{norm_code}\t{fall}\t{spring}\n")
        valid_courses.append(norm_code)



# --------------- COURSE TIMING ---------------
with open(f"{output_dir}/coursetiming_{subject_code}.txt", "w") as f:
    for code, sessions in timings.items():
        subject, number = code.split("___") if "___" in code else (code[:3], code[3:])
        norm_code = normalize_code(subject, number)

        # Group sessions by CRN
        crn_dict = defaultdict(list)
        for crn, start, end in sessions:
            crn_dict[crn].append((start, end))

        num_crns = len(crn_dict)

        for crn, times in crn_dict.items():
            f.write(f"{norm_code}\t{num_crns}\t{len(times)}")
            for start, end in times:
                f.write(f"\t{crn}\t{start}\t{end}")
            f.write("\n")



# --------------- MASTER COURSE LIST ---------------
master_file = f"{output_dir}/mastercourselist_{subject_code}.txt"

# 1) Build credits from API (do NOT parse generic hours from description)
api_credits = {}
for course in all_courses:
    code = normalize_code(course["crs_subj_cd"], course["crs_nbr"].zfill(3))
    desc = (course.get("crs_desc_catalog") or "").strip()
    min_raw = course.get("crs_min_credit_hour_nbr")
    max_raw = course.get("crs_max_credit_hour_nbr")

    def parse_api_credits(min_raw, max_raw, desc):
        try:
            min_credit = int(float(min_raw)) if min_raw is not None else None
            max_credit = int(float(max_raw)) if max_raw is not None else None

            if min_credit is not None and max_credit is not None:
                return list(range(min_credit, max_credit + 1))
            if min_credit is not None:
                return [min_credit]

            # VERY narrow fallback: only support "maximum of X hours"
            m = re.search(r"maximum of\s+(\d+)\s+hours", desc, flags=re.I)
            if m:
                x = int(m.group(1))
                return list(range(1, x + 1))
        except:
            pass
        return ["???"]

    api_credits[code] = parse_api_credits(min_raw, max_raw, desc)

# 2) Build credits from catalog (hours span OR end of title ONLY; never from description)
catalog_url = f"https://catalog.uis.edu/coursedescriptions/{subject_code.lower()}/"
resp = requests.get(catalog_url, timeout=30)
soup = BeautifulSoup(resp.text, "html.parser")

def parse_hours_text(text: str):
    text = text.strip()

    # Range like "1-12 Hours" or with en dash "1–12 Hours"
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*Hours?\s*(?:\.|\)|$)", text, flags=re.I)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        return list(range(lo, hi + 1))

    # Single like "4 Hours"
    m = re.search(r"(\d+)\s*Hours?\s*(?:\.|\)|$)", text, flags=re.I)
    if m:
        return [int(m.group(1))]

    return None

catalog_credits = {}
for blk in soup.select("div.courseblock"):
    title_el = blk.select_one(".courseblocktitle")
    if not title_el:
        continue
    title_text = title_el.get_text(" ", strip=True)

    # e.g., "CSC 399. Tutorial. 1-12 Hours."
    m = re.search(r"\b([A-Z]{3,4})\s+(\d{3})\b", title_text)
    if not m:
        continue
    subj, num = m.group(1), m.group(2)
    code = normalize_code(subj, num)

    # Prefer explicit hours element if present
    hours_el = blk.select_one(".courseblockhours, .hours")
    credits = None
    if hours_el:
        credits = parse_hours_text(hours_el.get_text(" ", strip=True))

    # Fallback: parse ONLY from the end of the title
    if credits is None:
        credits = parse_hours_text(title_text)

    # No description parsing at all (prevents "last 12 hours" false positives)
    catalog_credits[code] = credits if credits is not None else ["???"]

# 3) Merge API + Catalog (prefer API unless it's ??? or 0)
all_codes = sorted(set(api_credits.keys()) | set(catalog_credits.keys()))
with open(master_file, "w") as f:
    for code in all_codes:
        credits = api_credits.get(code)
        if not credits or credits == ["???"] or credits == [0]:
            credits = catalog_credits.get(code, ["???"])
        credit_str = ",".join(str(c) for c in credits)
        f.write(f"{code}\t{credit_str}\n")

print(f"✅ Wrote mastercourselist to {master_file} (API ∪ Catalog)")

# --------------- PREREQUISITES ---------------

catalog_url = "https://catalog.uis.edu/coursedescriptions/csc/"
reqs_file = f"{output_dir}/prerequisites_{subject_code}.txt"

resp = requests.get(catalog_url)
soup = BeautifulSoup(resp.text, "html.parser")
entries = soup.select("div.courseblock")

with open(reqs_file, "w") as f:
    for block in entries:
        header = block.select_one(".courseblocktitle").text.strip()
        desc = block.select_one(".courseblockdesc").text.strip()

        match = re.search(r"([A-Z]{3,4})\s+(\d{3})", header)
        if not match:
            continue
        subj, num = match.groups()
        course_code = normalize_code(subj, num)

        # Look for 'Prerequisite' line
        if "Prerequisite" in desc:
            prereq_line = desc.split("Prerequisite")[1].split(".")[0]
            found = re.findall(r"([A-Z]{3,4})\s+(\d{3})", prereq_line)
            seen = set()

            for psubj, pnum in found:
                prereq_code = normalize_code(psubj, pnum)
                if prereq_code == course_code or (prereq_code, course_code) in seen:
                    continue
                flag = -1 if " or " in prereq_line.lower() else 0
                f.write(f"{prereq_code}\t{course_code}\t{flag}\n")
                seen.add((prereq_code, course_code))

print(f"✅ Wrote prerequisites to {reqs_file}")




print("\n✅ Combined Fall + Spring data written to uis/data/")


