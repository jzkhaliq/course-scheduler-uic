import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from collections import defaultdict
import json

CACHE_FILE = "UIC/data/data_archive/credit_cache.json"

# Load or initialize the cache
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        credit_cache = json.load(f)
else:
    credit_cache = {}

def get_credit_from_uic_catalog(subject, course_num):
    import os
    import json
    import re
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException

    CACHE_FILE = "UIC/data/data_archive/credit_cache.json"
    key = f"{subject} {course_num}"

    # Load or init cache
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            credit_cache = json.load(f)
    else:
        credit_cache = {}

    if key in credit_cache and credit_cache[key] != "???":
        return credit_cache[key]

    # Set up headless Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print(f"[ERROR] Could not start ChromeDriver: {e}")
        credit_cache[key] = "???"
        with open(CACHE_FILE, "w") as f:
            json.dump(credit_cache, f, indent=2)
        return "???"

    try:
        url = f"https://catalog.uic.edu/search/?P={subject}%20{course_num}"
        driver.get(url)

        # Wait for <h3> elements to load
        WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.TAG_NAME, "h3"))
        )

        h3_tags = driver.find_elements(By.TAG_NAME, "h3")
        for tag in h3_tags:
            text = tag.text.strip()
            if f"{subject} {course_num}" in text:
                match = re.search(r"(\d+(?:\.\d+)?)\s+hours", text, re.IGNORECASE)
                if match:
                    credit = match.group(1)
                    credit_cache[key] = credit
                    with open(CACHE_FILE, "w") as f:
                        json.dump(credit_cache, f, indent=2)
                    print(f"✅ {key}: {credit}")
                    driver.quit()
                    return credit

    except TimeoutException:
        print(f"[TIMEOUT] {key} took too long to load")
    except Exception as e:
        print(f"[ERROR] {key}: {e}")
    finally:
        driver.quit()

    credit_cache[key] = "???"
    with open(CACHE_FILE, "w") as f:
        json.dump(credit_cache, f, indent=2)
    print(f"❌ {key}: ???")
    return "???"




TERMS = [
    ("fall", 2022),
    ("spring", 2023),
    ("fall", 2023),
    ("spring", 2024),
    ("fall", 2024),
    ("spring", 2025)
]

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
    """Parse course table from UIC schedule page"""
    try:
        #print(f"Fetching {url}")
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Debug: Print page structure
        ## print(f"Page title: {soup.title.string if soup.title else 'No title'}")
        
        # Try different selectors to find course information
        courses = soup.find_all("div", class_="course")
        if not courses:
            # Try alternative selectors
            courses = soup.find_all("div", class_="course-block")
        if not courses:
            courses = soup.find_all("table")
        
        ## print(f"Found {len(courses)} potential course containers in {term}")
        
        if not courses:
            print("No courses found. Printing page structure:")
            print(soup.prettify()[:1000])  # First 1000 chars
            return
        
        for i, course in enumerate(courses):
            try:
                
                text = course.get_text(" ", strip=True)

                match = re.search(rf"{subject}\s+(\d{{3}})", text)
                if not match:
                    continue

                course_number = match.group(1)
                code = f"{subject} {course_number}"
                norm_code = normalize_course_code(subject, course_number)
                seen_in_term[norm_code].add(term)
                all_seen_terms[norm_code].add(f"{term}-{year}")
                


                
                # Extract prerequisite sentence (e.g., "Prerequisite(s): CS 111 and CS 151.")
                prereq_match = re.search(r"Prerequisite\s*\(s\):\s*(.+)", text, re.IGNORECASE)
                if prereq_match:
                    # Only update if this is the latest year
                    if norm_code not in latest_prereq_year or year > latest_prereq_year[norm_code]:
                        prereq_text = prereq_match.group(1)
                        chunks = re.split(r";|\band\b", prereq_text, flags=re.IGNORECASE)

                        current_prereqs = set()

                        for chunk in chunks:
                            flag = -1 if " or " in chunk.lower() else 0
                            course_refs = re.findall(r"\b([A-Z]{2,4})\s+(\d{3})\b", chunk)

                            for dept, num in course_refs:
                                prereq_code = normalize_course_code(dept, num)

                                if prereq_code == norm_code:
                                    continue
                                if dept not in VALID_SUBJECTS:
                                    continue

                                current_prereqs.add((prereq_code, norm_code, flag))

                        # Overwrite if this year is newer
                        prereq_map[norm_code] = current_prereqs
                        latest_prereq_year[norm_code] = year


                                                
                match = re.search(rf"{subject}\s+(\d{{3}})", text)
                if not match:
                    continue

                course_number = match.group(1)
                code = f"{subject} {course_number}"
                norm_code = normalize_course_code(subject, course_number)


                # Always mark this course as seen, even if no table rows
                seen_in_term[norm_code].add(term)

                # Also try to extract credits here
                credit_match = re.search(r"(\d+(?:\.\d+)?)(?:\s+to\s+\d+(?:\.\d+)?)?\s+hours", text, re.IGNORECASE)
                if credit_match:
                    master[code] = credit_match.group(1)
                else:
                    master[code] = "???"


                # Try to extract course credit from "... 3 hours." or "... 4.0 hours."
                # Match variable range: "1 to 3 hours"
                range_match = re.search(r"(\d+(?:\.\d+)?)\s+to\s+(\d+(?:\.\d+)?)\s+hours", text, re.IGNORECASE)
                if range_match:
                    start = float(range_match.group(1))
                    end = float(range_match.group(2))
                    # Build comma-separated range like "1,2,3"
                    credit = ",".join(str(int(i)) if i.is_integer() else str(i)
                                    for i in frange(start, end + 1))
                else:
                    # Fallback to single credit match: "3 hours"
                    credit_match = re.search(r"(\d+(?:\.\d+)?)\s+hours", text, re.IGNORECASE)
                    credit = credit_match.group(1) if credit_match else "???"

                # Save scraped credit to master (overwrite or create)
                master[code] = credit

                seen_in_term[norm_code].add(term)

                # Ensure the course is tracked even if no valid LEC time
                ## prereqs.add(norm_code)
                


                
                ## print(f"Processing course: {code}")
                
                # Find table rows within this course block
                rows = course.find_all('tr')
                if not rows:
                    # If no table, try to parse text directly
                    print(f"No table rows found for {code}, trying text parsing")
                    continue
                
                found_lecture = False

                representative_crn = None

                for row in rows:
                    cols = row.find_all('td')
                    
                    if len(cols) < 6:
                        continue
                    
                    # Extract column data
                    col_texts = [col.get_text(strip=True) for col in cols]
                    
                    # Assuming column order: CRN, Type, Time, Days, Room, Building, ...
                    if len(col_texts) >= 6:
                        crn = col_texts[0]
                        course_type = col_texts[1]
                        time = col_texts[2]
                        days = col_texts[3]
                        room = col_texts[4]
                        building = col_texts[5]
                        
                        # Only process lecture sections
                        keep_types = ["LEC", "LEC-DIS", "LEC/LAB", "LCD"]
                        if not any(t in course_type.upper() for t in keep_types):
                            continue


                        if not representative_crn:
                            representative_crn = crn  # Save first valid lecture CRN
                        
                        # Parse timing
                        time_blocks = minutes_from_monday(time, days)
                        for start, end in time_blocks:
                            if term == "fall":
                                # Only keep latest fall
                                if norm_code not in latest_fall_year or year > latest_fall_year[norm_code]:
                                    timing_fall[norm_code] = [(crn, start, end)]
                                    latest_fall_year[norm_code] = year
                                elif year == latest_fall_year[norm_code]:
                                    timing_fall[norm_code].append((crn, start, end))

                            elif term == "spring":
                                if norm_code not in latest_spring_year or year > latest_spring_year[norm_code]:
                                    timing_spring[norm_code] = [(crn, start, end)]
                                    latest_spring_year[norm_code] = year
                                elif year == latest_spring_year[norm_code]:
                                    timing_spring[norm_code].append((crn, start, end))

                        
                        
                        
                        found_lecture = True
                # If no timing was captured, look for fallback LBD section
                if not found_lecture:
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) < 6:
                            continue

                        col_texts = [col.get_text(strip=True) for col in cols]
                        crn = col_texts[0]
                        course_type = col_texts[1].strip().upper()
                        time = col_texts[2]
                        days = col_texts[3]

                        if course_type != "LBD":
                            continue

                        # Store first CRN if still missing
                        if not representative_crn:
                            representative_crn = crn

                        # Parse timing
                        time_blocks = minutes_from_monday(time, days)
                        for start, end in time_blocks:
                            if term == "fall":
                                if norm_code not in latest_fall_year or year > latest_fall_year[norm_code]:
                                    timing_fall[norm_code] = [(crn, start, end)]
                                    latest_fall_year[norm_code] = year
                            elif term == "spring":
                                if norm_code not in latest_spring_year or year > latest_spring_year[norm_code]:
                                    timing_spring[norm_code] = [(crn, start, end)]
                                    latest_spring_year[norm_code] = year

                        found_lecture = True
                        break  # Only take the first valid LBD

                    

                        
            except Exception as e:
                print(f"Error processing course {i}: {e}")
                continue
                
    except requests.RequestException as e:
        print(f"Failed to fetch {url}: {e}")
        return
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return


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
                prereq for prereq, _, _ in prereqs
                if prereq[:len(subject)] == subject and prereq[len(subject)] == '_'
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
                    fetched = get_credit_from_uic_catalog(subject_part, number_part)
                    if fetched != "???":
                        credit = fetched
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

        # print(f"\n=== Scraping {subject} ===")

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