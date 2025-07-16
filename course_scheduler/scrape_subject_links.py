### scrape_subject_links.py
import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from collections import defaultdict



BASE_URLS = {
    "fall": "https://webcs7.osss.uic.edu/schedule-of-classes/static/schedules/fall-2024/",
    "spring": "https://webcs7.osss.uic.edu/schedule-of-classes/static/schedules/spring-2025/",
}

CS_URLS = {
    "fall": BASE_URLS["fall"] + "CS.html",
    "spring": BASE_URLS["spring"] + "CS.html"
}

# Request headers to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

master = {}
offering_term = {}  # norm_code → "fall" or "spring"
excluded_courses = set()  # courses seen in both terms
seen_in_term = defaultdict(set)  # term → set of course codes seen in that term
timings = defaultdict(list)  # CS___XXX_CRN → [(crn, start, end)]
prereqs = set()


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


def parse_course_table(url, term, subject):
    """Parse course table from UIC schedule page"""
    try:
        print(f"Fetching {url}")
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
                norm_code = code.replace(" ", "___")
                seen_in_term[norm_code].add(term)
                


                
                # Extract prerequisite sentence (e.g., "Prerequisite(s): CS 111 and CS 151.")
                prereq_match = re.search(r"Prerequisite\s*\(s\):\s*(.+)", text, re.IGNORECASE)
                if prereq_match:
                        
                    prereq_text = prereq_match.group(1)
                    
                    # Split prereq sentence into chunks by ; or " and "
                    chunks = re.split(r";|\band\b", prereq_text, flags=re.IGNORECASE)

                    for chunk in chunks:
                        flag = -1 if " or " in chunk.lower() else 0
                        course_refs = re.findall(r"\b([A-Z]{2,4})\s+(\d{3})\b", chunk)

                        for dept, num in course_refs:
                            prereq_code = f"{dept}___{num}"

                            if prereq_code == norm_code:
                                continue

                            if dept not in VALID_SUBJECTS:
                                continue

                            prereqs.add((prereq_code, norm_code, flag))




                    ## print(f"[PREREQ RAW] {norm_code}: {prereq_text}")

                                                
                match = re.search(rf"{subject}\s+(\d{{3}})", text)
                if not match:
                    continue

                course_number = match.group(1)
                code = f"{subject} {course_number}"
                norm_code = code.replace(" ", "___")


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
                        keep_types = ["LEC", "LEC-DIS", "LEC/LAB", "LBD", "LCD"]
                        if not any(t in course_type.upper() for t in keep_types):
                            continue


                        ## print(f"[LEC] {norm_code} — CRN {crn}, Time: {time}, Days: {days}")


                        ## if not time or not days:
                        ##    print(f"[SKIP] {norm_code} CRN {crn} — missing time or days: '{time}', '{days}'")

                        if not representative_crn:
                            representative_crn = crn  # Save first valid lecture CRN

                        
                        ## print(f"  Found lecture: CRN={crn}, Time={time}, Days={days}")
                        
                        # Parse timing
                        time_blocks = minutes_from_monday(time, days)
                        for start, end in time_blocks:
                            timings[f"{norm_code}_{crn}"].append((crn, start, end))
                        
                        
                        
                        found_lecture = True
                
                    

                        
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
    major_dir = os.path.join("majors", subject)
    os.makedirs(major_dir, exist_ok=True)

    """Write output files"""
    try:
        # Course offerings
        with open(os.path.join(major_dir, f"courseoffering_{subject}.txt"), "w") as f:
            # print(f"[DEBUG] Sample offering_term: {list(offering_term.items())[:3]}")
            for code in sorted(offering_term.keys()):
                term = offering_term[code]
                fall = 1 if term in ["fall", "both"] else 0
                spring = 1 if term in ["spring", "both"] else 0
                f.write(f"{code}\t{fall}\t{spring}\n")
        print(f"Wrote {len(offering_term)} course offerings")
        
        # Course timings
        with open(os.path.join(major_dir, f"coursetiming_{subject}.txt"), "w") as f:
            for section_id, time_blocks in sorted(timings.items()):
                f.write(f"{section_id}\t{len(time_blocks)}")
                for crn, start, end in time_blocks:
                    f.write(f"\t{crn}\t{start}\t{end}")
                f.write("\n")
        print(f"Wrote {len(timings)} course timings")
        
        # Clean and filter prereqs
        prereqs_cleaned = [
            (prereq, course, flag)
            for prereq, course, flag in prereqs
            if prereq != course and isinstance(prereq, str) and isinstance(course, str)
        ]

        # Sort: first by course (middle column), then by prereq (left column)
        prereqs_sorted = sorted(
            prereqs_cleaned,
            key=lambda x: (
                int(x[1].split("___")[1]),  # course number (middle column)
                int(x[0].split("___")[1])  # prereq number (left column)
            )
        )

        # Write prerequisites file
        with open(os.path.join(major_dir, f"prerequisites_{subject}.txt"), "w") as f:
            for prereq, course, flag in prereqs_sorted:
                f.write(f"{prereq}\t{course}\t{flag}\n")



        print(f"Wrote {len(prereqs)} prerequisite placeholders")

        # Rebuild master course list from offering_term and timings keys
        with open(os.path.join(major_dir, f"mastercourselist_{subject}.txt"), "w") as f:
            added = set()
            all_seen = set(seen_in_term.keys()) | {key.rsplit("_", 1)[0] for key in timings.keys()}
            for code in sorted(all_seen):
                if code.count("___") == 1 and code not in added:
                    credit = master.get(code.replace("___", " "), "???")
                    f.write(f"{code}\t{credit}\n")
                    added.add(code)



        print(f"Wrote {len(added)} to mastercourselist_{subject}.txt")

        
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

    for subject in ["CS", "MATH", "ECE"]:
        if subject not in subjects:
            print(f"[SKIP] {subject} not found in subject list")
            continue

        urls = subjects[subject]

        print(f"\n=== Scraping {subject} ===")

        # Clear data between subjects
        master.clear()
        offering_term.clear()
        excluded_courses.clear()
        
        timings.clear()
        prereqs.clear()

        parse_course_table(urls["fall"], "fall", subject)
        parse_course_table(urls["spring"], "spring", subject)

        # Determine offering term for each course
        for norm_code, terms in seen_in_term.items():
            if "fall" in terms and "spring" in terms:
                continue  # Skip both-term courses
            elif "fall" in terms:
                offering_term[norm_code] = "fall"
            elif "spring" in terms:
                offering_term[norm_code] = "spring"

        

        write_outputs(subject)

        seen_in_term.clear()