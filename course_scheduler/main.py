# === main.py ===
from catalog import CourseCatalog
from planner import Planner
from config import load_major_config

config = load_major_config("data/major_config_cs.json")

catalog = CourseCatalog()
catalog.load_all_data(
    config["data_paths"]["prereqs"],
    config["data_paths"]["offerings"],
    config["data_paths"]["credits"]
)

planner = Planner(catalog, config=config)
plan = planner.plan(["MATH_180"])

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

user_input = input("📘 Enter completed course codes (comma-separated, e.g. CS___141,MATH_180):\n> ")
completed_courses = [code.strip().upper() for code in user_input.split(",") if code.strip()]

plan = planner.plan(completed_courses)


print("\n📅 Full Semester Plan:\n")
for i, semester in enumerate(plan, 1):
    print(f"Semester {i}:")
    total_credits = 0
    for code, credits in semester:
        print(f"  {code} ({credits} credits)")
        total_credits += credits
    print(f"  Total: {total_credits} credits")
    print()