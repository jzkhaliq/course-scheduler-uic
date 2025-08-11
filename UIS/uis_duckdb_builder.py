import json
import duckdb
import os

def normalize_course_code(subject, course_number):
    """Pads subject and number to form an 8-character course code (e.g., CSC__225 or CS___141)."""
    return f"{subject}{'_' * (8 - len(subject) - len(course_number))}{course_number}"

# Paths for UIS
json_path = "uis/data/uis.json"
db_path = "uis/data/uis.duckdb"

with open(json_path) as f:
    data = json.load(f)

# Recreate DB
if os.path.exists(db_path):
    os.remove(db_path)
con = duckdb.connect(db_path)

# Create tables
con.execute("CREATE TABLE courses (subject TEXT, course_id TEXT, credits FLOAT, offered_fall BOOLEAN, offered_spring BOOLEAN)")
con.execute("CREATE TABLE timings (subject TEXT, course_id TEXT, term TEXT, group_idx INT, start INT, end_time INT)")
con.execute("CREATE TABLE prerequisites (subject TEXT, course_id TEXT, prereq_id TEXT, type INT)")
con.execute("CREATE TABLE lecture_days (subject TEXT, course_id TEXT, term TEXT, group_idx INT, days INT)")

for subject, subject_data in data.items():
    courses = subject_data.get("courses", [])
    for course in courses:
        raw_id = course.get("id")  # e.g., "CSC__225"
        if not raw_id or len(raw_id) < 3:
            continue

        # Rebuild normalized id from JSON subject key + last 3 digits
        course_number = raw_id[-3:]
        course_id = normalize_course_code(subject, course_number)

        # Credits
        credit_list = course.get("credits", [])
        credits = float(credit_list[0]) if credit_list else None

        # Offerings
        offered = course.get("offerings", {})
        fall = offered.get("fall", True)
        spring = offered.get("spring", True)

        con.execute(
            "INSERT INTO courses VALUES (?, ?, ?, ?, ?)",
            (subject, course_id, credits, fall, spring),
        )

        # Prereqs
        for prereq in course.get("prerequisites", []):
            prereq_id = prereq.get("id", "")
            if len(prereq_id) < 3:
                continue
            prereq_number = prereq_id[-3:]
            prereq_subj = prereq_id[: len(prereq_id) - 3].rstrip("_")
            normalized_prereq = normalize_course_code(prereq_subj, prereq_number)
            con.execute(
                "INSERT INTO prerequisites VALUES (?, ?, ?, ?)",
                (subject, course_id, normalized_prereq, int(prereq.get("type", -1))),
            )

        # Timings (timing_fall / timing_spring)
        for term in ["fall", "spring"]:
            key = f"timing_{term}"
            timing_data = course.get(key, [])
            for group_idx, session in enumerate(timing_data):
                if not isinstance(session, dict):
                    continue
                time_blocks = session.get("time", [])
                if not time_blocks:
                    continue

                lecture_count = len(time_blocks) // 2
                con.execute(
                    "INSERT INTO lecture_days VALUES (?, ?, ?, ?, ?)",
                    (subject, course_id, term, group_idx, lecture_count),
                )

                for i in range(0, len(time_blocks), 2):
                    try:
                        start = int(time_blocks[i])
                        end = int(time_blocks[i + 1])
                        con.execute(
                            "INSERT INTO timings VALUES (?, ?, ?, ?, ?, ?)",
                            (subject, course_id, term, group_idx, start, end),
                        )
                    except (IndexError, ValueError):
                        continue

print("✅ UIS DuckDB fully built from uis/data/uis.json")
