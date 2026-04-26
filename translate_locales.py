import json
import os
import asyncio
from googletrans import Translator

async def main():
    translator = Translator()
    
    with open('frontend/src/locales/en.json', 'r') as f:
        en_data = json.load(f)
        
    langs = {
        'bn': 'bengali', 'te': 'telugu', 'mr': 'marathi', 
        'ta': 'tamil', 'ur': 'urdu', 'gu': 'gujarati', 
        'kn': 'kannada', 'ml': 'malayalam', 'or': 'odia', 
        'pa': 'punjabi', 'as': 'assamese'
    }
    
    def extract_texts(data, path=""):
        texts = []
        for k, v in data.items():
            if isinstance(v, dict):
                texts.extend(extract_texts(v, f"{path}{k}."))
            else:
                texts.append((f"{path}{k}", v))
        return texts

    def set_nested(d, key, val):
        parts = key.split('.')
        for p in parts[:-1]:
            d = d.setdefault(p, {})
        d[parts[-1]] = val

    en_texts = extract_texts(en_data)
    keys = [item[0] for item in en_texts]
    values = [item[1] for item in en_texts]
    
    for code, name in langs.items():
        print(f"Translating to {name} ({code})...")
        try:
            translations = await translator.translate(values, dest=code)
            out_data = {}
            for k, t in zip(keys, translations):
                set_nested(out_data, k, t.text)
                
            with open(f'frontend/src/locales/{code}.json', 'w') as f:
                json.dump(out_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Failed for {code}: {e}")
            # Fallback to english if API fails
            with open(f'frontend/src/locales/{code}.json', 'w') as f:
                json.dump(en_data, f, ensure_ascii=False, indent=4)

asyncio.run(main())
