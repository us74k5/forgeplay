import os
import subprocess
import requests
import shlex
import getpass

MODEL_SERVER = "https://ai.cudaforge.com/ask"
API_KEY = "5035443880"

WORKSPACE = "agent_workspace"
MAX_STEPS = 15

DANGEROUS_PATTERNS = [
    "rm -rf /",
    "rm -rf ~",
    "mkfs",
    "dd if=",
    ":(){",
    "shutdown",
    "reboot",
    "poweroff",
]

USERNAME = input("Enter your username: ").strip()
SUDO_PASSWORD = getpass.getpass("Enter sudo password (hidden): ")


def ask_model(prompt):
    r = requests.post(MODEL_SERVER, json={
        "key": API_KEY,
        "prompt": prompt,
        "username": USERNAME
    }, timeout=120)

    data = r.json()

    if "error" in data:
        raise RuntimeError(data["error"])

    return data["response"].strip()


def clean_command(text):
    text = text.strip()

    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part and not part.lower().startswith(("bash", "sh", "shell")):
                return part
        return parts[1].replace("bash", "").replace("sh", "").strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0] if lines else ""


def is_dangerous(command):
    lowered = command.lower()
    return any(pattern in lowered for pattern in DANGEROUS_PATTERNS)


def run_command(command):
    if is_dangerous(command):
        return f"Blocked dangerous command: {command}"

    try:
        if command.startswith("sudo"):
            command = command.replace("sudo", "sudo -S", 1)
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=WORKSPACE,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(SUDO_PASSWORD + "\n", timeout=60)
            output = stdout + stderr
        else:
            result = subprocess.run(
                command,
                shell=True,
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=60
            )
            output = result.stdout + result.stderr

        if not output.strip():
            output = "Command completed"

        return output

    except subprocess.TimeoutExpired:
        return "Command timed out"


def main():
    os.makedirs(WORKSPACE, exist_ok=True)

    print("\nLocal AI Agent")
    print(f"Workspace: {os.path.abspath(WORKSPACE)}\n")

    while True:
        task = input("Task> ").strip()

        if task.lower() in ["exit", "quit"]:
            break

        history = ""

        for step in range(1, MAX_STEPS + 1):
            prompt = f"""
You are a terminal coding agent.

Workspace:
{os.path.abspath(WORKSPACE)}

User task:
{task}

History:
{history}

Choose the next command.

Rules:
- One command only
- No explanation
- Use sudo if required
- If done, output DONE
"""

            try:
                command = clean_command(ask_model(prompt))
            except Exception as e:
                print("Model error:", e)
                break

            if command.upper() == "DONE":
                print("\nAgent finished.\n")
                break

            print(f"\n[{step}] $ {command}")

            output = run_command(command)
            print(output)

            history += f"\nCommand: {command}\nOutput:\n{output}\n"

        print("\nDone.\n")


if __name__ == "__main__":
    main()