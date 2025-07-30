import json
import duckdb
import os

with open("data/combined.json") as f:
    data = json.load(f)

if os.path.exists("data/combined.duckdb"):
    os.remove("data/combined.duckdb")

con = duckdb.connect("data/combined.duckdb")

# Create tables
con.execute("CREATE TABLE courses (subject TEXT, course_id TEXT, credits FLOAT, offered_fall BOOLEAN, offered_spring BOOLEAN)")
con.execute("CREATE TABLE timings (subject TEXT, course_id TEXT, group_idx INT, start INT, end_time INT)")
con.execute("CREATE TABLE prerequisites (subject TEXT, course_id TEXT, prereq_id TEXT, type INT)")
con.execute("CREATE TABLE lecture_counts (subject TEXT, course_id TEXT, group_idx INT, count INT)")

for subject, subject_data in data.items():
    courses = subject_data.get("courses", [])
    for course in courses:
        course_id = course.get("id")
        credit_list = course.get("credits", [])
        credits = float(credit_list[0]) if credit_list else None
        offered = course.get("offerings", {})
        fall = offered.get("fall", True)
        spring = offered.get("spring", True)

        con.execute("INSERT INTO courses VALUES (?, ?, ?, ?, ?)", (subject, course_id, credits, fall, spring))

        for prereq in course.get("prerequisites", []):
            con.execute("INSERT INTO prerequisites VALUES (?, ?, ?, ?)", (
                subject,
                course_id,
                prereq.get("id"),
                int(prereq.get("type", -1))
            ))

        timing_data = course.get("timing", [])
        for group_idx, session in enumerate(timing_data):
            if not isinstance(session, dict):
                continue

            time_blocks = session.get("time", [])
            if not time_blocks:
                continue

            lecture_count = len(time_blocks) // 2
            con.execute("INSERT INTO lecture_counts VALUES (?, ?, ?, ?)", (subject, course_id, group_idx, lecture_count))

            for i in range(0, len(time_blocks), 2):
                try:
                    start = time_blocks[i]
                    end = time_blocks[i + 1]
                    con.execute("INSERT INTO timings VALUES (?, ?, ?, ?, ?)", (subject, course_id, group_idx, start, end))
                except IndexError:
                    continue



print("✅ DuckDB fully built from combined.json")
