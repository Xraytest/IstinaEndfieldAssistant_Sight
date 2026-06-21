"""Check available models from cherryin.ai vendor API"""
import requests, json

API_KEY = "sk-SHYG0HNKhAEPXbEHOdlLcggKXYlyEGJyolvGjh0T2r5FQOst"
BASE_URL = "https://open.cherryin.ai"

# List all models
r = requests.get(f"{BASE_URL}/v1/models", headers={"Authorization": f"Bearer {API_KEY}"})
if r.status_code == 200:
    data = r.json()
    models = data.get("data", [])
    print(f"Total models: {len(models)}")
    for m in sorted(models, key=lambda x: x.get("id", "")):
        mid = m.get("id", "")
        owner = m.get("owned_by", "")
        print(f"  {mid} ({owner})")
else:
    print(f"Error {r.status_code}: {r.text[:500]}")

# Check specific model IDs
targets = ["qwen3.6-plus", "qwen3.5-395b", "qwen3.5-35b", "qwen3", "vision"]
print(f"\n--- Searching for key models ---")
for t in targets:
    r = requests.get(f"{BASE_URL}/v1/models", headers={"Authorization": f"Bearer {API_KEY}"})
    if r.status_code == 200:
        data = r.json()
        for m in data.get("data", []):
            if t.lower() in m.get("id", "").lower():
                print(f"  Found: {m['id']}")
    else:
        print(f"  Query failed for {t}")
        break
