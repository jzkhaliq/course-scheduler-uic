import requests
import os

term_code = "420248"  # Fall 2024
subject = "Computer Science"
subject_code = "CSC"  # ✅ UIS-style subject code

base_url = "https://apps.uis.edu/dynamic-course-schedule/api/course"
params = {
    "filter[term_cd]": term_code,
    "filter[crs_subj_desc]": subject,
    "page": 1,
    "limit": 100
}

all_courses = []

# Fetch paginated results
while True:
    response = requests.get(base_url, params=params)
    data = response.json()
    results = data.get("data", [])
    if not results:
        break
    all_courses.extend(results)
    print(f"✅ Page {params['page']}: {len(results)} courses")
    params["page"] += 1

print(f"🎓 Total courses fetched: {len(all_courses)}")

# ✅ Ensure output folder exists
output_dir = "uis/data"
os.makedirs(output_dir, exist_ok=True)

# Write to courseoffering_CSC.txt
with open(f"{output_dir}/courseoffering_{subject_code}.txt", "w") as f:
    for course in all_courses:
        code = f"{subject_code}___{course['crs_nbr'].zfill(3)}"
        f.write(f"{code}\t1\t0\n")  # offered in Fall only

# Write to coursetiming_CSC.txt
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

with open(f"{output_dir}/coursetiming_{subject_code}.txt", "w") as f:
    for course in all_courses:
        code = f"{subject_code}___{course['crs_nbr'].zfill(3)}"
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

        line = f"{code}\t{len(days)}"
        for d in days:
            offset = {"M": 0, "T": 1, "W": 2, "R": 3, "F": 4, "S": 5, "U": 6}[d]
            base = offset * 24 * 60
            line += f"\t{crn}\t{base + start_min}\t{base + end_min}"
        f.write(line + "\n")

print("✅ Files written to uis/data/ as courseoffering_CSC.txt and coursetiming_CSC.txt")
