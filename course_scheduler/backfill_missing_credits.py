import json
import time
from credit_lookup import get_credit_from_uic_catalog

# Load the credit cache
with open("data/credit_cache.json", "r") as f:
    cache = json.load(f)

missing = [key for key, val in cache.items() if val == "???"]

print(f"🔍 Found {len(missing)} courses with missing credit hours...\n")

for i, course in enumerate(missing, 1):
    try:
        subject, number = course.split()
        credit = get_credit_from_uic_catalog(subject, number)
        print(f"[{i}/{len(missing)}] {course}: {credit}")
        
    except Exception as e:
        print(f"[ERROR] Failed to update {course}: {e}")

print("\n✅ Backfill complete. All updates saved to data/credit_cache.json")
