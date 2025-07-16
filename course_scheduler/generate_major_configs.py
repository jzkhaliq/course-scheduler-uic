import os
import json
import re

def generate_config_for_major(major_dir):
    major = os.path.basename(major_dir)
    prefix = f"{major}___"
    courses = []

    # Load master course list
    master_path = os.path.join(major_dir, f"mastercourselist_{major}.txt")
    if not os.path.exists(master_path):
        return None

    with open(master_path) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            code, _ = parts
            courses.append(code)

    # Detect intro courses — 100-level
    intro_courses = [c for c in courses if re.match(f"{prefix}1\\d\\d", c)]

    # Required courses — 200–399 level (excluding XXX)
    required_courses = [
        c for c in courses
        if re.match(f"{prefix}[2-3]\\d\\d", c) and not c.endswith("XXX")
    ]

    # Electives — 400-level (limit to top 15)
    electives = [
        c for c in courses
        if re.match(f"{prefix}4\\d\\d", c)
    ][:15]

    config = {
        "major": major,
        "course_prefix": prefix,
        "intro_courses": intro_courses,
        "only_one_intro": True,
        "placeholder_courses": [f"{prefix}499", f"{prefix}XXX"],
        "exclude_levels": [500, 600],
        "min_total_credits": 128,
        "required_courses": required_courses + [f"{prefix}499"],
        "required_course_equivalents": {
            intro: [alt for alt in intro_courses if alt != intro] for intro in intro_courses
        },
        "elective_pool": {
            "min_required": 5,
            "courses": electives
        },
        "data_paths": {
            "credits": os.path.join(major_dir, f"mastercourselist_{major}.txt"),
            "offerings": os.path.join(major_dir, f"courseoffering_{major}.txt"),
            "prereqs": os.path.join(major_dir, f"prerequisites_{major}.txt"),
            "timings": os.path.join(major_dir, f"coursetiming_{major}.txt")
        }
    }

    return config

def main():
    os.makedirs("data", exist_ok=True)

    for major_dir in sorted(os.listdir("majors")):
        full_path = os.path.join("majors", major_dir)
        if not os.path.isdir(full_path):
            continue

        config = generate_config_for_major(full_path)
        if config:
            output_path = f"data/major_config_{major_dir}.json"
            with open(output_path, "w") as f:
                json.dump(config, f, indent=2)
            print(f"✅ Generated {output_path}")
        else:
            print(f"⚠️ Skipped {major_dir} (missing or invalid mastercourselist)")

if __name__ == "__main__":
    main()
