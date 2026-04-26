import json
import os
import concurrent.futures
from deep_translator import GoogleTranslator

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def get_missing(en_dict, target_dict):
    missing_keys = []
    missing_values = []
    
    def walk(e, t, path=""):
        for k, v in e.items():
            current_path = f"{path}.{k}" if path else k
            if isinstance(v, dict):
                t_sub = t.get(k, {})
                if not isinstance(t_sub, dict): t_sub = {}
                walk(v, t_sub, current_path)
            else:
                if k not in t or t[k] == v: # If it's literally the English string, translate it
                    missing_keys.append(current_path)
                    missing_values.append(v)
    walk(en_dict, target_dict)
    return missing_keys, missing_values

def set_nested(d, key, val):
    parts = key.split('.')
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = val

lang = 'ta'

with open('frontend/src/locales/en.json', 'r') as f:
    en_data = json.load(f)

file_path = f'frontend/src/locales/{lang}.json'
if os.path.exists(file_path):
    with open(file_path, 'r') as f:
        target_data = json.load(f)
else:
    target_data = {}

missing_keys, missing_values = get_missing(en_data, target_data)

if not missing_keys:
    print("OK")
    exit()

print(f"[{lang}] Translating {len(missing_keys)} missing items...")

translated_flat = {}

def process_chunk(args):
    idx, chunk = args
    translator = GoogleTranslator(source='en', target=lang)
    try:
        return idx, translator.translate_batch(chunk)
    except Exception as e:
        print(f"Error in batch {idx}: {e}")
        return idx, chunk

chunks = list(chunk_list(missing_values, 50))
chunk_args = [(i, c) for i, c in enumerate(chunks)]

with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
    results = list(executor.map(process_chunk, chunk_args))

# Reassemble in order
results.sort(key=lambda x: x[0])
all_translated = []
for idx, res in results:
    all_translated.extend(res)

for k, v in zip(missing_keys, all_translated):
    set_nested(target_data, k, v)

with open(file_path, 'w') as f:
    json.dump(target_data, f, ensure_ascii=False, indent=4)

print("Saved!")
