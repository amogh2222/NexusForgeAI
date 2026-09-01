import requests
import json
import time
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def print_result(step, response):
    print(f"--- {step} ---")
    print(f"Status: {response.status_code}")
    try:
        print(response.json())
    except:
        print(response.text)
    print("\n")

# Use unique email to avoid 400 conflict
email = f"test_{uuid.uuid4().hex[:6]}@example.com"

# 1. Register & Login
print("1. Testing Auth...")
auth_data_register = {"username": email, "email": email, "password": "password123"}
res = requests.post(f"{BASE_URL}/auth/register", json=auth_data_register)
if res.status_code not in [200, 201, 400]:
    print_result("Register", res)
    
auth_data_login = {"email": email, "password": "password123"}
res = requests.post(f"{BASE_URL}/auth/login", json=auth_data_login)
if res.status_code != 200:
    print_result("Login Failed", res)
    exit(1)
token = res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Auth Success.")

# 2. Create Project & Repo
print("2. Testing Projects...")
res = requests.post(f"{BASE_URL}/projects/", headers=headers, json={"name": "Test Project", "description": "Test"})
if res.status_code not in [200, 201]:
    print_result("Create Project Failed", res)
    exit(1)
project_id = res.json()["id"]
print(f"Project Created: {project_id}")

# 3. Execution Sandbox
print("3. Testing Sandbox...")
code_payload = {
    "project_id": project_id,
    "runtime": "python",
    "code": "print('Hello from Sandbox!')"
}
res = requests.post(f"{BASE_URL}/executions/", headers=headers, json=code_payload)
print_result("Sandbox Execution", res)


# 4. Intelligence Design
print("4. Testing Intelligence Design...")
design_payload = {
    "project_id": project_id,
    "prompt": "Design a scalable chat application"
}
res = requests.post(f"{BASE_URL}/intelligence/design", headers=headers, json=design_payload)
print_result("Intelligence Design", res)
