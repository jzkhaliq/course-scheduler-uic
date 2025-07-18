# === main.py ===
import os
from catalog import CourseCatalog
from planner import Planner
from config import load_major_config

for MAJOR in os.listdir("majors"):
    config = load_major_config(f"data/major_config_{MAJOR.lower()}.json")
    print(f"\n=== {MAJOR} ===")
    config = load_major_config(f"data/major_config_{MAJOR}.json")


    catalog = CourseCatalog()
    catalog.load_all_data(
        config["data_paths"]["prereqs"],
        config["data_paths"]["offerings"],
        config["data_paths"]["credits"],
        config["data_paths"].get("timings")
    )
    base_path = os.path.join("majors", MAJOR)
    config["data_paths"] = {
        "credits": os.path.join(base_path, f"mastercourselist_{MAJOR}.txt"),
        "offerings": os.path.join(base_path, f"courseoffering_{MAJOR}.txt"),
        "prereqs": os.path.join(base_path, f"prerequisites_{MAJOR}.txt"),
        "timings": os.path.join(base_path, f"coursetiming_{MAJOR}.txt")
    }

    planner = Planner(catalog, config=config)
    plan = planner.plan(["MATH_180"])



    user_input = input("📘 Enter completed course codes (comma-separated, or leave blank to use defaults):\n> ")
    if user_input.strip():
        completed_courses = [code.strip().upper() for code in user_input.split(",")]
    else:
        completed_courses = config.get("starting_courses", [])

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

