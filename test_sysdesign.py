import requests

API_URL = "http://localhost:8000/api/v1"
project_id = "0dfeea1a-599b-498c-82f2-06a1bbe84202" # Dummy ID

print("Testing System Design Generator (without streaming)...")
r = requests.post(f"{API_URL}/intelligence/design", json={"project_id": project_id, "scale": "10M_users"})
if r.status_code == 200:
    print("Success! Executive Summary:")
    print(r.json().get("executive_summary")[:200])
else:
    print(f"Failed: {r.status_code}")
    print(r.text)
