import os
import duckdb

db_path = "uis/data/uis.duckdb"  # <-- UIS path

if not os.path.exists(db_path):
    raise FileNotFoundError("UIS DB not found. Run your UIS DuckDB builder script first to create it.")

con = duckdb.connect(db_path)

tables = ["courses", "timings", "prerequisites", "lecture_days"]
for table in tables:
    print(f"\n=== {table.upper()} ===")
    try:
        results = con.execute(f"SELECT * FROM {table} LIMIT 150").fetchall()
        for row in results:
            print(row)
    except Exception as e:
        print(f"Error querying {table}: {e}")
