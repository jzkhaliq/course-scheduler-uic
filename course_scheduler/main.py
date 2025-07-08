# === main.py ===
from catalog import CourseCatalog
from planner import Planner

catalog = CourseCatalog()
catalog.load_all_data("data/prerequisites_cs.txt", "data/courseofferings_cs.txt", "data/mastercourselist_cs.txt")

planner = Planner(catalog)

# Debug: Check prerequisites for some courses after fix
test_courses = ["CS___141", "CS___211", "CS___251", "CS___294", "CS___394", "CS___491"]
print(f"Prerequisite analysis after fix:")
for course in test_courses:
    if course in catalog.prereqs:
        rule = catalog.prereqs[course]
        print(f"  {course}:")
        print(f"    Strict: {rule.strict}")
        print(f"    Concurrent: {rule.concurrent}")
        print(f"    Indegree: {catalog.indegree[course]}")
    else:
        print(f"  {course}: No prerequisites")

plan = planner.plan(["MATH_180"])

print("\n📅 Full Semester Plan:\n")
for i, semester in enumerate(plan, 1):
    print(f"Semester {i}:")
    total_credits = 0
    for code, credits in semester:
        print(f"  {code} ({credits} credits)")
        total_credits += credits
    print(f"  Total: {total_credits} credits")
    print()