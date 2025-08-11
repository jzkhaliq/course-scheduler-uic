import requests
import os
from collections import defaultdict
from bs4 import BeautifulSoup
import re

# ===================== CONFIG =====================

# Add majors here. "name" must match UIS API subject description; "code" is the subject code.
CATALOG_INDEX = "https://catalog.uis.edu/coursedescriptions/"

def get_catalog_subjects():
    """
    Scrape the UIS catalog subjects index and return:
      [{"name": "Computer Science", "code": "CSC"}, ...]
    """
    resp = requests.get(CATALOG_INDEX, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    subjects = []
    seen = set()

    # find all links to subject pages, e.g. /coursedescriptions/csc/
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not re.match(r"^/coursedescriptions/[a-z0-9-]+/?$", href):
            continue

        text = a.get_text(" ", strip=True)
        # Expect patterns like: "Computer Science (CSC)"
        m = re.search(r"^(.*?)\s*\(([^)]+)\)\s*$", text)
        if not m:
            # fallback: sometimes the code may be separate or missing; skip if no code
            continue

        name = m.group(1).strip()
        code_raw = m.group(2).strip()

        # Keep only letters in code, uppercase; common at UIS is 2–5 letters
        code = re.sub(r"[^A-Za-z]", "", code_raw).upper()
        if not (2 <= len(code) <= 5):
            continue

        # Deduplicate (some pages may repeat in mobile/desktop sections)
        key = (name, code)
        if key in seen:
            continue
        seen.add(key)

        subjects.append({"name": name, "code": code})

    return subjects

SUBJECTS = get_catalog_subjects()

TERMS = {
    "Fall": "420248",
    "Spring": "420251",
}

BASE_API = "https://apps.uis.edu/dynamic-course-schedule/api/course"
BASE_OUT = os.path.join("uis", "data")
os.makedirs(BASE_OUT, exist_ok=True)

# ===================== HELPERS =====================

def normalize_code(subject: str, number: str) -> str:
    total_len = 8
    joined = subject + number
    underscores_needed = total_len - len(joined)
    return subject + ("_" * underscores_needed) + number

def time_to_minutes(tstr: str) -> int:
    tstr = tstr.strip()
    parts = tstr.replace("AM", " AM").replace("PM", " PM").split()
    hh, mm = map(int, parts[0].split(":"))
    if "PM" in parts[1] and hh != 12:
        hh += 12
    if "AM" in parts[1] and hh == 12:
        hh = 0
    return hh * 60 + mm

DAY_OFFSETS = {"M":0, "T":1, "W":2, "R":3, "F":4, "S":5, "U":6}
DAY_ABBREVS = {
    "Monday":"M","Tuesday":"T","Wednesday":"W",
    "Thursday":"R","Friday":"F","Saturday":"S","Sunday":"U"
}

def parse_api_credits(min_raw, max_raw, desc: str):
    try:
        min_credit = int(float(min_raw)) if min_raw is not None else None
        max_credit = int(float(max_raw)) if max_raw is not None else None

        if min_credit is not None and max_credit is not None:
            lo, hi = (min_credit, max_credit) if min_credit <= max_credit else (max_credit, min_credit)
            return list(range(lo, hi + 1))
        if min_credit is not None:
            return [min_credit]

        # very narrow fallback from description
        m = re.search(r"maximum of\s+(\d+)\s+hours", desc or "", flags=re.I)
        if m:
            x = int(m.group(1))
            return list(range(1, x + 1))
    except:
        pass
    return ["???"]

def parse_hours_text(text: str):
    text = (text or "").strip()
    # handle hyphen or en dash
    m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*Hours?\s*(?:\.|\)|$)", text, flags=re.I)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        lo, hi = (a, b) if a <= b else (b, a)
        return list(range(lo, hi + 1))
    m = re.search(r"(\d+)\s*Hours?\s*(?:\.|\)|$)", text, flags=re.I)
    if m:
        return [int(m.group(1))]
    return None

def parse_catalog_credits_for_block(blk):
    # prefer explicit hours element if present
    hours_el = blk.select_one(".courseblockhours, .hours")
    if hours_el:
        credits = parse_hours_text(hours_el.get_text(" ", strip=True))
        if credits is not None:
            return credits
    # fallback: parse ONLY from end of title (never from description)
    title_text = blk.select_one(".courseblocktitle").get_text(" ", strip=True)
    credits = parse_hours_text(title_text)
    if credits is not None:
        return credits
    return ["???"]

# ===================== CORE LOGIC PER SUBJECT =====================

def process_subject(subject_name: str, subject_code: str):
    print(f"\n===== {subject_code} — {subject_name} =====")

    output_dir = os.path.join(BASE_OUT, subject_code)
    os.makedirs(output_dir, exist_ok=True)

    offerings = defaultdict(lambda: {"fall": 0, "spring": 0})
    timings = defaultdict(list)
    all_courses = []

    # ---------- fetch API pages for both terms ----------
    for term_name, term_code in TERMS.items():
        print(f"📅 Fetching {term_name} for {subject_code}...")
        params = {
            "filter[term_cd]": term_code,
            "filter[crs_subj_desc]": subject_name,
            "page": 1,
            "limit": 100
        }
        while True:
            resp = requests.get(BASE_API, params=params)
            data = resp.json()
            results = data.get("data", [])
            if not results:
                break
            print(f"  ✅ {term_name} page {params['page']}: {len(results)}")
            params["page"] += 1
            all_courses.extend(results)

            for course in results:
                code = f"{subject_code}___{course['crs_nbr'].zfill(3)}"
                offerings[code][term_name.lower()] = 1

                crn = course.get("crn", "00000")
                meeting_days = (course.get("meeting_days") or "").strip()
                meeting_time = (course.get("meeting_time") or "").strip()
                if not meeting_time or not meeting_days:
                    continue
                try:
                    start, end = meeting_time.split("-")
                    start_min = time_to_minutes(start)
                    end_min = time_to_minutes(end)
                except:
                    continue

                days = [DAY_ABBREVS.get(d.strip()) for d in meeting_days.split(",") if d.strip() in DAY_ABBREVS]
                if not days:
                    continue
                for d in days:
                    base = DAY_OFFSETS[d] * 24 * 60
                    timings[code].append((crn, base + start_min, base + end_min))

    # ---------- write COURSE OFFERING ----------
    valid_courses = []
    with open(os.path.join(output_dir, f"courseoffering_{subject_code}.txt"), "w") as f:
        for code in sorted(offerings):
            fall = offerings[code]["fall"]
            spring = offerings[code]["spring"]
            if fall + spring == 2:
                continue  # skip if offered in both
            subj, number = code.split("___")
            norm_code = normalize_code(subj, number)
            f.write(f"{norm_code}\t{fall}\t{spring}\n")
            valid_courses.append(norm_code)

    # ---------- write COURSE TIMING ----------
    with open(os.path.join(output_dir, f"coursetiming_{subject_code}.txt"), "w") as f:
        for code, sessions in timings.items():
            subj, number = code.split("___") if "___" in code else (code[:3], code[3:])
            norm_code = normalize_code(subj, number)
            crn_dict = defaultdict(list)
            for crn, start, end in sessions:
                crn_dict[crn].append((start, end))
            num_crns = len(crn_dict)
            for crn, times in crn_dict.items():
                f.write(f"{norm_code}\t{num_crns}\t{len(times)}")
                for start, end in times:
                    f.write(f"\t{crn}\t{start}\t{end}")
                f.write("\n")

    # ---------- MASTER COURSE LIST (API ∪ Catalog) ----------
    master_file = os.path.join(output_dir, f"mastercourselist_{subject_code}.txt")

    # API credits
    api_credits = {}
    for course in all_courses:
        code = normalize_code(course["crs_subj_cd"], course["crs_nbr"].zfill(3))
        desc = (course.get("crs_desc_catalog") or "").strip()
        min_raw = course.get("crs_min_credit_hour_nbr")
        max_raw = course.get("crs_max_credit_hour_nbr")
        api_credits[code] = parse_api_credits(min_raw, max_raw, desc)

    # Catalog credits (subject-specific URL)
    catalog_url = f"https://catalog.uis.edu/coursedescriptions/{subject_code.lower()}/"
    resp = requests.get(catalog_url, timeout=30)
    soup = BeautifulSoup(resp.text, "html.parser")

    catalog_credits = {}
    for blk in soup.select("div.courseblock"):
        title_el = blk.select_one(".courseblocktitle")
        if not title_el:
            continue
        title_text = title_el.get_text(" ", strip=True)
        m = re.search(r"\b([A-Z]{3,4})\s+(\d{3})\b", title_text)
        if not m:
            continue
        subj, num = m.group(1), m.group(2)
        code = normalize_code(subj, num)
        catalog_credits[code] = parse_catalog_credits_for_block(blk)

    # Merge (prefer API unless it's ??? or 0)
    all_codes = sorted(set(api_credits.keys()) | set(catalog_credits.keys()))
    with open(master_file, "w") as f:
        for code in all_codes:
            credits = api_credits.get(code)
            if not credits or credits == ["???"] or credits == [0]:
                credits = catalog_credits.get(code, ["???"])
            credit_str = ",".join(str(c) for c in credits)
            f.write(f"{code}\t{credit_str}\n")

    print(f"  ✅ Wrote mastercourselist to {master_file}")

    # ---------- PREREQUISITES ----------
    reqs_file = os.path.join(output_dir, f"prerequisites_{subject_code}.txt")
    entries = soup.select("div.courseblock")
    with open(reqs_file, "w") as f:
        for block in entries:
            header_el = block.select_one(".courseblocktitle")
            desc_el = block.select_one(".courseblockdesc")
            if not header_el or not desc_el:
                continue
            header = header_el.get_text(" ", strip=True)
            desc = desc_el.get_text(" ", strip=True)
            m = re.search(r"([A-Z]{3,4})\s+(\d{3})", header)
            if not m:
                continue
            subj, num = m.groups()
            course_code = normalize_code(subj, num)

            if "Prerequisite" in desc:
                prereq_line = desc.split("Prerequisite", 1)[1].split(".", 1)[0]
                found = re.findall(r"([A-Z]{3,4})\s+(\d{3})", prereq_line)
                seen = set()
                for psubj, pnum in found:
                    prereq_code = normalize_code(psubj, pnum)
                    if prereq_code == course_code or (prereq_code, course_code) in seen:
                        continue
                    flag = -1 if " or " in prereq_line.lower() else 0
                    f.write(f"{prereq_code}\t{course_code}\t{flag}\n")
                    seen.add((prereq_code, course_code))
    print(f"  ✅ Wrote prerequisites to {reqs_file}")
    print(f"✅ Finished {subject_code}")

# ===================== RUN =====================

if __name__ == "__main__":
    for subj in SUBJECTS:
        process_subject(subj["name"], subj["code"])
    print("\n🎉 All subjects complete.")
