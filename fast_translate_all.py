import json
import os
import concurrent.futures
import time
from deep_translator import GoogleTranslator

langs = ['gu', 'hi', 'bn', 'ta', 'te', 'mr', 'kn', 'ur', 'ml', 'or', 'pa', 'as']

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
                if k not in t or not t[k] or t[k] == v:
                    if len(str(v)) > 0:
                        missing_keys.append(current_path)
                        missing_values.append(v)
    walk(en_dict, target_dict)
    return missing_keys, missing_values

def set_nested(d, key, val):
    parts = key.split('.')
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = val

def translate_lang(lang):
    print(f"Starting {lang}...")
    file_path = f'frontend/src/locales/{lang}.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            target_data = json.load(f)
    else:
        target_data = {}

    with open('frontend/src/locales/en.json', 'r') as f:
        en_data = json.load(f)

    missing_keys, missing_values = get_missing(en_data, target_data)

    if not missing_keys:
        print(f"[{lang}] No missing strings.")
        return

    print(f"[{lang}] Translating {len(missing_keys)} items in batches...")
    
    translator = GoogleTranslator(source='en', target=lang)
    
    chunks = list(chunk_list(list(zip(missing_keys, missing_values)), 50))
    
    def process_batch(batch):
        batch_keys, batch_values = zip(*batch)
        try:
            time.sleep(0.1)
            translated = translator.translate_batch(list(batch_values))
            return list(zip(batch_keys, translated))
        except Exception:
            return list(zip(batch_keys, batch_values))

    count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for batch_results in executor.map(process_batch, chunks):
            for k, v in batch_results:
                set_nested(target_data, k, v)
            count += 1
            if count % 10 == 0:
                with open(file_path, 'w') as f:
                    json.dump(target_data, f, ensure_ascii=False, indent=4)
                print(f"[{lang}] Saved progress ({count * 50}/{len(missing_keys)})")

    with open(file_path, 'w') as f:
        json.dump(target_data, f, ensure_ascii=False, indent=4)
    print(f"[{lang}] Fully Saved!")

# Gujarati first
translate_lang('gu')

# Parallel others
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(translate_lang, langs[1:])

print("All done!")
