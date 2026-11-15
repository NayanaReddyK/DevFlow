import requests

url = "http://127.0.0.1:8000/api/v1/auth/login/"

email = input("Email: ")
password = input("Password: ")

response = requests.post(
    url,
    json={
        "email": email,
        "password": password
    }
)

print("Status:", response.status_code)

if response.status_code == 200:
    print("Email login successful!")
    print("Access token received:", "access" in response.json())
    print("Refresh token received:", "refresh" in response.json())
else:
    print("Response:", response.json())