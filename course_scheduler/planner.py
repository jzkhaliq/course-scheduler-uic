# === planner.py ===
from collections import deque

class Planner:
    def __init__(self, catalog, max_credits=18, max_terms=8):
        self.catalog = catalog
        self.max_credits = max_credits
        self.max_terms = max_terms

    def plan(self, starting_courses):
        completed = set(starting_courses)
        plan = []
        term_names = ["fall", "spring"] * (self.max_terms // 2)

        indegree = self.catalog.indegree.copy()
        available = deque([code for code in self.catalog.courses if indegree[code] == 0 and code not in completed])

        intro_or_group = set(["CS___107", "CS___109", "CS___111", "CS___112", "CS___113"])

        for term in term_names:
            semester = []
            total = 0
            next_available = deque()
            scheduled_this_term = set()

            while available and total < self.max_credits:
                code = available.popleft()
                if code in completed or code in scheduled_this_term:
                    continue

                # Skip junk and grad courses
                if code.startswith("CS___XXX") or code == "CS___499":
                    continue
                if max(self.catalog.courses[code].credits, default=0) == 0:
                    continue
                if code.startswith("CS___5") or code.startswith("CS___6"):
                    continue

                # Enforce only one intro course
                if code in intro_or_group and (intro_or_group & completed or intro_or_group & scheduled_this_term):
                    continue

                course = self.catalog.courses[code]
                if not course.offerings.get(term, True):
                    next_available.append(code)
                    continue

                rule = self.catalog.prereqs.get(code)
                if rule:
                    if not rule.strict_satisfied(completed):
                        continue
                    if not rule.concurrent_satisfied(completed, scheduled_this_term):
                        continue

                credits = max(course.credits)
                if total + credits <= self.max_credits:
                    semester.append((code, credits))
                    total += credits
                    scheduled_this_term.add(code)
                    completed.add(code)
                    for neighbor in self.catalog.graph[code]:
                        indegree[neighbor] -= 1
                        if indegree[neighbor] == 0:
                            next_available.append(neighbor)

            if not semester:
                break

            plan.append(semester)
            available = next_available

        return plan