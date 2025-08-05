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
output_dir = "uis/data"
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

# Write courseoffering_CSC.txt (exclude both-term courses)
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



# Write coursetiming_CSC.txt
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
written = set()

with open(master_file, "w") as f:
    for course in all_courses:
        code = normalize_code(course["crs_subj_cd"], course["crs_nbr"].zfill(3))
        if code in written:
            continue

        desc = course.get("crs_desc_catalog", "")
        min_raw = course.get("crs_min_credit_hour_nbr")
        max_raw = course.get("crs_max_credit_hour_nbr")

        try:
            min_credit = int(float(min_raw)) if min_raw else 0

            if max_raw:
                max_credit = int(float(max_raw))
            elif re.search(r"(\d+)\s*-\s*(\d+)\s*Hours", desc):
                max_credit = int(re.search(r"(\d+)\s*-\s*(\d+)\s*Hours", desc).group(2))
            elif re.search(r"maximum of (\d+) hours", desc.lower()):
                max_credit = int(re.search(r"maximum of (\d+) hours", desc.lower()).group(1))
            else:
                max_credit = min_credit

            if max_credit > min_credit:
                credits = list(range(min_credit, max_credit + 1))
            else:
                credits = [min_credit]

        except:
            credits = ["???"]

        credit_str = ",".join(str(c) for c in credits)
        f.write(f"{code}\t{credit_str}\n")
        written.add(code)

print(f"✅ Wrote mastercourselist to {master_file}")




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


