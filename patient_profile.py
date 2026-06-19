import json
import os

PROFILE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile.json")

def save_profile(name, age, gender, blood_pressure, known_conditions):
    profile = {
        "name": name,
        "age": age,
        "gender": gender,
        "blood_pressure": blood_pressure,
        "known_conditions": known_conditions
    }
    with open(PROFILE_FILE, "w") as f:
        json.dump(profile, f)

def load_profile():
    if os.path.exists(PROFILE_FILE):
        with open(PROFILE_FILE, "r") as f:
            return json.load(f)
    return {
        "name": "",
        "age": "",
        "gender": "",
        "blood_pressure": "",
        "known_conditions": ""
    }