import os
import json
from collections import defaultdict
from generate_major_configs import major_to_subject  # or paste it directly if needed

with open("data/all_uic_degrees.json") as f:
    major_credit_requirements = json.load(f)


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
    prereqs = defaultdict(lambda: {"strict": [], "concurrent": []})
    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) == 3:
                prereq, course, flag = parts
                prereq = normalize_code(prereq)
                course = normalize_code(course)
                group = "strict" if flag == "0" else "concurrent"
                prereqs[course][group].append([prereq])
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
                    timing_by_course[course_code][crn].append({
                        "start": start,
                        "end": end
                    })
                except (IndexError, ValueError):
                    continue

    # flatten structure to match final format
    formatted = {}
    for course_code, crn_dict in timing_by_course.items():
        formatted[course_code] = [
            { "crn": crn, "times": times }
            for crn, times in crn_dict.items()
        ]

    return formatted


def build_combined_json():
    base_dir = "data/subjects"
    combined = {}
    official_subjects = set(major_to_subject.values())
    reverse_lookup = defaultdict(list)
    for major, subject in major_to_subject.items():
        reverse_lookup[subject].append(major)

    for subject in sorted(os.listdir(base_dir)):
        subject_path = os.path.join(base_dir, subject)
        if not os.path.isdir(subject_path):
            continue

        prefix = f"{subject}___"
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

        major_courses = {}

        for course_code in sorted(credits.keys()):
            major_courses[course_code] = {
                "credits": credits[course_code],
                "prerequisites": prereqs.get(course_code, {"strict": [], "concurrent": []}),
                "offered": offerings.get(course_code, {"fall": True, "spring": True}),
                "timing": timings.get(course_code, [])

            }

        if subject in official_subjects:
            for major_name in reverse_lookup[subject]:
                safe_key = major_name.strip().lower().replace(" ", "_").replace("-", "_")
                combined[safe_key] = {
                    "subject_code": subject,
                    "min_total_credits": major_credit_requirements.get(major_name, 120),
                    "courses": major_courses
                }

        else:
            if "unmapped_subjects" not in combined:
                combined["unmapped_subjects"] = {}
            combined["unmapped_subjects"][subject] = {
                "courses": major_courses
            }

        print(f"✅ Processed {subject} → {len(major_courses)} courses")

    # Move "unmapped_subjects" to the bottom
    if "unmapped_subjects" in combined:
        unmapped = combined.pop("unmapped_subjects")
        combined["unmapped_subjects"] = unmapped

    # Save final output
    os.makedirs("data", exist_ok=True)
    output_path = "data/combined.json"
    
    with open(output_path, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\n🎉 combined.json saved with {len(combined)} top-level entries at {output_path}")

if __name__ == "__main__":
    build_combined_json()
