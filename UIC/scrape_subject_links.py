import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from collections import defaultdict
import json

COREQ_PHRASES = re.compile(r'\b(concurrent registration|co-?requisite|corequisite)\b', re.IGNORECASE)
RECOMMENDED_PHRASES = re.compile(r'\brecommended background\b', re.IGNORECASE)


def generate_terms(start_year, end_year):
    terms = []
    for year in range(start_year, end_year + 1):
        terms.append(("fall", year))
        if year + 1 <= end_year:
            terms.append(("spring", year + 1))
    return terms

# Adjust these 2 values to control scraping range
start_year = 2024
end_year = 2025
TERMS = generate_terms(start_year, end_year)


BASE_URL = "https://webcs7.osss.uic.edu/schedule-of-classes/static/schedules"

def generate_term_urls(subject):
    return {
        f"{term}-{year}": f"{BASE_URL}/{term}-{year}/{subject}.html"
        for term, year in TERMS
    }


# Request headers to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

master = {}
offering_term = {}  # norm_code → "fall" or "spring"
excluded_courses = set()  # courses seen in both terms
seen_in_term = defaultdict(set)  # term → set of course codes seen in that term
timing_fall = defaultdict(list)
timing_spring = defaultdict(list)
latest_prereq_year = {}  # norm_code → year
prereq_map = {}          # norm_code → set of (prereq, flag)


# Also store term tracking for fallback
latest_fall_year = {}
latest_spring_year = {}

prereqs = set()
all_seen_terms = defaultdict(set)  # norm_code → set of terms like "fall-2022"



def frange(start, stop, step=1):
    """Float range for handling decimal credit ranges."""
    while start <= stop:
        yield round(start, 2)
        start += step


def minutes_from_monday(time_str, days_str):
    """Convert time string and days to minutes from Monday midnight"""
    day_map = {'M': 0, 'T': 1, 'W': 2, 'R': 3, 'F': 4}
    if "ARRANGED" in time_str.upper() or not days_str.strip():
        # print(f"[SKIP] Unparsable time: '{time_str}' days: '{days_str}'")
        return []

    try:
        # Handle different time formats
        if '-' not in time_str:
            return []
        
        start_str, end_str = [t.strip() for t in time_str.split('-')]
        
        # Parse times - handle both 12-hour and 24-hour formats
        try:
            start = datetime.strptime(start_str, '%I:%M %p')
            end = datetime.strptime(end_str, '%I:%M %p')
        except ValueError:
            try:
                start = datetime.strptime(start_str, '%H:%M')
                end = datetime.strptime(end_str, '%H:%M')
            except ValueError:
                # print(f"[SKIP] Unparsable time: '{time_str}' days: '{days_str}'")
                return []
        
        results = []
        for d in days_str:
            if d in day_map:
                start_minutes = day_map[d] * 24 * 60 + start.hour * 60 + start.minute
                end_minutes = day_map[d] * 24 * 60 + end.hour * 60 + end.minute
                results.append((start_minutes, end_minutes))
        
        return results
    except Exception as e:
        print(f"Error parsing time: {time_str}, {days_str} — {e}")
        return []


def normalize_course_code(subject, course_number):
    """Convert subject and course number to 8-character format with underscores"""
    # Calculate how many underscores needed: 8 total - len(subject) - len(course_number)
    underscores_needed = 8 - len(subject) - len(course_number)
    return f"{subject}{'_' * underscores_needed}{course_number}"


def parse_course_table(url, term, year, subject):
    """Parse a single subject's schedule page for a given term/year.
       - Captures concrete lecture timings (LEC/LCD/LBD, etc.)
       - If offered but no concrete time (ARRANGED/CNF), inserts placeholder (0,0)
       - Keeps 'latest year wins' behavior per term (fall/spring)
    """
    try:
        print(f"Fetching {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Try to locate course containers
        courses = soup.find_all("div", class_="course")
        if not courses:
            courses = soup.find_all("div", class_="course-block")
        if not courses:
            # Fallback: entire page tables (some pages are just big tables)
            courses = soup.find_all("table")
        if not courses:
            print("No courses found on page.")
            return

        for i, course in enumerate(courses):
            try:
                text = course.get_text(" ", strip=True)

                # Find "[SUBJ] [NNN]"
                match = re.search(rf"\b{subject}\s+(\d{{3}})\b", text)
                if not match:
                    continue

                course_number = match.group(1)
                code = f"{subject} {course_number}"
                norm_code = normalize_course_code(subject, course_number)

                # ===== Prerequisites (latest year wins) =====
                prereq_match = re.search(r"Prerequisite\s*\(s\):\s*(.+)", text, re.IGNORECASE)
                if prereq_match:
                    if norm_code not in latest_prereq_year or year > latest_prereq_year[norm_code]:
                        prereq_text = prereq_match.group(1)

                        # Split the prereq line into segments; we’ll classify each segment.
                        segments = re.split(r"[;.\n]", prereq_text)
                        current_links = set()

                        for seg in segments:
                            seg = seg.strip()
                            if not seg or RECOMMENDED_PHRASES.search(seg):
                                # e.g., "Recommended background: Concurrent registration in CHEM 233" → ignore entirely
                                continue

                            # coreq if segment mentions “concurrent registration” / “corequisite”
                            is_coreq = bool(COREQ_PHRASES.search(seg))

                            # pull all course refs in the segment
                            course_refs = re.findall(r"\b([A-Z]{2,5})\s+(\d{3})\b", seg)
                            for dept, num in course_refs:
                                if dept not in VALID_SUBJECTS:
                                    continue
                                prereq_code = normalize_course_code(dept, num)
                                if prereq_code == norm_code:
                                    continue

                                flag = 0 if is_coreq else -1   # 0 = coreq, -1 = prereq
                                current_links.add((prereq_code, norm_code, flag))

                        prereq_map[norm_code] = current_links
                        latest_prereq_year[norm_code] = year


                # ===== Credits extraction (range or single) =====
                # Try range: "X to Y hours"
                range_match = re.search(r"(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s+hours", text, re.IGNORECASE)
                if range_match:
                    start = float(range_match.group(1))
                    end = float(range_match.group(2))
                    credit = ",".join(str(int(v)) if float(v).is_integer() else str(v) for v in frange(start, end, 1))
                else:
                    single_match = re.search(r"(\d+(?:\.\d+)?)\s+hours", text, re.IGNORECASE)
                    credit = single_match.group(1) if single_match else "???"
                master[code] = credit

                # ===== Rows parsing (sections/times) =====
                rows = course.find_all("tr")
                if not rows:
                    # Some course blocks might not have a table
                    # We still allow placeholder logic below if CNF/LEC appears in text
                    rows = []

                captured_any_time = False       # parsed at least one concrete timing block
                offered_any_section = False     # course has a relevant section this term
                representative_crn = None

                # Section types that indicate the course is offered in this term
                relevant_types = {"LEC", "LEC-DIS", "LEC/LAB", "LCD", "LBD", "CNF"}
                # Only these types produce concrete timing blocks
                keep_types = {"LEC", "LEC-DIS", "LEC/LAB", "LCD"}

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 6:
                        continue

                    col_texts = [col.get_text(strip=True) for col in cols]
                    crn = col_texts[0]
                    course_type = col_texts[1].strip().upper()
                    time = col_texts[2]
                    days = col_texts[3]

                    # Offered if we see any relevant type
                    if any(t in course_type for t in relevant_types):
                        offered_any_section = True
                        if not representative_crn:
                            representative_crn = crn

                    # Only try to parse concrete timing for keep_types
                    if not any(t in course_type for t in keep_types):
                        continue

                    # Skip explicit ARRANGED (no parseable time window)
                    if "ARRANGED" in time.upper() or not days.strip():
                        continue

                    time_blocks = minutes_from_monday(time, days)
                    for start_min, end_min in time_blocks:
                        captured_any_time = True
                        if term == "fall":
                            if norm_code not in latest_fall_year or year > latest_fall_year[norm_code]:
                                timing_fall[norm_code] = [(crn, start_min, end_min)]
                                latest_fall_year[norm_code] = year
                            elif year == latest_fall_year[norm_code]:
                                timing_fall[norm_code].append((crn, start_min, end_min))
                        elif term == "spring":
                            if norm_code not in latest_spring_year or year > latest_spring_year[norm_code]:
                                timing_spring[norm_code] = [(crn, start_min, end_min)]
                                latest_spring_year[norm_code] = year
                            elif year == latest_spring_year[norm_code]:
                                timing_spring[norm_code].append((crn, start_min, end_min))

                # ===== FLEXIBLE-TIME PLACEHOLDER =====
                # If the course is offered in this term but we captured no concrete times,
                # write a single (0,0) block (12:00 AM Monday) for that term/year.
                if offered_any_section and not captured_any_time:
                    placeholder_crn = representative_crn or "00000"
                    if term == "fall":
                        if norm_code not in latest_fall_year or year >= latest_fall_year[norm_code]:
                            timing_fall[norm_code] = [(placeholder_crn, 0, 0)]
                            latest_fall_year[norm_code] = year
                    elif term == "spring":
                        if norm_code not in latest_spring_year or year >= latest_spring_year[norm_code]:
                            timing_spring[norm_code] = [(placeholder_crn, 0, 0)]
                            latest_spring_year[norm_code] = year

                # Mark seen/offered for this term if we found any relevant section
                if offered_any_section:
                    seen_in_term[norm_code].add(term)
                    all_seen_terms[norm_code].add(f"{term}-{year}")

            except Exception as e:
                print(f"Error processing course block #{i}: {e}")
                continue

    except requests.RequestException as e:
        print(f"Failed to fetch {url}: {e}")
    except Exception as e:
        print(f"Error parsing {url}: {e}")



def write_outputs(subject):
    # Create subfolder for this subject
    major_dir = os.path.join("UIC/data/subjects", subject)
    os.makedirs(major_dir, exist_ok=True)

    """Write output files"""
    try:
        # Course offerings
        with open(os.path.join(major_dir, f"courseoffering_{subject}.txt"), "w") as f:
            # print(f"[DEBUG] Sample offering_term: {list(offering_term.items())[:3]}")
            for code in sorted(offering_term.keys()):
                # ✅ Skip if course is not from this subject
                if not code.startswith(subject + "_"):
                    continue

                term = offering_term[code]
                if term == "both":
                    continue  # ❌ skip courses offered in both terms

                fall = 1 if term == "fall" else 0
                spring = 1 if term == "spring" else 0
                f.write(f"{code}\t{fall}\t{spring}\n")


        #print(f"Wrote {len(offering_term)} course offerings")
        
        # Group all (start, end) pairs per course, ignoring CRNs
        #course_timings = defaultdict(set)  # course_code → set of (start, end)

        # Group all (start, end) pairs per course but preserve CRNs

        with open(os.path.join(major_dir, f"coursetiming_{subject}.txt"), "w") as f:
            for course_code in sorted(set(timing_fall.keys()) | set(timing_spring.keys())):
                for term, timing_dict in [("fall", timing_fall), ("spring", timing_spring)]:
                    if course_code not in timing_dict:
                        continue

                    sessions = timing_dict[course_code]
                    if not sessions:
                        continue

                    # Group by CRN
                    crn_sessions = defaultdict(list)
                    for crn, start, end in sessions:
                        crn_sessions[crn].append((start, end))

                    num_sections = len(crn_sessions)

                    for crn, blocks in sorted(crn_sessions.items()):
                        f.write(f"{course_code}\t{term}\t{num_sections}\t{len(blocks)}")
                        for start, end in blocks:
                            f.write(f"\t{crn}\t{start}\t{end}")
                        f.write("\n")


        
        # Clean and filter prereqs
        # Flatten prereq_map into list
        prereqs_cleaned = [
            (prereq, course, flag)
            for course, prereq_set in prereq_map.items()
            for (prereq, course, flag) in prereq_set
        ]


        # Sort: first by course (middle column), then by prereq (left column)
        prereqs_sorted = sorted(
            prereqs_cleaned,
            key=lambda x: (
                int(x[1][-3:]),  # course number (last 3 chars)
                int(x[0][-3:])   # prereq number (last 3 chars)
            )
        )

        # Write prerequisites file
        with open(os.path.join(major_dir, f"prerequisites_{subject}.txt"), "w") as f:
            for prereq, course, flag in prereqs_sorted:
                f.write(f"{prereq}\t{course}\t{flag}\n")



        #print(f"Wrote {len(prereqs)} prerequisite placeholders")

        # Rebuild master course list from offering_term and timings keys
                # Rebuild master course list from offering_term, timings, and prereqs
        with open(os.path.join(major_dir, f"mastercourselist_{subject}.txt"), "w") as f:
            added = set()

            # Gather all seen course codes
            all_seen = (
                set(seen_in_term.keys()) |
                set(timing_fall.keys()) |
                set(timing_spring.keys())
            )


            # Only include prereqs that belong to the current subject
            prereq_courses = {
                prereq for prereq, _, _ in prereqs_cleaned
                if prereq.startswith(subject + "_")
            }



            all_codes = all_seen | prereq_courses

            for code in sorted(all_codes):
                if len(code) != 8 or code in added:
                    continue
                subject_part = code.rstrip('_0123456789')
                number_part = code[-3:]
                original_format = f"{subject_part} {number_part}"
                if original_format in master:
                    credit = master[original_format]
                else:
                    credit = "???"
                    # Try live UIC catalog lookup if missing
                    # fetched = get_credit_from_uic_catalog(subject_part, number_part)
                    # if fetched != "???":
                    #     credit = fetched
                if credit == "???" or not credit:
                    continue  # ❌ Skip courses without valid credit

                f.write(f"{code}\t{credit}\n")
                added.add(code)




        #print(f"Wrote {len(added)} to mastercourselist_{subject}.txt")

        
    except Exception as e:
        print(f"Error writing output files: {e}")



def get_all_subjects():
    base_url = "https://webcs7.osss.uic.edu/schedule-of-classes/static/schedules"
    index_url = f"{base_url}/fall-2024/index.html"

    try:
        response = requests.get(index_url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        subject_map = {}

        for a in soup.find_all("a", href=True):
            href = a["href"]
            match = re.match(r"([A-Z]{2,5})\.html$", href)
            if match:
                subject = match.group(1)
                subject_map[subject] = {
                    "fall": f"{base_url}/fall-2024/{subject}.html",
                    "spring": f"{base_url}/spring-2025/{subject}.html"
                }

        print(f"[INFO] Found {len(subject_map)} subjects")
        return subject_map

    except Exception as e:
        print(f"[ERROR] Failed to load subject list: {e}")
        return {}




def debug_page_structure(url):
    """Debug function to inspect page structure"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # print(f"\n=== Debug info for {url} ===")
        # print(f"Title: {soup.title.string if soup.title else 'No title'}")
        
        # Look for common class names
        for class_name in ['course', 'course-block', 'course-info', 'class', 'section']:
            elements = soup.find_all(class_=class_name)
            if elements:
                print(f"Found {len(elements)} elements with class '{class_name}'")
        
        # Look for tables
        tables = soup.find_all('table')
        print(f"Found {len(tables)} tables")
        
        # Print first few lines of page
        ## print("\nFirst 500 characters of page:")
        ## print(soup.get_text()[:500])
        
    except Exception as e:
        print(f"Debug error: {e}")


if __name__ == "__main__":
    subjects = get_all_subjects()
    VALID_SUBJECTS = set(subjects)  # e.g., {"CS", "MATH", "ECE", ...}

    for subject in sorted(subjects):
        if subject not in subjects:
            print(f"[SKIP] {subject} not found in subject list")
            continue

        urls = subjects[subject]

        print(f"\n=== Scraping {subject} ===")

        # Clear data between subjects
        master.clear()
        offering_term.clear()
        excluded_courses.clear()
        timing_fall.clear()
        timing_spring.clear()
        latest_fall_year.clear()
        latest_spring_year.clear()
        offering_term.clear()
        prereqs.clear()
        seen_in_term.clear()
        latest_prereq_year.clear()
        prereq_map.clear()
        all_seen_terms.clear()




        term_urls = generate_term_urls(subject)
        for term, year in TERMS:
            term_key = f"{term}-{year}"
            if term_key not in term_urls:
                continue
            parse_course_table(term_urls[term_key], term, year, subject)



        # Determine offering term for each course
        for norm_code, terms in all_seen_terms.items():
            offered_fall = any(t.startswith("fall") for t in terms)
            offered_spring = any(t.startswith("spring") for t in terms)

            if offered_fall and offered_spring:
                offering_term[norm_code] = "both"
            elif offered_fall:
                offering_term[norm_code] = "fall"
            elif offered_spring:
                offering_term[norm_code] = "spring"


        

        write_outputs(subject)

        seen_in_term.clear()
    print("Done")