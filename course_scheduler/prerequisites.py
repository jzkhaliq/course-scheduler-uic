# === prerequisites.py ===
class PrerequisiteRule:
    def __init__(self):
        self.strict = []      # List[List[str]]: OR groups
        self.concurrent = []  # List[List[str]]

    def strict_satisfied(self, completed):
        for group in self.strict:
            if not any(course in completed for course in group):
                return False
        return True

    def concurrent_satisfied(self, completed, current):
        for group in self.concurrent:
            if not any(course in completed or course in current for course in group):
                return False
        return True