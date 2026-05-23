import requests

def test_clone():
    # 1. Login to get token
    login_url = "http://localhost:8000/api/v1/auth/login"
    login_payload = {
        "email": "demo@nexusforge.ai",
        "password": "password123"
    }
    try:
        response = requests.post(login_url, json=login_payload)
        token = response.json().get("access_token")
        print("Logged in. Token acquired.")
    except Exception as e:
        print("Login failed:", e)
        return

    # 2. Call github clone endpoint
    url = "http://localhost:8000/api/v1/repos/github"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "project_id": "00000000-0000-0000-0000-000000000000",
        "url": "https://github.com/amogh2222/atomquest-nexagoals",
        "branch": "main"
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        print("Status Code:", response.status_code)
        print("Response JSON:", response.json())
    except Exception as e:
        print("Error connecting to backend:", e)

if __name__ == "__main__":
    test_clone()
