import csv
import json
import os

seeds = {}

def add_seed(text):
    if not text: return
    text = str(text).strip()
    if text:
        seeds[text] = text

# Parse backend/proposals_2.csv
with open('backend/proposals_2.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        add_seed(row.get('title'))
        add_seed(row.get('description'))
        add_seed(row.get('village_name'))
        add_seed(row.get('village_address'))
        add_seed(row.get('location'))

# Parse backend/people_2.csv
with open('backend/people_2.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        add_seed(row.get('name'))
        add_seed(row.get('full_name'))
        # Skills
        skills = row.get('skills', '')
        if '[' in skills:
            try:
                for s in json.loads(skills):
                    add_seed(s)
            except:
                pass
        else:
            for s in skills.split('|'):
                add_seed(s)

with open('frontend/src/locales/en.json', 'r') as f:
    en_data = json.load(f)

if 'seed' not in en_data:
    en_data['seed'] = {}

en_data['seed'].update(seeds)

with open('frontend/src/locales/en.json', 'w') as f:
    json.dump(en_data, f, indent=4)

print(f"Extracted {len(seeds)} unique seed strings.")
