import os
import json
from collections import defaultdict

# ---------- helpers ----------
def normalize_code(code: str) -> str:
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
                prereqs[course].append({"id": prereq, "type": flag})
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
                    "spring": spring == "1",
                }
    return offerings

def load_course_timings(path):
    """
    Supports BOTH formats:

    A) With term (UIC-style):
       code  term  num_sections  num_sessions  crn  start  end  [crn start end]...

    B) Without term (some UIS writers):
       code  num_sections  num_sessions  crn  start  end  [crn start end]...
       -> stored as 'both' and later fanned out to offered terms.
    """
    timing_by_course = defaultdict(lambda: {"fall": [], "spring": [], "both": []})

    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 4:
                continue

            code = normalize_code(parts[0])

            # Detect format
            has_term = parts[1].lower() in {"fall", "spring"}
            idx = 2 if has_term else 1  # index where num_sections should be

            try:
                # num_sections, num_sessions (not used directly, but parsed for offset)
                _num_sections = int(parts[idx]); _num_sessions = int(parts[idx + 1])
            except ValueError:
                # If can't parse counts, try to continue anyway
                pass
            except IndexError:
                continue

            # Triplets start after counts
            triplet_start = idx + 2
            crn_blocks = parts[triplet_start:]
            times = []
            for i in range(0, len(crn_blocks), 3):
                try:
                    crn = crn_blocks[i]
                    start = int(crn_blocks[i + 1])
                    end = int(crn_blocks[i + 2])
                    times.append((crn, start, end))
                except (IndexError, ValueError):
                    continue

            # Group sessions by CRN then flatten as required
            crn_sessions = defaultdict(list)
            for crn, start, end in times:
                crn_sessions[crn].append((start, end))

            payload = []
            for crn, session_list in crn_sessions.items():
                time_flat = [t for pair in session_list for t in pair]
                payload.append({
                    "crn": crn,
                    "days": len(session_list),
                    "time": time_flat,
                })

            if has_term:
                term = parts[1].lower()
                if term in ("fall", "spring"):
                    timing_by_course[code][term].extend(payload)
            else:
                timing_by_course[code]["both"].extend(payload)

    return timing_by_course

# ---------- main builder ----------
def build_combined_json_uis():
    base_dir = "uis/data/subjects"  # <--- UIS outputs live here: uis/data/<SUBJECT_CODE>/
    combined = {}

    # Optional: mark backfilled courses as having no offerings by default (if present)
    credit_cache_path = "UIC/data/data_archive/credit_cache.json"
    backfilled_courses = set()
    if os.path.exists(credit_cache_path):
        try:
            with open(credit_cache_path) as f:
                credit_cache = json.load(f)
            for key in credit_cache.keys():  # e.g., "CS 113"
                subj, num = key.split(" ")
                underscores = 8 - len(subj) - len(num)
                normalized = f"{subj}{'_' * underscores}{num}"
                backfilled_courses.add(normalized)
        except Exception:
            pass

    if not os.path.isdir(base_dir):
        raise FileNotFoundError(f"Base directory not found: {base_dir}")

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
            # Parse credits to floats (skip non-numeric like "???")
            credits_list = [
                float(c.strip())
                for c in credit_str.split(',')
                if c.strip().replace('.', '', 1).isdigit()
            ]
            if not credits_list:
                # skip courses with no valid credit parsed
                continue

            course_data = {
                "id": course_code,
                "credits": credits_list,
                "prerequisites": prereqs.get(course_code, []),
            }

            # Offerings logic (same as your UIC builder)
            if course_code in offerings:
                course_data["offerings"] = offerings[course_code]
            elif course_code in backfilled_courses:
                course_data["offerings"] = {"fall": False, "spring": False}
            else:
                course_data["offerings"] = {"fall": True, "spring": True}

            # Timing logic:
            # - If file had explicit term timings, keep them.
            # - If file had no term (stored under "both"), fan out to offered terms only.
            tinfo = timings.get(course_code, {})
            fall_times = list(tinfo.get("fall", []))
            spring_times = list(tinfo.get("spring", []))
            both_times = list(tinfo.get("both", []))

            if both_times:
                if course_data["offerings"]["fall"]:
                    fall_times = fall_times or both_times
                if course_data["offerings"]["spring"]:
                    spring_times = spring_times or both_times

            if course_data["offerings"]["fall"] and fall_times:
                course_data["timing_fall"] = fall_times
            if course_data["offerings"]["spring"] and spring_times:
                course_data["timing_spring"] = spring_times

            course_array.append(course_data)

        combined[subject] = {"courses": course_array}
        print(f"✅ Processed {subject} → {len(course_array)} courses")

    os.makedirs("uis/data", exist_ok=True)
    output_path = "uis/data/uis.json"
    with open(output_path, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\n🎉 uis.json saved with {len(combined)} subjects at {output_path}")

if __name__ == "__main__":
    build_combined_json_uis()
