# config.py

import json

def load_major_config(path):
    with open(path) as f:
        return json.load(f)
