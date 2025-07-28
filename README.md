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
