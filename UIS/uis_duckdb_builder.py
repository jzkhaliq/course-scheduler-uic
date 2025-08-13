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
con.execute("""
CREATE TABLE courses (
  subject TEXT,
  course_id TEXT,
  credits FLOAT,
  offered_fall BOOLEAN,
  offered_spring BOOLEAN
)""")

# Note: include CRN + term + group_idx; one row per contiguous [start,end] block
con.execute("""
CREATE TABLE timings (
  subject TEXT,
  course_id TEXT,
  term TEXT,        -- 'fall' | 'spring'
  group_idx INT,    -- index of the CRN-group within timing_(term)
  crn TEXT,
  start INT,
  end_time INT
)""")

# Also store per-CRN "days" (number of sessions) for quick queries
con.execute("""
CREATE TABLE lecture_days (
  subject TEXT,
  course_id TEXT,
  term TEXT,
  group_idx INT,
  crn TEXT,
  days INT
)""")

con.execute("""
CREATE TABLE prerequisites (
  subject TEXT,
  course_id TEXT,
  prereq_id TEXT,
  type INT
)""")

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
            prereq_id = (prereq.get("id") or "").strip()
            if len(prereq_id) < 3:
                continue
            prereq_number = prereq_id[-3:]
            prereq_subj = prereq_id[: len(prereq_id) - 3].rstrip("_")
            normalized_prereq = normalize_course_code(prereq_subj, prereq_number)
            # default to -1 when missing/invalid
            try:
                ptype = int(prereq.get("type", -1))
            except Exception:
                ptype = -1
            con.execute(
                "INSERT INTO prerequisites VALUES (?, ?, ?, ?)",
                (subject, course_id, normalized_prereq, ptype),
            )

        # Timings (timing_fall / timing_spring), keep CRN + 0/0 placeholders
        for term in ("fall", "spring"):
            key = f"timing_{term}"
            timing_data = course.get(key, [])
            for group_idx, session in enumerate(timing_data):
                if not isinstance(session, dict):
                    continue
                crn = str(session.get("crn", "")).strip()

                # Prefer explicit 'days' if present; otherwise compute from time blocks
                time_blocks = session.get("time", []) or []
                if isinstance(time_blocks, list):
                    # must be even-length: [s1,e1,s2,e2,...]
                    blocks_len = max(0, len(time_blocks) // 2)
                else:
                    blocks_len = 0
                    time_blocks = []

                days_val = session.get("days")
                try:
                    days = int(days_val) if days_val is not None else blocks_len
                except Exception:
                    days = blocks_len

                # Store lecture_days row (even if 0/0 only)
                con.execute(
                    "INSERT INTO lecture_days VALUES (?, ?, ?, ?, ?, ?)",
                    (subject, course_id, term, group_idx, crn, days),
                )

                # Insert each [start,end] pair as a row in timings
                # Includes 0/0 pairs (flexible/TBA) so downstream can detect them
                for i in range(0, len(time_blocks), 2):
                    try:
                        start = int(time_blocks[i])
                        end = int(time_blocks[i + 1])
                    except Exception:
                        continue
                    con.execute(
                        "INSERT INTO timings VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (subject, course_id, term, group_idx, crn, start, end),
                    )

print("✅ UIS DuckDB fully built from uis/data/uis.json")
