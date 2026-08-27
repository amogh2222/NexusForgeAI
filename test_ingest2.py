import requests, sys, time, uuid

API_URL = "http://localhost:8000/api/v1"
repo_url = "https://github.com/amogh2222/DellPartVisionAI"

email = f"test_{uuid.uuid4().hex[:8]}@example.com"
print(f"Registering user {email}...")
res = requests.post(f"{API_URL}/auth/register", json={
    "email": email,
    "username": "testuser_" + uuid.uuid4().hex[:4],
    "password": "password123",
    "full_name": "Test"
})
if res.status_code not in [200, 201]:
    print("Registration failed:", res.text)
    sys.exit(1)

token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

print("Creating project...")
res = requests.post(f"{API_URL}/projects/", json={"name": "Test Project", "description": "Test"}, headers=headers)
if res.status_code not in [200, 201]:
    print("Project creation failed:", res.text)
    sys.exit(1)
project_id = res.json()["id"]

print("Connecting GitHub repository...")
res = requests.post(f"{API_URL}/repos/github", json={"project_id": project_id, "url": repo_url, "branch": "main"}, headers=headers)
if res.status_code not in [200, 201]:
    print("Repo connect failed:", res.text)
    sys.exit(1)

repo_id = res.json()["id"]
print(f"Repo added with ID: {repo_id}. Polling status...")

for i in range(60):
    res = requests.get(f"{API_URL}/projects/{project_id}/repos", headers=headers)
    repos = res.json()
    print("Repos response:", repos)
    if isinstance(repos, list) and len(repos) > 0:
        repo = repos[0]
        print(f"Status: {repo['indexed_status']}, Progress: {repo['indexing_progress']}%")
        if repo["indexed_status"] == "COMPLETED":
            print("Successfully indexed!")
            sys.exit(0)
        elif repo["indexed_status"] == "FAILED":
            print("Indexing failed!")
            sys.exit(1)
    time.sleep(2)

print("Timeout waiting for indexing to complete.")
sys.exit(1)
