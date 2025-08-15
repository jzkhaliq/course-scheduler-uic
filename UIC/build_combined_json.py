import os
import re
import json
import requests
from bs4 import BeautifulSoup
from collections import defaultdict

# ===================== Subject-name helper (UIC) =====================

BASE_UIC_SCHEDULE = "https://webcs7.osss.uic.edu/schedule-of-classes/static/schedules"

def _extract_subject_name_from_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    # Gather all visible text chunks
    texts = []
    for el in soup.find_all(text=True):
        txt = el.strip()
        if txt and len(txt) < 120:  # ignore long paragraphs
            texts.append(txt)

    for txt in texts:
        m = re.search(r"(Fall|Spring)\s+\d{4}\s+([A-Za-z0-9&/\-.,\s]+)", txt, flags=re.I)
        if m:
            name = m.group(2).strip()
            # Remove trailing stuff after "Location:" or "Phone:"
            name = re.split(r"\bLocation\b|\bPhone\b|Last generated:", name, maxsplit=1)[0].strip(" -:.,")
            if len(name) > 3 and name.lower() != "semester":
                return name.lower()
    return None


def get_uic_subject_name(subject_code: str, fallback_years=(2025, 2024)) -> str:
    """
    Fetch one or more subject pages until we can extract a readable subject name.
    Tries Fall then Spring for each year in fallback_years.
    Falls back to the subject_code if nothing is found.
    """
    for year in fallback_years:
        for term in ("fall", "spring"):
            url = f"{BASE_UIC_SCHEDULE}/{term}-{year}/{subject_code}.html"
            try:
                resp = requests.get(url, timeout=20)
                if resp.status_code != 200:
                    continue
                name = _extract_subject_name_from_html(resp.text)
                if name:
                    return name.lower()
            except Exception:
                continue
    return subject_code.lower()  # safe fallback

# ===================== Your existing helpers =====================

def normalize_code(code):
    return code.strip().ljust(8, '_')

def load_master_course_list(path):
    credits = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 2:
                code, credit = parts
                credits[normalize_code(code)] = credit
    return credits

def load_prerequisites(path):
    prereqs = defaultdict(list)
    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 3:
                prereq, course, flag = parts
                prereq = normalize_code(prereq)
                course = normalize_code(course)
                prereqs[course].append({
                    "id": prereq,
                    "type": flag
                })
    return prereqs

def load_course_offerings(path):
    offerings = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 3:
                code, fall, spring = parts
                offerings[normalize_code(code)] = {
                    "fall": fall == "1",
                    "spring": spring == "1"
                }
    return offerings

def load_course_timings(path):
    # course_code → { "fall": [...], "spring": [...] }
    timing_by_course = defaultdict(lambda: {"fall": [], "spring": []})

    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 5:
                continue

            course_code = normalize_code(parts[0])
            term = parts[1].strip().lower()  # "fall" or "spring"
            try:
                # we don't need these, but parsing advances the offset
                _num_sections = int(parts[2])
                _num_sessions = int(parts[3])
            except ValueError:
                continue

            crn_blocks = parts[4:]
            times = []

            for i in range(0, len(crn_blocks), 3):
                try:
                    crn = crn_blocks[i]
                    start = int(crn_blocks[i + 1])
                    end = int(crn_blocks[i + 2])
                    times.append((crn, start, end))
                except (IndexError, ValueError):
                    continue

            crn_sessions = defaultdict(list)
            for crn, start, end in times:
                crn_sessions[crn].append((start, end))

            for crn, session_list in crn_sessions.items():
                time_flat = [t for pair in session_list for t in pair]
                timing_by_course[course_code][term].append({
                    "crn": crn,
                    "days": len(session_list),
                    "time": time_flat
                })

    return timing_by_course

# ===================== Builder =====================

def build_combined_json():
    base_dir = "UIC/data/subjects"
    combined = {}

    # Load list of backfilled courses
    credit_cache_path = "UIC/data/data_archive/credit_cache.json"
    backfilled_courses = set()

    if os.path.exists(credit_cache_path):
        try:
            with open(credit_cache_path) as f:
                credit_cache = json.load(f)
                for key in credit_cache.keys():  # key is like "CS 113"
                    subject_part, number_part = key.split(" ")
                    underscores = 8 - len(subject_part) - len(number_part)
                    normalized = f"{subject_part}{'_' * underscores}{number_part}"
                    backfilled_courses.add(normalized)
        except Exception:
            pass

    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Base directory not found: {base_dir}")

    for subject in sorted(os.listdir(base_dir)):
        subject_path = os.path.join(base_dir, subject)
        if not os.path.isdir(subject_path):
            continue

        files = {
            "credits": os.path.join(subject_path, f"mastercourselist_{subject}.txt"),
            "prereqs": os.path.join(subject_path, f"prerequisites_{subject}.txt"),
            "offerings": os.path.join(subject_path, f"courseoffering_{subject}.txt"),
            "timings": os.path.join(subject_path, f"coursetiming_{subject}.txt"),
        }

        if not all(os.path.exists(p) for p in files.values()):
            print(f"⚠️ Skipping {subject}: missing one or more files")
            continue

        # NEW: pull human-readable subject name
        subject_name = get_uic_subject_name(subject)

        credits = load_master_course_list(files["credits"])
        prereqs = load_prerequisites(files["prereqs"])
        offerings = load_course_offerings(files["offerings"])
        timings = load_course_timings(files["timings"])

        course_array = []
        for course_code in sorted(credits.keys()):
            credit_str = credits[course_code]
            credits_list = [
                float(c.strip())
                for c in credit_str.split(',')
                if c.strip().replace('.', '', 1).isdigit()
            ]

            # keep courses even if credits couldn't parse? (your original kept all)
            # if you want to skip non-numeric credits, uncomment:
            # if not credits_list:
            #     continue

            course_data = {
                "id": course_code,
                "credits": credits_list if credits_list else [],  # [] when "???"
                "prerequisites": prereqs.get(course_code, [])
            }

            # Offerings logic
            if course_code in offerings:
                course_data["offerings"] = offerings[course_code]
            elif course_code in backfilled_courses:
                course_data["offerings"] = {"fall": False, "spring": False}
            else:
                course_data["offerings"] = {"fall": True, "spring": True}

            # Timing
            if course_code in timings:
                timing_info = timings[course_code]
                if timing_info.get("fall"):
                    course_data["timing_fall"] = timing_info["fall"]
                if timing_info.get("spring"):
                    course_data["timing_spring"] = timing_info["spring"]

            course_array.append(course_data)

        # ⬅️ NEW: store subject_name at the subject header level
        combined[subject] = {
            "subject": subject_name,
            "courses": course_array
        }
        print(f"✅ Processed {subject} ({subject_name}) → {len(course_array)} courses")

    os.makedirs("UIC/data", exist_ok=True)
    output_path = "UIC/data/combined.json"

    with open(output_path, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\n🎉 combined.json saved with {len(combined)} subjects at {output_path}")

if __name__ == "__main__":
    build_combined_json()
