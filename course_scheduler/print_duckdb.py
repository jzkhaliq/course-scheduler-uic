import duckdb

con = duckdb.connect("data/combined.duckdb")

tables = ["courses", "timings", "prerequisites", "lecture_days"]

for table in tables:
    print(f"\n=== {table.upper()} ===")
    try:
        results = con.execute(f"SELECT * FROM {table} LIMIT 1000").fetchall()
        for row in results:
            print(row)
    except Exception as e:
        print(f"Error querying {table}: {e}")
