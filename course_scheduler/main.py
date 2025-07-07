def load_prerequisites(file_path):
    prereq_graph = {}

    with open(file_path, "r") as f:
        for line in f:
            parts = line.strip().split("\t")
            # print(parts)  # debug
            if len(parts) != 3:
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

    # Step 1: courses where all -1 prereqs are satisfied
    for course, prereqs in prereq_graph.items():
        if course in completed_courses:
            continue

        all_strict_met = True
        for prereq, relation in prereqs:
            if relation == -1 and prereq not in completed_courses:
                all_strict_met = False
                break

        if all_strict_met:
            directly_eligible.add(course)

    # Step 2: filter out courses where concurrent prereqs aren’t eligible either
    truly_eligible = []

    for course in directly_eligible:
        prereqs = prereq_graph.get(course, [])
        valid = True
        for prereq, relation in prereqs:
            if relation == 0:  # concurrent
                if prereq not in completed_courses and prereq not in directly_eligible:
                    valid = False
                    break
        if valid:
            truly_eligible.append(course)

    return truly_eligible


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
            # not listed = assume it's offered every semester
            filtered.append(course)
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


def plan_semester(eligible_courses, credits_map, max_credits=15):
    semester = []
    total = 0

    for course in eligible_courses:
        course_credit = credits_map.get(course, 3)  # assume 3 if missing
        if total + course_credit <= max_credits:
            semester.append((course, course_credit))
            total += course_credit

    return semester









if __name__ == "__main__":
    prereq_graph = load_prerequisites("data/prerequisites_cs.txt")

    # Print first 5 entries
    #for course, prereqs in list(prereq_graph.items())[:5]:
    #    print(f"{course} ← {prereqs}")
    
    completed = ["MATH_180", "CS___111"]
    offerings = load_course_offerings("data/courseofferings_cs.txt")

    eligible = get_eligible_courses(prereq_graph, completed)
    eligible_in_fall = filter_by_semester(eligible, offerings, "fall")

    #print("\nEligible Fall courses:")
    #for course in eligible_in_fall:
    #    print(course)

    credits = load_course_credits("data/mastercourselist_cs.txt")
    semester_plan = plan_semester(eligible_in_fall, credits)

    print("\nPlanned Fall Semester:")
    for course, credit in semester_plan:
        print(f"{course} ({credit} credits)")



