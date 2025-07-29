# UIC Smart Course Scheduler (GPIP Project)

This project scrapes and models course data from the University of Illinois Chicago (UIC) to support automated semester planning and curriculum mapping for undergraduate majors.

## 🔍 What It Does

- Scrapes the official UIC Schedule of Classes website for:
  - Course offerings (Fall/Spring)
  - Course prerequisites
  - Course timings (in minutes from Monday midnight)
  - Course credit hours
- Processes data for all 190+ subjects and maps it to 93+ official undergraduate majors
- Builds a single `combined.json` file containing:
  - All major-specific courses with metadata
  - A fallback section for unmapped subjects
  - Clean lecture-only timing data (excluding labs/discussions)

## 🗂 Output Structure

- `data/combined.json`  
  Structure:
  ```json
  {
    "computer_science": {
      "subject_code": "CS",
      "min_total_credits": 128,
      "courses": {
        "CS___141": {
          "credits": "4",
          "prerequisites": {
            "strict": [["CS___107"]],
            "concurrent": [["MATH_180"]]
          },
          "offered": {
            "fall": true,
            "spring": true
          },
          "timing": [
            {
              "crn": "12345",
              "times": [
                { "start": 840, "end": 930 },
                { "start": 960, "end": 1050 }
              ]
            }
          ]
        }
      }
    },
    "unmapped_subjects": {
      "MOVI": {
        "courses": { ... }
      }
    }
  }

## 🌿 Branch Overview

This repository contains two active branches for different JSON formats:

### `main`
> 🎓 **Major-Centric Format**

- Top-level keys: undergraduate majors (e.g. `"computer_science"`)
- Contains:
  - `subject_code`
  - `min_total_credits`
  - Dictionary of courses keyed by 8-character course code
  - Fallback `"unmapped_subjects"` section

### `subject_json_format`
> 🧾 **Subject-Centric Format**

- Top-level keys: subject codes (e.g. `"CS"`, `"MATH"`, `"ECE"`)
- Each subject contains a list of course dictionaries:
  ```json
  {
    "id": "CS_141",
    "credits": [4],
    "offerings": { "fall": true, "spring": true },
    "prerequisites": [
      { "id": "CS_107", "type": "0" }
    ],
    "timing": {
      "0": {
        "days": 2,
        "time": [840, 930, 960, 1050]
      },
      "1": {
        "days": 1,
        "time": [660, 750]
      }
    }
  }


### 🗃️ DuckDB: `data/combined.duckdb`

A compact SQL database is generated using DuckDB with the following tables:

- `courses`:  
  - `subject`, `course_id`, `credits`, `offered_fall`, `offered_spring`

- `prerequisites`:  
  - `subject`, `course_id`, `prereq_id`, `type` (`-1` for OR-group, `0` for AND)

- `timings`:  
  - `subject`, `course_id`, `crn`, `start`, `end`

- `lecture_counts`:  
  - `subject`, `course_id`, `crn`, `lecture_count`

You can query this database directly using the DuckDB CLI or Python DuckDB client.
(This is found in the branch subject_json_format)

