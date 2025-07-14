### scrape_subject_links.py
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




def load_master():
    try:
        with open("data/mastercourselist_cs.txt") as f:
            for line in f:
                line = line.strip()
                if not line or '\t' not in line:
                    continue
                parts = line.split("\t")
                if len(parts) != 2:
                    # print(f"[SKIP] Malformed line in mastercourselist: {line}")
                    continue  # Skip lines that don't have exactly 2 parts
                code, credits = parts
                normalized = code.replace("___", " ")
                master[normalized] = credits
        print(f"Loaded {len(master)} courses from master list")
    except FileNotFoundError:
        print("Warning: mastercourselist_cs.txt not found")
    except Exception as e:
        print(f"Error loading master list: {e}")




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


def parse_course_table(url, term):
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
                
                # Get all text from the course block
                text = course.get_text(" ", strip=True)
                                                
                # Look for CS course codes
                cs_match = re.search(r"CS\s+(\d{3})", text)
                if not cs_match:
                    continue
                
                course_number = cs_match.group(1)

                code = f"CS {course_number}"
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
                prereqs.add(norm_code)
                


                
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


def write_outputs():
    """Write output files"""
    try:
        # Course offerings
        with open("courseoffering_cs.txt", "w") as f:
            # print(f"[DEBUG] Sample offering_term: {list(offering_term.items())[:3]}")
            for code in sorted(offering_term.keys()):
                term = offering_term[code]
                fall = 1 if term in ["fall", "both"] else 0
                spring = 1 if term in ["spring", "both"] else 0
                f.write(f"{code}\t{fall}\t{spring}\n")
        print(f"Wrote {len(offering_term)} course offerings")
        
        # Course timings
        with open("coursetiming_cs.txt", "w") as f:
            for section_id, time_blocks in sorted(timings.items()):
                f.write(f"{section_id}\t{len(time_blocks)}")
                for crn, start, end in time_blocks:
                    f.write(f"\t{crn}\t{start}\t{end}")
                f.write("\n")
        print(f"Wrote {len(timings)} course timings")
        
        # Prerequisites (placeholder)
        with open("prerequisites_cs.txt", "w") as f:
            for code in sorted(prereqs):
                f.write(f"{code}\t???\n")
        print(f"Wrote {len(prereqs)} prerequisite placeholders")

        # Rebuild master course list from offering_term and timings keys
        with open("mastercourselist_cs.txt", "w") as f:
            added = set()
            all_seen = set(seen_in_term.keys()) | {key.rsplit("_", 1)[0] for key in timings.keys()}
            for code in sorted(all_seen):
                if code.count("___") == 1 and code not in added:
                    credit = master.get(code.replace("___", " "), "???")
                    f.write(f"{code}\t{credit}\n")
                    added.add(code)



        print(f"Wrote {len(added)} to mastercourselist_cs.txt")

        
    except Exception as e:
        print(f"Error writing output files: {e}")


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
    load_master()

    # First, debug the page structure
    print("=== Debugging page structure ===")
    for term in ["fall", "spring"]:
        debug_page_structure(CS_URLS[term])
    
    print("\n=== Starting scraping ===")
    for term in ["fall", "spring"]:
        parse_course_table(CS_URLS[term], term)
    
    # Postprocess offerings
    for code, terms in seen_in_term.items():
        if "fall" in terms and "spring" in terms:
            excluded_courses.add(code)  # Exclude from offering file
        elif "fall" in terms:
            offering_term[code] = "fall"
        elif "spring" in terms:
            offering_term[code] = "spring"
        
        prereqs.add(code)  # Still add to prereq/master




    
    print(f"\nSummary:")
    print(f"Courses found: {len(offering_term)}")
    print(f"Excluded courses (both terms): {len(excluded_courses)}")
    print(f"Timing records: {len(timings)}")
    print(f"\nStats:")
    print(f"  Courses seen: {len(seen_in_term)}")
    print(f"  Offering courses: {len(offering_term)}")
    print(f"  Excluded (both terms): {len(excluded_courses)}")
    print(f"  Prerequisite stubs: {len(prereqs)}")
    print(f"  Timing entries: {len(timings)}")
    

    write_outputs()
    print("Done!")