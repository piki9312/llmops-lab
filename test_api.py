"""Quick API test script."""
import httpx

url = "http://localhost:8000/generate"
payload = {
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "max_output_tokens": 50
}

try:
    response = httpx.post(url, json=payload, timeout=30)
    print(f"Status: {response.status_code}")
    print(f"Response:\n{response.json()}")
except Exception as e:
    print(f"Error: {e}")
