"""Install a pinned n8n container on an operator-managed Docker host."""

from __future__ import annotations

import time
from typing import Optional

from n8nManager.setup.ssh_helper import SSHHelper

N8N_IMAGE = "docker.n8n.io/n8nio/n8n:2.26.8"


class N8nInstaller:
    def __init__(
        self,
        host: str,
        user: str = "root",
        ssh_key: Optional[str] = None,
        port: int = 22,
        n8n_port: int = 5678,
    ):
        if not 1 <= int(n8n_port) <= 65535:
            raise ValueError("invalid n8n port")
        self.ssh = SSHHelper(host, user, ssh_key, port)
        self.host = host
        self.n8n_port = int(n8n_port)
        self._log: list[str] = []

    def log(self, message: str) -> None:
        self._log.append(message)
        print(f"  [n8n-setup] {message}")

    def get_log(self) -> list[str]:
        return list(self._log)

    def install(self) -> dict:
        connection = self.ssh.test_connection()
        if not connection["ok"]:
            return {"ok": False, "error": "SSH connection failed", "log": self._log}
        if not self.ssh.command_exists("docker"):
            self.log("Docker is required and is not installed; install it through the host OS package policy.")
            return {"ok": False, "error": "Docker not installed", "log": self._log}
        check = self.ssh.run("docker ps -a --filter name='^/n8n$' --format '{{.Names}}'")
        if check.get("stdout", "").strip() == "n8n":
            image = self.ssh.run("docker inspect --format '{{.Config.Image}}' n8n")
            if image.get("stdout", "").strip() != N8N_IMAGE:
                return {
                    "ok": False,
                    "error": "Existing n8n container uses an unexpected image; review it manually",
                    "log": self._log,
                }
            started = self.ssh.run("docker start n8n", timeout=30)
            if not started["ok"]:
                return {"ok": False, "error": "Existing n8n container could not start", "log": self._log}
        else:
            result = self._start_n8n_container()
            if not result["ok"]:
                return {"ok": False, "error": "n8n container failed to start", "log": self._log}
        for _ in range(30):
            health = self.ssh.run(
                f"curl --fail --silent http://127.0.0.1:{self.n8n_port}/healthz >/dev/null",
                timeout=10,
            )
            if health.get("ok"):
                tunnel = f"ssh -L {self.n8n_port}:127.0.0.1:{self.n8n_port} {self.host}"
                return {
                    "ok": True,
                    "url": f"http://127.0.0.1:{self.n8n_port}",
                    "ssh_tunnel": tunnel,
                    "message": "n8n installed on a loopback-only port",
                    "log": self._log,
                }
            time.sleep(2)
        return {"ok": False, "error": "n8n readiness timeout", "log": self._log}

    def _start_n8n_container(self) -> dict:
        command = (
            "docker run -d --name n8n --restart unless-stopped "
            f"-p 127.0.0.1:{self.n8n_port}:5678 "
            "-v n8n_data:/home/node/.n8n "
            "-e N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true "
            "-e N8N_RUNNERS_ENABLED=true "
            f"{N8N_IMAGE}"
        )
        return self.ssh.run(command, timeout=180)

    def uninstall(self) -> dict:
        self.ssh.run("docker rm --force n8n", timeout=30)
        return {"ok": True, "log": self._log}

    def status(self) -> dict:
        result = self.ssh.run("docker ps --filter name='^/n8n$' --format '{{.Status}}'")
        running = bool(result.get("stdout", "").strip())
        return {
            "running": running,
            "status": result.get("stdout", "").strip() or "not found",
            "url": f"http://127.0.0.1:{self.n8n_port}" if running else None,
        }
