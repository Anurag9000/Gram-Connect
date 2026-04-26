import json

with open('frontend/src/locales/en.json', 'r') as f:
    data = json.load(f)

if 'map' not in data:
    data['map'] = {}

data['map'].update({
    "pending": "Pending",
    "in_progress": "In Progress",
    "resolved": "Resolved",
    "all_problems": "All Problems",
    "all_cases": "All cases",
    "showing": "Showing",
    "problem": "problem",
    "in": "in"
})

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(data, f, indent=4)
