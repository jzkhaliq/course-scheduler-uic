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

    A) With term:
       code  term  num_crns  num_sessions  crn  start  end  [crn start end]...

    B) Without term:
       code  num_crns  num_sessions  crn  start  end  [crn start end]...
       -> stored under 'both' and later fanned out to offered terms.
    """
    timing_by_course = defaultdict(lambda: {"fall": [], "spring": [], "both": []})

    with open(path) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) < 4:
                continue

            code = normalize_code(parts[0])
            # robust term detection
            maybe_term = parts[1].strip().lower()
            has_term = maybe_term in {"fall", "spring"}
            idx = 2 if has_term else 1  # index for num_crns

            # Try to parse num_crns / num_sessions (for offset only)
            try:
                _num_crns = int(parts[idx]); _num_sessions = int(parts[idx + 1])
            except Exception:
                # If malformed counts, try to continue regardless
                pass

            triplet_start = idx + 2
            crn_blocks = parts[triplet_start:]

            # Parse [CRN start end] triplets
            sessions = []
            for i in range(0, len(crn_blocks), 3):
                try:
                    crn = crn_blocks[i]
                    start = int(crn_blocks[i + 1])
                    end = int(crn_blocks[i + 2])
                    sessions.append((crn, start, end))
                except (IndexError, ValueError):
                    continue

            # Group by CRN then flatten times per CRN
            crn_sessions = defaultdict(list)
            for crn, start, end in sessions:
                crn_sessions[crn].append((start, end))

            payload = []
            for crn, sess_list in crn_sessions.items():
                # flatten list of (start,end) pairs → [s1,e1,s2,e2,...]
                flat_times = [t for pair in sess_list for t in pair]
                payload.append({
                    "crn": crn,
                    "days": len(sess_list),
                    "time": flat_times,
                })

            if has_term:
                term = maybe_term  # already lower()
                timing_by_course[code][term].extend(payload)
            else:
                timing_by_course[code]["both"].extend(payload)

    return timing_by_course

# ---------- main builder ----------
def build_combined_json_uis():
    base_dir = "uis/data/subjects"  # uis/data/<SUBJECT_CODE>/
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
                # skip courses with no valid numeric credit parsed
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
                if course_data["offerings"]["fall"] and not fall_times:
                    fall_times = both_times
                if course_data["offerings"]["spring"] and not spring_times:
                    spring_times = both_times

            # If offered this term and we have any timing entries (including 0 0),
            # set timing_fall / timing_spring accordingly.
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
