import os
import json
from collections import defaultdict
from generate_major_configs import major_to_subject  # or paste it directly if needed


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
    timing_by_course = defaultdict(lambda: defaultdict(list))

    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 3:
                continue

            course_code = normalize_code(parts[0])
            num_sections = int(parts[1])
            num_sessions = int(parts[2])
            crn_blocks = parts[3:]

            for i in range(0, len(crn_blocks), 3):
                try:
                    crn = crn_blocks[i]
                    start = int(crn_blocks[i + 1])
                    end = int(crn_blocks[i + 2])
                    timing_by_course[course_code][crn].append(start)
                    timing_by_course[course_code][crn].append(end)
                except (IndexError, ValueError):
                    continue

    formatted = {}
    for course_code, crn_dict in timing_by_course.items():
        formatted[course_code] = []
        for times in crn_dict.values():
            days = len(times) // 2
            formatted[course_code].append({
                "days": days,
                "time": times
            })

    return formatted


def build_combined_json():
    base_dir = "data/subjects"
    combined = {}

    # Load list of backfilled courses
    credit_cache_path = "data/credit_cache.json"
    backfilled_courses = set()

    if os.path.exists(credit_cache_path):
        with open(credit_cache_path) as f:
            credit_cache = json.load(f)
            for key in credit_cache.keys():  # key is like "CS 113"
                subject_part, number_part = key.split(" ")
                underscores = 8 - len(subject_part) - len(number_part)
                normalized = f"{subject_part}{'_' * underscores}{number_part}"
                backfilled_courses.add(normalized)



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

        credits = load_master_course_list(files["credits"])
        prereqs = load_prerequisites(files["prereqs"])
        offerings = load_course_offerings(files["offerings"])
        timings = load_course_timings(files["timings"])

        course_array = []
        for course_code in sorted(credits.keys()):
            credit_str = credits[course_code]
            credits_list = [float(c.strip()) for c in credit_str.split(',') if c.strip().replace('.', '', 1).isdigit()]

            course_data = {
                "id": course_code,
                "credits": credits_list,
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
                course_data["timing"] = timings[course_code]

            course_array.append(course_data)


        combined[subject] = {"courses": course_array}
        print(f"✅ Processed {subject} → {len(course_array)} courses")

    os.makedirs("data", exist_ok=True)
    output_path = "data/combined.json"

    with open(output_path, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\n🎉 combined.json saved with {len(combined)} subjects at {output_path}")

if __name__ == "__main__":
    build_combined_json()
