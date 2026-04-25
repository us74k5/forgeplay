import requests

response = requests.post("http://localhost:11434/api/generate", json={
    "model": "qwen2.5-coder:14b",
    "prompt": "Write a Python function that reads a file and prints its contents",
    "stream": False
})

print(response.json()["response"])