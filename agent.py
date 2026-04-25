import requests
import subprocess
import re
import time

API = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:14b"
MAX_ITERATIONS = 8


def ask(prompt):
    try:
        response = requests.post(
            API,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2
                }
            },
            timeout=120
        )

        response.raise_for_status()

        return response.json()["response"].strip()

    except requests.exceptions.ConnectionError:
        print("\nOllama not running. Start it with:\n")
        print("ollama serve\n")
        raise SystemExit


def write_file(filename, content):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)


def run_code():
    result = subprocess.run(
        "python main.py",
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout + result.stderr


def install_package(pkg):
    print(f"\nInstalling missing package: {pkg}")
    subprocess.run(
        f"python -m pip install {pkg}",
        shell=True
    )


def extract_missing_modules(error_output):
    return re.findall(
        r"No module named '(.+?)'",
        error_output
    )


def extract_code(text):
    if "```" in text:
        parts = text.split("```")

        for part in parts:
            if "python" in part.lower():
                return part.replace(
                    "python",
                    ""
                ).strip()

        return parts[1].strip()

    return text.strip()


def clean_code(code):
    lines = code.splitlines()
    cleaned = []

    for line in lines:
        if line.strip().startswith("```"):
            continue
        cleaned.append(line)

    return "\n".join(cleaned).strip()


def generate_code(task):
    return ask(f"""
You are an elite software engineer.

Treat the user input as ONE complete software project request.

Generate complete executable Python code.

Rules:
- Output code only
- No markdown
- No explanations
- Include all imports
- Produce runnable code
- Do not break user request into shell commands
- Solve the whole project

Task:
{task}
""")


def fix_code(code, error):
    return ask(f"""
You are a senior debugging engineer.

Fix this Python code.

Return ONLY corrected code.

CODE:
{code}

ERROR:
{error}
""")


def get_multiline_task():
    print("Paste task. End with blank line:\n")

    lines = []

    while True:
        line = input()

        if line.strip() == "END":
            break

        lines.append(line)

    return "\n".join(lines)


def main():
    task = get_multiline_task()

    print("\nGenerating code...")
    code = generate_code(task)

    code = clean_code(
        extract_code(code)
    )

    write_file("main.py", code)

    for i in range(MAX_ITERATIONS):

        print(
            f"\nRunning code (attempt {i+1})..."
        )

        output = run_code()

        if (
            "Traceback" not in output and
            "Error" not in output
        ):
            print("\nSuccess:\n")
            print(output if output.strip()
                  else "Program ran successfully.")
            return

        print("\nDetected issue:\n")
        print(output)

        missing = extract_missing_modules(output)

        if missing:
            for pkg in set(missing):
                install_package(pkg)
            continue

        print("\nFixing code...")

        new_code = fix_code(
            code,
            output
        )

        new_code = clean_code(
            extract_code(new_code)
        )

        if new_code == code:
            print(
                "\nModel returned same code. Stopping."
            )
            break

        code = new_code

        write_file(
            "main.py",
            code
        )

        time.sleep(1)

    print(
        "\nMax attempts reached. Check main.py manually."
    )


if __name__ == "__main__":
    main()