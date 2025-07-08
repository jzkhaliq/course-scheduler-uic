# === catalog.py ===
from collections import defaultdict
from course import Course
from prerequisites import PrerequisiteRule

class CourseCatalog:
    def __init__(self):
        self.courses = {}  # code -> Course
        self.prereqs = defaultdict(PrerequisiteRule)
        self.graph = defaultdict(list)
        self.indegree = defaultdict(int)

    def load_credits(self, path):
        with open(path) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) != 2:
                    continue
                code, credit_str = parts
                if "," in credit_str:
                    credits = [int(c) for c in credit_str.split(",")]
                else:
                    credits = [int(credit_str)]
                if code not in self.courses:
                    self.courses[code] = Course(code, credits, {"fall": True, "spring": True})
                else:
                    self.courses[code].credits = credits

    def load_offerings(self, path):
        with open(path) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) != 3:
                    continue
                code, fall, spring = parts
                if code not in self.courses:
                    self.courses[code] = Course(code, [3], {})
                self.courses[code].offerings = {"fall": bool(int(fall)), "spring": bool(int(spring))}

    def load_prereqs(self, path):
        temp = defaultdict(lambda: {"strict": defaultdict(list), "concurrent": defaultdict(list)})

        with open(path) as f:
            for i, line in enumerate(f):
                parts = line.strip().split("\t")
                if len(parts) != 3:
                    continue
                prereq, target, relation = parts
                relation = int(relation)
                if relation == -1:
                    temp[target]["strict"][i].append(prereq)
                else:
                    temp[target]["concurrent"][i].append(prereq)

        for target, groups in temp.items():
            rule = self.prereqs[target]
            for line_prereqs in groups["strict"].values():
                rule.strict.append(line_prereqs)
                for prereq in line_prereqs:
                    self.graph[prereq].append(target)
                    self.indegree[target] += 1
            for line_prereqs in groups["concurrent"].values():
                rule.concurrent.append(line_prereqs)

    def load_all_data(self, prereq_path, offerings_path, credits_path):
        self.load_credits(credits_path)
        self.load_offerings(offerings_path)
        self.load_prereqs(prereq_path)
