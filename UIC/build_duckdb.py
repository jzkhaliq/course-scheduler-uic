import json
import duckdb
import os

def normalize_course_code(subject, course_number):
    """Pads subject and number to form an 8-character course code (e.g., CS___141)."""
    return f"{subject}{'_' * (8 - len(subject) - len(course_number))}{course_number}"

with open("UIC/data/combined.json") as f:
    data = json.load(f)

if os.path.exists("UIC/data/combined.duckdb"):
    os.remove("UIC/data/combined.duckdb")

con = duckdb.connect("UIC/data/combined.duckdb")

# Create tables
con.execute("CREATE TABLE courses (subject TEXT, course_id TEXT, credits FLOAT, offered_fall BOOLEAN, offered_spring BOOLEAN)")
con.execute("CREATE TABLE timings (subject TEXT, course_id TEXT, term TEXT, group_idx INT, start INT, end_time INT)")
con.execute("CREATE TABLE prerequisites (subject TEXT, course_id TEXT, prereq_id TEXT, type INT)")
con.execute("CREATE TABLE lecture_days (subject TEXT, course_id TEXT, term TEXT, group_idx INT, days INT)")

for subject, subject_data in data.items():
    courses = subject_data.get("courses", [])
    for course in courses:
        raw_id = course.get("id")  # e.g., "CS___141"
        course_number = raw_id[-3:]
        course_id = normalize_course_code(subject, course_number)

        credit_list = course.get("credits", [])
        credits = float(credit_list[0]) if credit_list else None

        offered = course.get("offerings", {})
        fall = offered.get("fall", True)
        spring = offered.get("spring", True)

        con.execute("INSERT INTO courses VALUES (?, ?, ?, ?, ?)", (subject, course_id, credits, fall, spring))

        for prereq in course.get("prerequisites", []):
            prereq_id = prereq.get("id")
            prereq_number = prereq_id[-3:]
            normalized_prereq = normalize_course_code(prereq_id[:len(prereq_id) - 4].rstrip('_'), prereq_number)
            con.execute("INSERT INTO prerequisites VALUES (?, ?, ?, ?)", (
                subject,
                course_id,
                normalized_prereq,
                int(prereq.get("type", -1))
            ))

        # ✅ Handle timing_fall and timing_spring
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
                con.execute("INSERT INTO lecture_days VALUES (?, ?, ?, ?, ?)",
                            (subject, course_id, term, group_idx, lecture_count))

                for i in range(0, len(time_blocks), 2):
                    try:
                        start = time_blocks[i]
                        end = time_blocks[i + 1]
                        con.execute("INSERT INTO timings VALUES (?, ?, ?, ?, ?, ?)",
                                    (subject, course_id, term, group_idx, start, end))
                    except IndexError:
                        continue

print("✅ DuckDB fully built from combined.json")
