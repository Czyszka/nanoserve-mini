from __future__ import annotations

import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

COMMANDS: dict[str, list[str]] = {
    "git_version": ["git", "--version"],
    "python_version": ["python", "--version"],
    "uv_version": ["uv", "--version"],
    "rg_version": ["rg", "--version"],
    "uname": ["uname", "-a"],
    "os_release": ["cat", "/etc/os-release"],
    "lscpu": ["lscpu"],
    "memory": ["free", "-h"],
    "disk": ["df", "-h"],
    "nvidia_smi": ["nvidia-smi"],
    "nvcc_version": ["nvcc", "--version"],
    "nvidia_smi_query": [
        "nvidia-smi",
        "--query-gpu=index,name,memory.total,driver_version",
        "--format=csv",
    ],
    "docker_version": ["docker", "--version"],
    "docker_compose_version": ["docker", "compose", "version"],
}


def run_command(command: list[str]) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except FileNotFoundError as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": f"command not found: {exc}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command,
            "returncode": None,
            "stdout": exc.stdout or "",
            "stderr": f"timeout: {exc}",
        }


def main() -> None:
    output_path = Path("results/raw/server_env_snapshot.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {
        "timestamp": datetime.now(UTC).isoformat(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "commands": {
            name: run_command(command)
            for name, command in COMMANDS.items()
        },
    }

    output_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    main()
