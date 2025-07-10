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