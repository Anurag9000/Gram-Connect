import json

with open('frontend/src/locales/en.json', 'r') as f:
    data = json.load(f)

if 'submit' not in data:
    data['submit'] = {}

if 'severity' not in data['submit']:
    data['submit']['severity'] = {}

data['submit']['severity'].update({
    "auto_label": "Auto-detect",
    "auto_desc": "Inferred from your description",
    "low_label": "Low",
    "low_desc": "Routine, no immediate risk",
    "normal_label": "Normal",
    "normal_desc": "Needs attention within days",
    "high_label": "High",
    "high_desc": "Urgent / emergency"
})

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(data, f, indent=4)
