import json
import os
import asyncio
from googletrans import Translator

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

async def translate_lang(lang_code, lang_name, en_data):
    translator = Translator()
    file_path = f'frontend/src/locales/{lang_code}.json'
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            target_data = json.load(f)
    else:
        target_data = {}

    target_seed = target_data.get('seed', {})
    en_seed = en_data.get('seed', {})
    
    missing_keys = []
    missing_values = []
    
    for k, v in en_seed.items():
        if k not in target_seed:
            missing_keys.append(k)
            missing_values.append(str(v))
            
    if not missing_keys:
        print(f"[{lang_code}] OK")
        return

    print(f"[{lang_code}] Translating {len(missing_keys)} missing seeds...")
    
    translated_values = []
    chunks = list(chunk_list(missing_values, 100))
    
    for i, batch in enumerate(chunks):
        try:
            # Sleep briefly to avoid HTTP 429
            await asyncio.sleep(0.5)
            translations = await translator.translate(batch, dest=lang_code)
            translated_values.extend([t.text for t in translations])
            print(f"[{lang_code}] Batch {i+1}/{len(chunks)} done.")
        except Exception as e:
            print(f"[{lang_code}] Batch {i+1} failed: {e}. Falling back.")
            translated_values.extend(batch)

    for k, v in zip(missing_keys, translated_values):
        target_seed[k] = v
        
    target_data['seed'] = target_seed
    
    with open(file_path, 'w') as f:
        json.dump(target_data, f, ensure_ascii=False, indent=4)
    print(f"[{lang_code}] Saved!")

async def main():
    with open('frontend/src/locales/en.json', 'r') as f:
        en_data = json.load(f)
        
    langs = {
        'ta': 'tamil', 'bn': 'bengali', 'hi': 'hindi', 'te': 'telugu', 'mr': 'marathi', 
        'ur': 'urdu', 'gu': 'gujarati', 'kn': 'kannada', 'ml': 'malayalam', 'or': 'odia', 
        'pa': 'punjabi', 'as': 'assamese'
    }
    
    # Priority: ta, bn first
    await translate_lang('ta', 'tamil', en_data)
    await translate_lang('bn', 'bengali', en_data)
    
    # Rest in parallel
    tasks = []
    for code, name in langs.items():
        if code not in ['ta', 'bn']:
            tasks.append(translate_lang(code, name, en_data))
            
    await asyncio.gather(*tasks)
    print("All done!")

asyncio.run(main())
