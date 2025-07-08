# === main.py ===
from catalog import CourseCatalog
from planner import Planner

catalog = CourseCatalog()
catalog.load_all_data("data/prerequisites_cs.txt", "data/courseofferings_cs.txt", "data/mastercourselist_cs.txt")

planner = Planner(catalog)
print("[DEBUG] Offerings for CS___141:", catalog.courses["CS___141"].offerings)
print("[DEBUG] Offerings for CS___151:", catalog.courses["CS___151"].offerings)

plan = planner.plan(["MATH_180"])

print("\n📅 Full Semester Plan:\n")
for i, semester in enumerate(plan, 1):
    print(f"Semester {i}:")
    for code, credits in semester:
        print(f"  {code} ({credits} credits)")
    print()
