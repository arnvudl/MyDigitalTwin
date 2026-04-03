import json, os

files = [
    r'C:\Users\arnau\Documents\MyDigitalTwin\data\raw\INSTAGRAM\preferences\your_topics\recommended_topics.json',
    r'C:\Users\arnau\Documents\MyDigitalTwin\data\raw\X\data\personalization.js',
]

for path in files:
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            raw = f.read()
        if raw.strip().startswith('window.'):
            raw = raw[raw.index('=') + 1:].strip()
        data = json.loads(raw)
        print(f'\n=== {os.path.basename(path)} ===')
        print(str(data)[:1000])
    else:
        print(f'INTROUVABLE: {path}')