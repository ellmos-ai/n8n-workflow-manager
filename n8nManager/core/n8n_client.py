"""Synchronous client for the n8n public REST API."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

logger = logging.getLogger(__name__)

WRITABLE_WORKFLOW_FIELDS = {
    "name",
    "description",
    "parentFolderId",
    "nodes",
    "connections",
    "nodeGroups",
    "settings",
    "staticData",
    "pinData",
}


def normalize_server_url(value: str) -> str:
    """Validate and normalize an operator-configured n8n instance URL."""
    candidate = (value or "").strip()
    if not candidate or any(ord(char) < 32 for char in candidate):
        raise ValueError("server URL is empty or contains control characters")
    try:
        parsed = urlsplit(candidate)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("server URL contains an invalid port") from exc
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("server URL must use http or https")
    if not parsed.hostname:
        raise ValueError("server URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("server URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("server URL must not contain a query or fragment")
    path = parsed.path.rstrip("/")
    if path.endswith("/api/v1") or path == "/api/v1":
        raise ValueError("use the n8n instance URL without /api/v1")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class N8nClient:
    """Small httpx wrapper around n8n's public API v1."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 15.0,
        verify_tls: bool = True,
    ):
        self.base_url = normalize_server_url(base_url)
        self.api_key = api_key
        self.timeout = timeout
        self.verify_tls = verify_tls
        self._headers = {
            "X-N8N-API-KEY": api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        try:
            with httpx.Client(
                timeout=self.timeout,
                verify=self.verify_tls,
                follow_redirects=False,
            ) as client:
                response = client.request(
                    method, self._url(path), headers=self._headers, **kwargs
                )
                response.raise_for_status()
                if not response.content:
                    return {}
                payload = response.json()
                if not isinstance(payload, dict):
                    return {"error": True, "detail": "n8n API returned an unexpected response"}
                return payload
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning(
                "n8n API %s %s failed with HTTP %s", method, path, status_code
            )
            return {
                "error": True,
                "status_code": status_code,
                "detail": f"n8n API returned HTTP {status_code}",
            }
        except httpx.RequestError as exc:
            logger.warning("n8n API %s %s request failed: %s", method, path, exc)
            return {"error": True, "detail": "n8n API request failed"}
        except ValueError:
            logger.warning("n8n API %s %s returned invalid JSON", method, path)
            return {"error": True, "detail": "n8n API returned invalid JSON"}

    def ping(self) -> dict:
        result = self._request("GET", "/workflows", params={"limit": 1})
        if result.get("error"):
            return {"ok": False, **result}
        return {"ok": True, "message": "n8n is reachable"}

    def list_workflows(self, limit: int = 100, cursor: str = "") -> dict:
        page_size = max(1, min(int(limit), 250))
        params = {"limit": page_size}
        if cursor:
            params["cursor"] = cursor
        return self._request("GET", "/workflows", params=params)

    def list_all_workflows(self, page_size: int = 100, max_pages: int = 10000) -> dict:
        all_items: list = []
        cursor = ""
        seen_cursors = set()
        for _ in range(max_pages):
            result = self.list_workflows(limit=page_size, cursor=cursor)
            if result.get("error"):
                return result
            data = result.get("data", [])
            if not isinstance(data, list):
                return {"error": True, "detail": "n8n API returned invalid workflow data"}
            all_items.extend(data)
            next_cursor = result.get("nextCursor") or ""
            if not next_cursor:
                return {"data": all_items}
            if next_cursor in seen_cursors:
                return {"error": True, "detail": "n8n API repeated a pagination cursor"}
            seen_cursors.add(next_cursor)
            cursor = str(next_cursor)
        return {"error": True, "detail": "n8n API pagination limit exceeded"}

    def get_workflow(self, workflow_id: str) -> dict:
        return self._request("GET", f"/workflows/{workflow_id}")

    @staticmethod
    def _clean_workflow_payload(data: dict) -> dict:
        clean = {key: data[key] for key in WRITABLE_WORKFLOW_FIELDS if key in data}
        clean.setdefault("name", "Untitled Workflow")
        clean.setdefault("nodes", [])
        clean.setdefault("connections", {})
        clean.setdefault("settings", {})
        return clean

    def create_workflow(self, workflow_data: dict) -> dict:
        return self._request(
            "POST", "/workflows", json=self._clean_workflow_payload(workflow_data)
        )

    def update_workflow(self, workflow_id: str, workflow_data: dict) -> dict:
        return self._request(
            "PUT",
            f"/workflows/{workflow_id}",
            json=self._clean_workflow_payload(workflow_data),
        )

    def delete_workflow(self, workflow_id: str) -> dict:
        return self._request("DELETE", f"/workflows/{workflow_id}")

    def activate_workflow(self, workflow_id: str) -> dict:
        return self._request("POST", f"/workflows/{workflow_id}/activate")

    def deactivate_workflow(self, workflow_id: str) -> dict:
        return self._request("POST", f"/workflows/{workflow_id}/deactivate")
