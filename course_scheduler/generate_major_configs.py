### --------- generate_major_configs.py --------- ###
import os
import json
import re
from collections import defaultdict

major_to_subject = {
    "Disability and Human Development": "DHD",
    "Health Information Management": "HIM",
    "Kinesiology": "KN",
    "Nutrition-Nutrition Science": "HN",
    "Rehabilitation Sciences": "AHS",
    "Acting": "THTR",
    "Architecture": "ARCH",
    "Architectural Studies": "ARCH",
    "Art": "ART",
    "Art Education": "ART",
    "Art History": "AH",
    "Design Studies": "DES",
    "Graphic Design": "DES",
    "Industrial Design": "DES",
    "Interdisciplinary Education in the Arts": "IDEA",
    "Music": "MUS",
    "Music-Jazz Studies": "MUS",
    "Music-Performance": "MUS",
    "Music Business": "MUS",
    "Music Education": "MUS",
    "Theatre and Performance": "THTR",
    "Theatre Design, Production, and Technology": "THTR",
    "Accounting": "ACTG",
    "Entrepreneurship": "ENTR",
    "Finance": "FIN",
    "Human Resource Management": "MGMT",
    "Information and Decision Sciences": "IDS",
    "Management": "MGMT",
    "Marketing": "MKTG",
    "Real Estate": "FIN",
    "Urban Education": "ED",
    "Human Development and Learning": "ED",
    "Biomedical Engineering": "BME",
    "Chemical Engineering": "CHE",
    "Civil Engineering": "CE",
    "Computer Engineering": "ECE",
    "Computer Science": "CS",
    "Computer Science and Design": "CS",
    "Data Science": "CS",
    "Electrical Engineering": "ECE",
    "Engineering Management": "IE",
    "Engineering Physics": "PHYS",
    "Environmental Engineering": "CE",
    "Industrial Engineering": "IE",
    "Mechanical Engineering": "ME",
    "Anthropology": "ANTH",
    "Applied Psychology": "PSCH",
    "Biochemistry": "BCMG",
    "Biological Sciences": "BIOS",
    "Black Studies": "BLST",
    "Central and Eastern European Studies": "CEES",
    "Chemistry-BA": "CHEM",
    "Chemistry-BS": "CHEM",
    "Classical Studies": "CL",
    "Communication": "COMM",
    "Computer Science and Linguistics": "LING",
    "Computer Science and Philosophy": "PHIL",
    "Criminology, Law, and Justice": "CLJ",
    "Earth and Environmental Sciences": "EAES",
    "Economics": "ECON",
    "English": "ENGL",
    "English-Teacher Education": "ENGL",
    "French and Francophone Studies": "FR",
    "French-Teacher Education": "FR",
    "Gender and Women's Studies": "GWS",
    "Germanic Studies": "GER",
    "German-Teacher Education": "GER",
    "Global Asian Studies": "GLAS",
    "History": "HIST",
    "History-Teacher Education": "HIST",
    "Integrated Health Studies": "IHS",
    "Italian": "ITAL",
    "Latin American and Latino Studies": "LALS",
    "Liberal Studies": "LIB",
    "Mathematics": "MATH",
    "Mathematics-Teacher Education": "MTHT",
    "Mathematics and Computer Science": "MCS",
    "Neuroscience": "NEUS",
    "Philosophy": "PHIL",
    "Physics-BA": "PHYS",
    "Physics-BS": "PHYS",
    "Political Science": "POLS",
    "Psychology": "PSCH",
    "Sociology": "SOC",
    "Spanish": "SPAN",
    "Spanish-Teacher Education": "SPAN",
    "Statistics": "STAT",
    "Nursing": "NURS",
    "Pharmaceutical Sciences": "PHAR",
    "Public Health": "PUBH",
    "Public Policy": "PPOL",
    "Urban Studies": "UPA"
}

def generate_config_for_major(major_name, subject_code, major_credit_requirements):
    subject_dir = os.path.join("data/subjects", subject_code)
    
    if not os.path.isdir(subject_dir):
        return None

    prefix = f"{subject_code}___"
    
    paths = {
        "credits": os.path.join(subject_dir, f"mastercourselist_{subject_code}.txt"),
        "prereqs": os.path.join(subject_dir, f"prerequisites_{subject_code}.txt"),
    }

    # Check if required files exist
    if not all(os.path.exists(p) for p in paths.values()):
        return None

    # 1. Load credits
    credits_map = {}
    with open(paths["credits"]) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 2:
                continue
            code, credit = parts
            try:
                credits_map[code] = float(credit)
            except:
                credits_map[code] = None

    # 2. Load prerequisites
    prereq_map = defaultdict(list)
    with open(paths["prereqs"]) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) != 3:
                continue
            prereq, course, _ = parts
            prereq_map[course].append(prereq)

    # 3. Build course data - simplified structure with exactly 8-character formatting
    courses = {}
    for course_code in sorted(credits_map.keys()):
        # Normalize to exactly 8 characters
        parts = course_code.split("___")
        if len(parts) == 2:
            subject, number = parts
            # Create 8-character format: pad subject with underscores to make total = 8
            base_code = f"{subject}_{number}"
            if len(base_code) < 8:
                # Add extra underscores after subject to reach 8 characters
                underscores_needed = 8 - len(subject) - len(number) - 1
                formatted_code = f"{subject}{'_' * underscores_needed}_{number}"
            else:
                formatted_code = base_code[:8]  # truncate if too long
        else:
            formatted_code = course_code[:8].ljust(8, '_')  # ensure 8 chars
        
        # Format prerequisites to exactly 8 characters too
        formatted_prereqs = []
        for prereq in prereq_map.get(course_code, []):
            prereq_parts = prereq.split("___")
            if len(prereq_parts) == 2:
                prereq_subject, prereq_number = prereq_parts
                prereq_base = f"{prereq_subject}_{prereq_number}"
                if len(prereq_base) < 8:
                    underscores_needed = 8 - len(prereq_subject) - len(prereq_number) - 1
                    formatted_prereq = f"{prereq_subject}{'_' * underscores_needed}_{prereq_number}"
                else:
                    formatted_prereq = prereq_base[:8]
                formatted_prereqs.append(formatted_prereq)
            else:
                formatted_prereqs.append(prereq[:8].ljust(8, '_'))
        
        courses[formatted_code] = {
            "credits": credits_map[course_code],
            "prerequisites": formatted_prereqs
        }

    # 4. Get total credit requirement
    min_total = major_credit_requirements.get(major_name, 120)

    # 5. Simple JSON structure
    config = {
        "major": major_name,
        "subject_code": subject_code,
        "min_total_credits": min_total,
        "courses": courses
    }

    return config

def main():
    os.makedirs("data/majors", exist_ok=True)

    # Load credit requirements from existing file
    with open("data/all_uic_degrees.json") as f:
        major_credit_requirements = json.load(f)

    generated_count = 0
    
    # Process each major
    for major_name, subject_code in major_to_subject.items():
        if major_name not in major_credit_requirements:
            continue

        config = generate_config_for_major(major_name, subject_code, major_credit_requirements)
        if config:
            # Use sanitized filename
            safe_major_name = re.sub(r'[^\w\s-]', '', major_name).replace(' ', '_')
            output_path = f"data/majors/{safe_major_name}.json"
            
            with open(output_path, "w") as f:
                json.dump(config, f, indent=2)
            
            generated_count += 1
            print(f"✅ Generated {output_path} ({major_credit_requirements[major_name]} credits)")
        else:
            print(f"⚠️ Skipped {major_name} ({subject_code}) - missing files")

    print(f"\n🎉 Generated {generated_count} major configuration files")

if __name__ == "__main__":
    main()