# === planner.py ===
from collections import deque
import re

class Planner:
    def __init__(self, catalog, max_credits=18, max_terms=8):
        self.catalog = catalog
        self.max_credits = max_credits
        self.max_terms = max_terms

    def course_level(self, code):
        match = re.search(r"CS___(\d+)", code)
        return int(match.group(1)) if match else 999

    def topological_sort(self):
        indegree = self.catalog.indegree.copy()
        queue = deque([c for c in self.catalog.courses if indegree[c] == 0])
        topo_order = []

        while queue:
            queue = deque(sorted(queue))  # Lexical tie-breaking
            node = queue.popleft()
            topo_order.append(node)
            for neighbor in self.catalog.graph[node]:
                indegree[neighbor] -= 1
                if indegree[neighbor] == 0:
                    queue.append(neighbor)

        return topo_order

    def is_course_allowed(self, code, completed, taken_intro):
        """Check if a course should be scheduled"""
        course = self.catalog.courses.get(code)
        if not course:
            return False
        
        # Skip 0-credit courses
        if max(course.credits, default=0) == 0:
            return False
        
        # Skip grad courses (5xx, 6xx)
        if code.startswith("CS___5") or code.startswith("CS___6"):
            return False
        
        # Skip placeholder courses
        if code.startswith("CS___XXX") or code == "CS___499":
            return False
        
        # Skip if already completed
        if code in completed:
            return False
        
        # Intro course group logic - only allow one
        intro_or_group = {"CS___107", "CS___109", "CS___111", "CS___112", "CS___113"}
        if code in intro_or_group and taken_intro:
            return False
        
        return True

    def plan(self, starting_courses):
        completed = set(starting_courses)
        plan = []
        term_names = ["fall", "spring"] * (self.max_terms // 2)
        intro_or_group = {"CS___107", "CS___109", "CS___111", "CS___112", "CS___113"}
        taken_intro = any(course in intro_or_group for course in completed)

        topo_order = self.topological_sort()
        
        for term_idx, term in enumerate(term_names):
            semester = []
            current_courses = set()
            total_credits = 0
            
            # Create list of available courses for this term
            available = []
            
            for code in topo_order:
                course = self.catalog.courses.get(code)
                if not course:
                    continue
                
                # Skip if already completed
                if code in completed:
                    continue
                
                # Skip 0-credit courses
                if max(course.credits, default=0) == 0:
                    continue
                
                # Skip grad courses (5xx, 6xx)
                if code.startswith("CS___5") or code.startswith("CS___6"):
                    continue
                
                # Skip placeholder courses
                if code.startswith("CS___XXX") or code == "CS___499":
                    continue
                
                # Check if course is offered this term
                if not course.offerings.get(term, True):
                    continue
                
                # Intro course group logic - only allow one intro course total
                if code in intro_or_group and taken_intro:
                    continue
                
                # Check prerequisites
                rule = self.catalog.prereqs.get(code)
                if rule:
                    if not rule.strict_satisfied(completed):
                        continue
                    if not rule.concurrent_satisfied(completed, current_courses):
                        continue
                
                available.append((code, course))
            
            # Sort by course level (prioritize lower-numbered courses)
            available.sort(key=lambda x: (self.course_level(x[0]), x[0]))
            
            # Pack courses into semester, but enforce intro course limit
            intro_scheduled_this_term = False
            for code, course in available:
                credits = max(course.credits)
                
                # Double-check intro course logic
                if code in intro_or_group:
                    if taken_intro or intro_scheduled_this_term:
                        continue
                    intro_scheduled_this_term = True
                
                if total_credits + credits <= self.max_credits:
                    semester.append((code, credits))
                    current_courses.add(code)
                    total_credits += credits
                    completed.add(code)
                    
                    # Mark that we've taken an intro course
                    if code in intro_or_group:
                        taken_intro = True
                else:
                    break  # Stop if we can't fit any more courses
            
            if semester:
                plan.append(semester)
            else:
                # If no courses can be scheduled, we're done
                break
        
        return plan

