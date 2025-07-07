# Manual OR-groups for prerequisites
OR_GROUPS = [
    {"CS___107", "CS___109", "CS___111", "CS___112", "CS___113"}  # for CS___141
]
# Later on, we will not manually use OR_GROUPS
# but instead will automatically detect OR groups

DEBUG = False  # Set to False to silence debug output

def load_prerequisites(file_path):
    prereq_graph = {}
    with open(file_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 3:
                if DEBUG:
                    print(f"Skipping bad line: {line}")
                continue
            prereq, target, relation = parts
            relation = int(relation)
            if target not in prereq_graph:
                prereq_graph[target] = []
            prereq_graph[target].append((prereq, relation))
    return prereq_graph


def get_eligible_courses(prereq_graph, completed_courses):
    directly_eligible = set()

    # Step 1: courses where all -1 prereqs are satisfied (supports OR-groups)
    for course, prereqs in prereq_graph.items():
        if course in completed_courses:
            continue

        required = [p for p, rel in prereqs if rel == -1]
        concurrent = [p for p, rel in prereqs if rel == 0]

        satisfied = True
        required_set = set(required)

        # Check if any required prereqs belong to a defined OR-group
        for group in OR_GROUPS:
            if required_set & group:
                if not (set(completed_courses) & group):
                    satisfied = False
                    break
                required_set -= group

        # Check remaining required prereqs (must be completed)
        for r in required_set:
            if r not in completed_courses:
                satisfied = False
                break

        if not satisfied:
            continue

        # Step 2: filter out courses where concurrent prereqs aren’t eligible either
        for r in concurrent:
            if r not in completed_courses and r not in directly_eligible:
                satisfied = False
                break

        if satisfied:
            directly_eligible.add(course)

    return list(directly_eligible)


def load_course_offerings(file_path):
    offerings = {}
    with open(file_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 3:
                continue
            course, fall, spring = parts
            offerings[course] = {
                "fall": int(fall),
                "spring": int(spring)
            }
    return offerings


def filter_by_semester(courses, offerings, semester):
    """semester = 'fall' or 'spring'"""
    filtered = []
    for course in courses:
        if course not in offerings:
            filtered.append(course)  # not listed = assume offered every semester
        elif offerings[course].get(semester, 0):
            filtered.append(course)
    return filtered


def load_course_credits(file_path):
    credits = {}
    with open(file_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            course, credit_str = parts

            # Handle variable credit values like "1,2,3"
            if "," in credit_str:
                credit_options = [int(c) for c in credit_str.split(",")]
                credit = max(credit_options)  # use the maximum for now
            else:
                credit = int(credit_str)

            credits[course] = credit
    return credits


def plan_semester(eligible_courses, credits_map, max_credits=18):
    semester = []
    total = 0
    for course in eligible_courses:
        course_credit = credits_map.get(course, 3)  # assume 3 if missing
        if total + course_credit <= max_credits:
            semester.append((course, course_credit))
            total += course_credit
    return semester


def run_planner(completed, semester, max_credits=18):
    prereq_graph = load_prerequisites("data/prerequisites_cs.txt")
    offerings = load_course_offerings("data/courseofferings_cs.txt")
    credits = load_course_credits("data/mastercourselist_cs.txt")

    eligible = get_eligible_courses(prereq_graph, completed)
    eligible_in_semester = filter_by_semester(eligible, offerings, semester)
    semester_plan = plan_semester(eligible_in_semester, credits, max_credits)

    print(f"\nPlanned {semester.capitalize()} Semester:")
    for course, credit in semester_plan:
        print(f"{course} ({credit} credits)")

    if DEBUG:
        print(f"\nCS___141 prereqs: {prereq_graph.get('CS___141')}")
        print("Eligible:", eligible)
        print(f"Eligible in {semester.capitalize()}:", eligible_in_semester)
        print("Credits map:", {c: credits.get(c) for c in eligible_in_semester})


if __name__ == "__main__":
    completed_courses = ["MATH_180", "CS___111", "CS___107", "CS___109"]
    run_planner(completed_courses, semester="fall")
