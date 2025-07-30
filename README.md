# UIC Smart Course Scheduler (GPIP Project)

This project scrapes and models course data from the University of Illinois Chicago (UIC) to support automated semester planning and curriculum mapping for undergraduate majors.

## 🔍 What It Does

- Scrapes the official UIC Schedule of Classes website for:
  - Course offerings (Fall/Spring)
  - Course prerequisites
  - Course lecture timings (in minutes from Monday midnight)
  - Course credit hours
- Processes data for all 190+ subjects and maps it to 94 official undergraduate majors
- Builds a unified `combined.json` file containing:
  - All subject-specific course data with metadata
  - Clean lecture-only timing data (excludes labs/discussions and duplicate time slots)

## 🗂 Output Structure

- `data/combined.json`  
  Subject-based structure:
  ```json
  {
    "CS": {
      "courses": [
        {
          "id": "CS___141",
          "credits": [4],
          "offerings": { "fall": true, "spring": true },
          "prerequisites": [
            { "id": "CS___107", "type": "0" }
          ],
          "timing": [
            {
              "days": 2,
              "time": [840, 930, 960, 1050]
            },
            {
              "days": 1,
              "time": [660, 750]
            }
          ]
        }
      ]
    }
  }


## 🗃️ DuckDB: `data/combined.duckdb`

A compact SQL database is generated from `combined.json` using DuckDB with the following tables:

### `courses`

| Column         | Type     | Description                     |
|----------------|----------|---------------------------------|
| subject        | TEXT     | Subject code (e.g., `CS`)       |
| course_id      | TEXT     | Normalized 8-char course code   |
| credits        | FLOAT    | Credit hours                    |
| offered_fall   | BOOLEAN  | Offered in Fall semester        |
| offered_spring | BOOLEAN  | Offered in Spring semester      |

---

### `prerequisites`

| Column      | Type | Description                              |
|-------------|------|------------------------------------------|
| subject     | TEXT | Subject code                             |
| course_id   | TEXT | Course that has the prerequisite         |
| prereq_id   | TEXT | The prerequisite course                  |
| type        | INT  | `0` = AND group, `-1` = OR group         |

---

### `timings`

| Column     | Type | Description                                      |
|------------|------|--------------------------------------------------|
| subject    | TEXT | Subject code                                     |
| course_id  | TEXT | Course code                                      |
| group_idx  | INT  | Index of timing group (e.g., 0, 1, 2...)          |
| start      | INT  | Start time in minutes from Monday 12:00am        |
| end_time   | INT  | End time in minutes from Monday 12:00am          |

> Each `group_idx` represents a distinct section or set of class sessions (e.g., MWF 9–9:50am).

---

### `lecture_counts`

| Column     | Type | Description                            |
|------------|------|----------------------------------------|
| subject    | TEXT | Subject code                           |
| course_id  | TEXT | Course code                            |
| group_idx  | INT  | Index of timing group                  |
| count      | INT  | Number of (start, end) sessions stored |

---

You can query this database directly using the DuckDB CLI:

```bash
duckdb data/combined.duckdb

```
Or from Python using the DuckDB client:

```python
import duckdb

# Connect to the database
con = duckdb.connect("data/combined.duckdb")

# Run a query (example: list all CS courses)
results = con.execute("SELECT * FROM courses WHERE subject = 'CS'").fetchall()

# Print results
for row in results:
    print(row)
