# === planner.py ===
from collections import deque
import re

class Planner:
    def __init__(self, catalog, max_credits=18, max_terms=8, config=None):
        self.catalog = catalog
        self.max_credits = max_credits
        self.max_terms = max_terms
        self.config = config or {}


    def course_level(self, code):
        match = re.search(r"CS___(\d+)", code)
        return int(match.group(1)) if match else 999

    def is_course_allowed(self, code, completed, taken_intro):
        course = self.catalog.courses.get(code)
        if not course:
            return False

        prefix = self.config.get("course_prefix", "")
        intro_courses = set(self.config.get("intro_courses", []))
        placeholder_courses = set(self.config.get("placeholder_courses", []))
        excluded_levels = set(self.config.get("exclude_levels", []))

        # Skip placeholders like XXX or 499
        if code in placeholder_courses:
            return False

        # Skip excluded levels (500, 600, etc.)
        for level in excluded_levels:
            if code.startswith(f"{prefix}{level}"):
                return False

        # Skip if already completed
        if code in completed:
            return False

        # Only one intro course allowed
        if code in intro_courses and taken_intro:
            return False

        return True


    def plan(self, starting_courses):
        completed = set(starting_courses)
        plan = []
        term_names = ["fall", "spring"] * (self.max_terms // 2)
        intro_or_group = {"CS___107", "CS___109", "CS___111", "CS___112", "CS___113"}
        taken_intro = any(course in intro_or_group for course in completed)
        all_codes = sorted(self.catalog.courses.keys())

        for term_idx, term in enumerate(term_names):
            semester = []
            current_courses = set()
            total_credits = 0
            scheduled_this_term = set()

            # Pass 1 — strict prereqs
            for code in all_codes:
                if not self.is_course_allowed(code, completed, taken_intro):
                    continue

                course = self.catalog.courses.get(code)
                if not course or not course.offerings.get(term, True):
                    continue

                # 🛑 Defer CS___499 until final semester only
                if code == "CS___499" and term_idx != self.max_terms - 1:
                    continue

                rule = self.catalog.prereqs.get(code)
                is_variable_credit = len(course.credits) > 1
                no_real_prereqs = rule is None or (not rule.strict and not rule.concurrent)

                if is_variable_credit and no_real_prereqs and term_idx < 4:
                    continue

                if code in intro_or_group and taken_intro:
                    continue
                if rule and not rule.strict_satisfied(completed):
                    continue
                if rule and rule.concurrent and not rule.concurrent_satisfied(completed, set()):
                    continue

                if self.has_conflict(code, current_courses):
                    continue


                credits = max(course.credits)
                if total_credits + credits > self.max_credits:
                    continue

                semester.append((code, credits))
                current_courses.add(code)
                total_credits += credits
                scheduled_this_term.add(code)

                if code in intro_or_group:
                    taken_intro = True

            # Pass 2 — allow courses with concurrent prereqs now met
            for code in all_codes:
                if code in scheduled_this_term or code in completed:
                    continue
                if not self.is_course_allowed(code, completed, taken_intro):
                    continue

                course = self.catalog.courses.get(code)
                if not course or not course.offerings.get(term, True):
                    continue

                # 🛑 Defer CS___499 until final semester only
                if code == "CS___499" and term_idx != self.max_terms - 1:
                    continue

                rule = self.catalog.prereqs.get(code)
                is_variable_credit = len(course.credits) > 1
                no_real_prereqs = rule is None or (not rule.strict and not rule.concurrent)

                if is_variable_credit and no_real_prereqs and term_idx < 4:
                    continue

                if code in intro_or_group and taken_intro:
                    continue
                if rule:
                    if not rule.strict_satisfied(completed):
                        continue
                    if not rule.concurrent_satisfied(completed, current_courses):
                        continue

                if self.has_conflict(code, current_courses):
                    continue


                credits = max(course.credits)
                if total_credits + credits > self.max_credits:
                    continue

                semester.append((code, credits))
                current_courses.add(code)
                total_credits += credits
                scheduled_this_term.add(code)

                if code in intro_or_group:
                    taken_intro = True

            for code, _ in semester:
                completed.add(code)

            if semester:
                plan.append(semester)
            else:
                break

        # ✅ Check for missing required courses
        required = set(self.config.get("required_courses", []))
        equivalents = self.config.get("required_course_equivalents", {})
        missing = set()

        for course in required:
            if course in completed:
                continue
            # If any equivalent is completed, treat it as satisfied
            if any(eq in completed for eq in equivalents.get(course, [])):
                continue
            missing.add(course)

        if missing:
            print(f"\n⚠️ Warning: Required courses not scheduled: {sorted(missing)}\n")
        
        # ✅ Elective pool check
        elective_pool = set(self.config.get("elective_pool", {}).get("courses", []))
        min_electives = self.config.get("elective_pool", {}).get("min_required", 0)
        scheduled_electives = [c for c in completed if c in elective_pool]

        if len(scheduled_electives) < min_electives:
            missing_count = min_electives - len(scheduled_electives)
            print(f"\n⚠️ Warning: Only {len(scheduled_electives)} electives taken from the required {min_electives}.")
            print(f"Missing {missing_count} elective(s).")
            print(f"Electives taken: {sorted(scheduled_electives)}")
            print(f"Eligible electives: {sorted(elective_pool)}\n")

        # ✅ Total credit check
        min_credits = self.config.get("min_total_credits", 128)
        total_credits = sum(credits for semester in plan for _, credits in semester)

        if total_credits < min_credits:
            print(f"\n⚠️ Warning: Only {total_credits} total credits scheduled — {min_credits} required to graduate.")
        else:
            print(f"\n✅ Total credits scheduled: {total_credits} / {min_credits}\n")


        return plan
    
    def has_conflict(self, code, current_courses):
        for other in current_courses:
            for s1, e1 in self.catalog.timings.get(code, []):
                for s2, e2 in self.catalog.timings.get(other, []):
                    if s1 < e2 and s2 < e1:
                        return True
        return False


