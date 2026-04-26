import json
import os
import sys
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def get_missing_keys(en_dict, target_dict):
    missing = {}
    for k, v in en_dict.items():
        if isinstance(v, dict):
            if k not in target_dict or not isinstance(target_dict[k], dict):
                missing[k] = v
            else:
                sub_missing = get_missing_keys(v, target_dict[k])
                if sub_missing:
                    missing[k] = sub_missing
        else:
            if k not in target_dict:
                missing[k] = v
    return missing

def flatten_dict(d, parent_key='', sep='|||'):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def unflatten_dict(d, sep='|||'):
    result_dict = {}
    for k, v in d.items():
        parts = k.split(sep)
        d_ref = result_dict
        for part in parts[:-1]:
            if part not in d_ref:
                d_ref[part] = {}
            d_ref = d_ref[part]
        d_ref[parts[-1]] = v
    return result_dict

def merge_dicts(base, overlay):
    for k, v in overlay.items():
        if isinstance(v, dict):
            base[k] = merge_dicts(base.get(k, {}), v)
        else:
            base[k] = v
    return base

with open('frontend/src/locales/en.json', 'r') as f:
    en_data = json.load(f)

langs = ['ta', 'bn', 'kn', 'hi', 'te', 'mr', 'ur', 'gu', 'ml', 'or', 'pa', 'as']

def translate_lang(lang):
    file_path = f'frontend/src/locales/{lang}.json'
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            target_data = json.load(f)
    else:
        target_data = {}

    missing = get_missing_keys(en_data, target_data)
    if not missing:
        print(f"[{lang}] OK")
        return

    flat_missing = flatten_dict(missing)
    keys = list(flat_missing.keys())
    values = [str(flat_missing[k]) for k in keys]
    
    print(f"[{lang}] Translating {len(keys)} items in batches...")
    
    translated_values = []
    translator = GoogleTranslator(source='en', target=lang)
    
    chunks = list(chunk_list(values, 100)) # Larger chunk
    for i, batch in enumerate(chunks):
        try:
            res = translator.translate_batch(batch)
            translated_values.extend(res)
            print(f"[{lang}] Batch {i+1}/{len(chunks)} done.")
        except Exception as e:
            print(f"[{lang}] Batch {i+1} failed: {e}. Falling back.")
            translated_values.extend(batch)

    translated_flat = {keys[i]: translated_values[i] for i in range(len(keys))}
    translated_nested = unflatten_dict(translated_flat)
    
    updated_data = merge_dicts(target_data, translated_nested)
    
    with open(file_path, 'w') as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=4)
    print(f"[{lang}] Saved!")

# Only do 'ta' first synchronously to fix the user's issue immediately
translate_lang('ta')

# Then do the rest in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    executor.map(translate_lang, langs[1:])
    
print("All done!")
