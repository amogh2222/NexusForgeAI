import requests
import json

API_URL = "http://localhost:8000/api/v1"
project_id = "0dfeea1a-599b-498c-82f2-06a1bbe84202"

print("Testing System Design Generator (streaming)...")
with requests.post(f"{API_URL}/intelligence/design", json={"project_id": project_id, "scale": "10M_users", "stream": True}, stream=True) as r:
    for chunk in r.iter_content(chunk_size=None):
        if chunk:
            print(chunk.decode('utf-8'), end='')
print("\nDone.")
