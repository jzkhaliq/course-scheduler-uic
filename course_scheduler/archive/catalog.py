# === catalog.py ===
from collections import defaultdict
from course import Course
from course_scheduler.archive.prerequisites import PrerequisiteRule

class CourseCatalog:
    def __init__(self):
        self.courses = {}  # code -> Course
        self.prereqs = defaultdict(PrerequisiteRule)
        self.graph = defaultdict(list)
        self.reverse_graph = defaultdict(list)
        self.indegree = defaultdict(int)
        self.timings = defaultdict(list)


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
        # Group prerequisites by target course and relation type
        temp = defaultdict(lambda: {"strict": [], "concurrent": []})

        with open(path) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) != 3:
                    continue
                prereq, target, relation = parts
                relation = int(relation)
                if relation == -1:
                    temp[target]["strict"].append(prereq)
                else:
                    temp[target]["concurrent"].append(prereq)

        # Process grouped prerequisites
        for target, groups in temp.items():
            rule = self.prereqs[target]
            
            # For strict prerequisites, group all with same relation as one OR group
            if groups["strict"]:
                rule.strict.append(groups["strict"])
                # Build graph edges for topological sort
                for prereq in groups["strict"]:
                    self.graph[prereq].append(target)
                    self.reverse_graph[target].append(prereq)
                # Only increment indegree once per OR group
                self.indegree[target] += 1
            
            # For concurrent prerequisites, group all as one OR group
            if groups["concurrent"]:
                rule.concurrent.append(groups["concurrent"])

    def load_all_data(self, prereq_path, offerings_path, credits_path, timings_path=None):
        self.load_credits(credits_path)
        self.load_offerings(offerings_path)
        self.load_prereqs(prereq_path)
        if timings_path:
            self.load_timings(timings_path)


    def load_timings(self, path):
        self.timings = defaultdict(list)
        with open(path) as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) < 2:
                    continue
                course_key = parts[0]
                num_sessions = int(parts[1])
                for i in range(num_sessions):
                    crn = parts[2 + i * 3]
                    start = int(parts[3 + i * 3])
                    end = int(parts[4 + i * 3])
                    self.timings[course_key.split("_")[0]].append((start, end))  # key like CS___141

