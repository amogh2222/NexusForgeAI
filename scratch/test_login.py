import requests

def test_login():
    url = "http://localhost:8000/api/v1/auth/login"
    payload = {
        "email": "demo@nexusforge.ai",
        "password": "password123"
    }
    try:
        response = requests.post(url, json=payload)
        print("Status Code:", response.status_code)
        print("Response JSON:", response.json())
    except Exception as e:
        print("Error connecting to backend:", e)

if __name__ == "__main__":
    test_login()
