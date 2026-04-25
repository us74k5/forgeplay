from fastapi import FastAPI
import subprocess
import requests
import re
import os

app = FastAPI()

OLLAMA_API = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:14b"


def ask(prompt):
    r = requests.post(OLLAMA_API, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2}
    })
    return r.json()["response"].strip()


def clean_code(text):
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            if "python" in part.lower():
                return part.replace("python", "").strip()
        return parts[1].strip()
    return text.strip()


def run_code():
    result = subprocess.run(
        "python main.py",
        shell=True,
        capture_output=True,
        text=True,
        timeout=20
    )
    return result.stdout + result.stderr


def install_package(pkg):
    subprocess.run(f"python -m pip install {pkg}", shell=True)


def extract_missing(error):
    return list(set(re.findall(r"No module named '(.+?)'", error)))


def is_success(output):
    if "Traceback" in output:
        return False
    if "Error" in output and "No module named" not in output:
        return False
    return True


@app.post("/run-task")
def run_task(data: dict):
    task = data.get("task", "")

    os.makedirs("sandbox", exist_ok=True)
    os.chdir("sandbox")

    code = ask(f"""
You are a senior software engineer.

Write complete Python code.
- No markdown
- No backticks
- No explanations
- Only valid Python

Task:
{task}
""")

    code = clean_code(code)

    with open("main.py", "w", encoding="utf-8") as f:
        f.write(code)

    for _ in range(6):
        output = run_code()

        if is_success(output):
            return {
                "status": "success",
                "output": output if output.strip() else "Program ran successfully"
            }

        missing = extract_missing(output)
        if missing:
            for pkg in missing:
                install_package(pkg)
            continue

        code = ask(f"""
Fix this Python code.

Rules:
- Only output code
- No markdown
- No explanations

CODE:
{code}

ERROR:
{output}
""")

        code = clean_code(code)

        with open("main.py", "w", encoding="utf-8") as f:
            f.write(code)

    return {"status": "failed", "output": output}