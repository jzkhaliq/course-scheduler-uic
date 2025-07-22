import os
import json
import re
from collections import defaultdict

def generate_config_for_subject(subject_dir):
    subject = os.path.basename(subject_dir)
    prefix = f"{subject}___"

    paths = {
        "credits": os.path.join(subject_dir, f"mastercourselist_{subject}.txt"),
        "offerings": os.path.join(subject_dir, f"courseoffering_{subject}.txt"),
        "prereqs": os.path.join(subject_dir, f"prerequisites_{subject}.txt"),
    }

    if not all(os.path.exists(p) for p in paths.values()):
        return None

    # 1. Load credits
    credits_map = {}
    with open(paths["credits"]) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            code, credit = parts
            try:
                credits_map[code] = float(credit)
            except:
                credits_map[code] = None  # for ???
    
    # 2. Load offerings
    offerings_map = {}
    with open(paths["offerings"]) as f:
        for line in f:
            code, fall, spring = line.strip().split("\t")
            offerings_map[code] = {
                "fall": fall == "1",
                "spring": spring == "1"
            }

    # 3. Load prerequisites
    prereq_map = defaultdict(list)
    with open(paths["prereqs"]) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 3:
                continue
            prereq, course, _ = parts
            prereq_map[course].append(prereq)

    # 4. Build course data
    course_data = {}
    required_courses = []
    electives = []
    intro_courses = []

    for course_code in sorted(credits_map.keys()):
        try:
            number = int(course_code.split("___")[1])
        except:
            continue

        # Categorize course
        if 100 <= number < 200:
            ctype = "intro"
            intro_courses.append(course_code)
        elif 200 <= number < 400:
            ctype = "required"
            required_courses.append(course_code)
        elif 400 <= number < 500:
            ctype = "elective"
            electives.append(course_code)
        else:
            ctype = "other"

        course_data[course_code] = {
            "credits": credits_map[course_code],
            "offered": offerings_map.get(course_code, {"fall": False, "spring": False}),
            "prerequisites": prereq_map.get(course_code, []),
            "type": ctype
        }

    # 5. Estimate total credits
    total_credits = sum(
        credits_map[c] for c in required_courses
        if c in credits_map and isinstance(credits_map[c], (int, float))
    )
    min_total = int(total_credits) if total_credits >= 40 else 128

    # 6. Final JSON structure
    config = {
        "subject": subject,
        "course_prefix": prefix,
        "courses": course_data,
        "elective_pool": {
            "min_required": 5,
            "courses": electives[:15]
        },
        "placeholder_courses": [f"{prefix}499", f"{prefix}XXX"],
        "min_total_credits": min_total
    }

    return config

def main():
    os.makedirs("data", exist_ok=True)

    test_subjects = ["CS", "MATH", "ECE"]  # 👈 Edit this list to test different subjects

    for subject in test_subjects:
        subject_dir = os.path.join("subjects", subject)
        if not os.path.isdir(subject_dir):
            print(f"⚠️ Skipping {subject} — folder not found")
            continue

        config = generate_config_for_subject(subject_dir)
        if config:
            output_path = f"data/major_config_{subject}.json"
            with open(output_path, "w") as f:
                json.dump(config, f, indent=2)
            print(f"✅ Generated {output_path}")
        else:
            print(f"⚠️ Skipped {subject} (missing or incomplete files)")

if __name__ == "__main__":
    main()

