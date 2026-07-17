"""Conservative wrapper around the local OpenSSH client."""

from __future__ import annotations

import re
import shlex
import subprocess
from typing import Optional

_HOST_RE = re.compile(r"^[A-Za-z0-9._:-]+$")
_USER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class SSHHelper:
    def __init__(
        self,
        host: str,
        user: str = "root",
        ssh_key: Optional[str] = None,
        port: int = 22,
    ):
        if not _HOST_RE.fullmatch(host or ""):
            raise ValueError("invalid SSH host")
        if not _USER_RE.fullmatch(user or ""):
            raise ValueError("invalid SSH user")
        if not 1 <= int(port) <= 65535:
            raise ValueError("invalid SSH port")
        self.host = host
        self.user = user
        self.ssh_key = ssh_key
        self.port = int(port)

    def _ssh_cmd(self) -> list[str]:
        command = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-o",
            "ConnectTimeout=10",
        ]
        if self.ssh_key:
            command.extend(["-i", str(self.ssh_key)])
        if self.port != 22:
            command.extend(["-p", str(self.port)])
        command.append(f"{self.user}@{self.host}")
        return command

    def run(self, command: str, timeout: int = 120) -> dict:
        try:
            result = subprocess.run(
                self._ssh_cmd() + [command],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": "Timeout", "returncode": -1}
        except FileNotFoundError:
            return {"ok": False, "stdout": "", "stderr": "ssh not found", "returncode": -1}

    def test_connection(self) -> dict:
        return self.run("printf 'SSH OK\\n' && hostname", timeout=15)

    def file_exists(self, path: str) -> bool:
        result = self.run(f"test -f {shlex.quote(path)} && printf 'yes\\n'", timeout=10)
        return result.get("stdout", "").strip() == "yes"

    def command_exists(self, command: str) -> bool:
        if not re.fullmatch(r"[A-Za-z0-9._+-]+", command or ""):
            raise ValueError("invalid command name")
        result = self.run(f"command -v {shlex.quote(command)} >/dev/null", timeout=10)
        return bool(result.get("ok"))
