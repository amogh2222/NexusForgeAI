import requests
import time
import json
import uuid

API_URL = "http://localhost:8000/api/v1"

def p(msg):
    print(f"[*] {msg}")

def fail(msg):
    print(f"[!] FAILED: {msg}")
    exit(1)

# 1. Register
p("Registering user...")
email = f"test_{uuid.uuid4()}@example.com"
password = "password123"
r = requests.post(f"{API_URL}/auth/register", json={"email": email, "password": password, "name": "Test User", "username": f"user_{uuid.uuid4().hex[:8]}"})
if r.status_code not in (200, 201): fail(f"Register failed: {r.text}")
token = r.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

# 2. Create Project
p("Creating project...")
r = requests.post(f"{API_URL}/projects/", json={"name": "Test Project"}, headers=headers)
if r.status_code not in (200, 201): fail(f"Project creation failed: {r.text}")
project_id = r.json()["id"]

# 3. Add Repo
p("Adding repository...")
repo_url = "https://github.com/amogh2222/NexusForgeAI"
r = requests.post(f"{API_URL}/repos/github", json={"project_id": project_id, "url": repo_url}, headers=headers)
if r.status_code not in (200, 201): fail(f"Repo add failed: {r.text}")
repo_id = r.json()["id"]

# 4. Poll Indexing
p("Polling indexing status...")
for _ in range(60):
    r = requests.get(f"{API_URL}/repos/{repo_id}", headers=headers)
    status = r.json().get("indexed_status")
    p(f"Status: {status}")
    if status == "indexed":
        p("Indexing complete!")
        break
    if status == "failed":
        fail("Indexing failed!")
    time.sleep(2)
else:
    fail("Indexing timed out!")

p("ALL CORE TESTS PASSED.")
