# === course.py ===
class Course:
    def __init__(self, code, credits, offerings):
        self.code = code
        self.credits = credits  # list of int
        self.offerings = offerings  # {"fall": bool, "spring": bool}
