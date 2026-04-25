from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import requests
import json
import os
from datetime import datetime

app = FastAPI()

OLLAMA_API = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:14b"
API_KEY = "your-secret"

LOG_FILE = "prompt_logs.jsonl"


def log_event(data):
    entry = {
        "time": datetime.utcnow().isoformat(),
        "user": data.get("username", "unknown"),
        "prompt": data.get("prompt", "")
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@app.post("/ask")
async def ask_model(request: Request):
    data = await request.json()

    if data.get("key") != API_KEY:
        return {"error": "unauthorized"}

    prompt = data.get("prompt", "")

    log_event(data)

    r = requests.post(OLLAMA_API, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    })

    return {"response": r.json()["response"]}


@app.get("/history")
def get_history():
    entries = []

    if not os.path.exists(LOG_FILE):
        return entries

    with open(LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except:
                continue

    return entries[-100:]


@app.get("/history-view", response_class=HTMLResponse)
def history_view():
    return """
    <html>
    <head>
        <title>Prompt History</title>
        <style>
            body { font-family: monospace; background: #111; color: #eee; }
            .entry { margin-bottom: 15px; padding: 10px; border-bottom: 1px solid #333; }
            .user { color: #6cf; }
            .time { color: #999; }
        </style>
    </head>
    <body>
        <h2>Prompt History</h2>
        <div id="log"></div>

        <script>
            async function load() {
                const res = await fetch('/history');
                const data = await res.json();

                const container = document.getElementById('log');
                container.innerHTML = "";

                data.reverse().forEach(entry => {
                    const div = document.createElement('div');
                    div.className = 'entry';

                    div.innerHTML = `
                        <div class="user">User: ${entry.user}</div>
                        <div class="time">${entry.time}</div>
                        <div>${entry.prompt}</div>
                    `;

                    container.appendChild(div);
                });
            }

            load();
            setInterval(load, 5000);
        </script>
    </body>
    </html>
    """