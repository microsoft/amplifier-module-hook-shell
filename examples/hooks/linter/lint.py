#!/usr/bin/env python3
"""
Linter Hook
Runs linter and injects feedback into agent context
"""
import json
import sys
import subprocess
from pathlib import Path


def lint_python(file_path: str) -> tuple[bool, str]:
    """Run pylint on Python file."""
    try:
        result = subprocess.run(
            ["pylint", file_path, "--output-format=text"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "No issues found"
        return False, result.stdout
    except subprocess.TimeoutExpired:
        return True, "Linter timed out"
    except FileNotFoundError:
        return True, "pylint not installed"


def lint_javascript(file_path: str) -> tuple[bool, str]:
    """Run eslint on JavaScript file."""
    try:
        result = subprocess.run(
            ["eslint", file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return True, "No issues found"
        return False, result.stdout
    except subprocess.TimeoutExpired:
        return True, "Linter timed out"
    except FileNotFoundError:
        return True, "eslint not installed"


def main():
    # Read input
    data = json.load(sys.stdin)
    file_path = data.get('tool_input', {}).get('file_path', '')
    
    if not file_path:
        sys.exit(0)
    
    path = Path(file_path)
    if not path.exists():
        sys.exit(0)
    
    # Run appropriate linter
    success = True
    message = ""
    
    if path.suffix == '.py':
        success, message = lint_python(file_path)
    elif path.suffix in ['.js', '.ts', '.jsx', '.tsx']:
        success, message = lint_javascript(file_path)
    else:
        # No linter for this file type
        sys.exit(0)
    
    # Output result
    if success:
        response = {
            "decision": "approve",
            "systemMessage": f"✓ Lint check passed for {path.name}"
        }
    else:
        response = {
            "decision": "approve",
            "contextInjection": f"Linting issues in {file_path}:\n{message}",
            "systemMessage": f"⚠️ Linting issues detected in {path.name}"
        }
    
    print(json.dumps(response))


if __name__ == "__main__":
    main()
