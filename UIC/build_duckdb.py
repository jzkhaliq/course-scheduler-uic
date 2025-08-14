import json
import duckdb
import os

def normalize_course_code(subject, course_number):
    """Pads subject and number to form an 8-character course code (e.g., CS___141)."""
    return f"{subject}{'_' * (8 - len(subject) - len(course_number))}{course_number}"

# Load JSON
with open("UIC/data/combined.json") as f:
    data = json.load(f)

# Recreate DB
db_path = "UIC/data/combined.duckdb"
if os.path.exists(db_path):
    os.remove(db_path)
con = duckdb.connect(db_path)

# Create tables (add subjects + subject_name in courses)
con.execute("""
CREATE TABLE subjects (
  subject TEXT PRIMARY KEY,
  subject_name TEXT
)""")

con.execute("""
CREATE TABLE courses (
  subject TEXT,
  subject_name TEXT,
  course_id TEXT,
  credits FLOAT,
  offered_fall BOOLEAN,
  offered_spring BOOLEAN
)""")

con.execute("""
CREATE TABLE timings (
  subject TEXT,
  course_id TEXT,
  term TEXT,
  group_idx INT,
  start INT,
  end_time INT
)""")

con.execute("""
CREATE TABLE prerequisites (
  subject TEXT,
  course_id TEXT,
  prereq_id TEXT,
  type INT
)""")

con.execute("""
CREATE TABLE lecture_days (
  subject TEXT,
  course_id TEXT,
  term TEXT,
  group_idx INT,
  days INT
)""")

# Insert data
for subject, subject_data in data.items():
    # lowercased subject_name from JSON (fallback to subject code)
    subject_name = (subject_data.get("subject_name") or subject).lower()

    # insert into subjects table (idempotent insert per subject)
    con.execute("INSERT INTO subjects VALUES (?, ?)", (subject, subject_name))

    courses = subject_data.get("courses", [])
    for course in courses:
        raw_id = course.get("id")  # e.g., "CS___141"
        if not raw_id or len(raw_id) < 3:
            continue

        course_number = raw_id[-3:]
        course_id = normalize_course_code(subject, course_number)

        # credits
        credit_list = course.get("credits", [])
        credits = float(credit_list[0]) if credit_list else None

        # offerings
        offered = course.get("offerings", {})
        fall = offered.get("fall", True)
        spring = offered.get("spring", True)

        con.execute(
            "INSERT INTO courses VALUES (?, ?, ?, ?, ?, ?)",
            (subject, subject_name, course_id, credits, fall, spring),
        )

        # prerequisites
        for prereq in course.get("prerequisites", []):
            prereq_id = prereq.get("id") or ""
            if len(prereq_id) < 3:
                continue
            prereq_number = prereq_id[-3:]
            prereq_subj = prereq_id[: len(prereq_id) - 3].rstrip('_')  # fix: slice off last 3, not 4
            normalized_prereq = normalize_course_code(prereq_subj, prereq_number)
            try:
                ptype = int(prereq.get("type", -1))
            except Exception:
                ptype = -1
            con.execute(
                "INSERT INTO prerequisites VALUES (?, ?, ?, ?)",
                (subject, course_id, normalized_prereq, ptype),
            )

        # timings (timing_fall / timing_spring)
        for term in ("fall", "spring"):
            key = f"timing_{term}"
            timing_data = course.get(key, [])
            for group_idx, session in enumerate(timing_data):
                if not isinstance(session, dict):
                    continue
                time_blocks = session.get("time", []) or []
                if not isinstance(time_blocks, list) or len(time_blocks) == 0:
                    continue

                # lecture_days row (count pairs)
                lecture_count = len(time_blocks) // 2
                con.execute(
                    "INSERT INTO lecture_days VALUES (?, ?, ?, ?, ?)",
                    (subject, course_id, term, group_idx, lecture_count),
                )

                # timings rows
                for i in range(0, len(time_blocks), 2):
                    try:
                        start = int(time_blocks[i])
                        end = int(time_blocks[i + 1])
                    except Exception:
                        continue
                    con.execute(
                        "INSERT INTO timings VALUES (?, ?, ?, ?, ?, ?)",
                        (subject, course_id, term, group_idx, start, end),
                    )

print("✅ UIC DuckDB built with lowercased subject_name in subjects and courses")
