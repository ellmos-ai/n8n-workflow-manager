"""REST-Client für die n8n API."""
import logging

import httpx
from typing import Optional

logger = logging.getLogger(__name__)


class N8nClient:
    """Synchroner httpx-Client für n8n REST API v1."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 15.0,
                 verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        # TLS certificate verification is on by default; opt out per server
        # (verify_tls=False) only for local self-signed setups.
        self.verify_tls = verify_tls
        self._headers = {
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Führt HTTP-Request aus und gibt ein Ergebnis-Dict zurück."""
        try:
            with httpx.Client(timeout=self.timeout, verify=self.verify_tls) as client:
                resp = client.request(method, self._url(path), headers=self._headers, **kwargs)
                resp.raise_for_status()
                return resp.json() if resp.content else {}
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            logger.warning("n8n API request failed with HTTP %s: %s", status_code, exc)
            return {
                "error": True,
                "status_code": status_code,
                "detail": f"n8n API returned HTTP {status_code}",
            }
        except httpx.RequestError as exc:
            logger.warning("n8n API request failed: %s", exc)
            return {"error": True, "detail": "n8n API request failed"}

    def ping(self) -> dict:
        """Health-Check: GET /api/v1/workflows?limit=1"""
        result = self._request("GET", "/workflows?limit=1")
        if "error" in result:
            return {"ok": False, **result}
        return {"ok": True, "message": "n8n erreichbar"}

    def list_workflows(self, limit: int = 100, cursor: str = "") -> dict:
        path = f"/workflows?limit={limit}"
        if cursor:
            path += f"&cursor={cursor}"
        return self._request("GET", path)

    def list_all_workflows(self, page_size: int = 100) -> dict:
        """Follows the n8n API cursor and collects workflows across all pages.

        Returns {"data": [...]} with every workflow, or the error dict of
        the first failing page.
        """
        all_items: list = []
        cursor = ""
        while True:
            result = self.list_workflows(limit=page_size, cursor=cursor)
            if result.get("error"):
                return result
            all_items.extend(result.get("data", []))
            cursor = result.get("nextCursor") or ""
            if not cursor:
                break
        return {"data": all_items}

    def get_workflow(self, workflow_id: str) -> dict:
        return self._request("GET", f"/workflows/{workflow_id}")

    @staticmethod
    def _clean_for_create(data: dict) -> dict:
        """Entfernt Felder die n8n bei POST /workflows nicht akzeptiert."""
        clean = dict(data)
        for key in ("id", "tags", "active", "createdAt", "updatedAt", "versionId"):
            clean.pop(key, None)
        return clean

    def create_workflow(self, workflow_data: dict) -> dict:
        return self._request("POST", "/workflows", json=self._clean_for_create(workflow_data))

    def update_workflow(self, workflow_id: str, workflow_data: dict) -> dict:
        return self._request("PUT", f"/workflows/{workflow_id}", json=workflow_data)

    def delete_workflow(self, workflow_id: str) -> dict:
        return self._request("DELETE", f"/workflows/{workflow_id}")

    def activate_workflow(self, workflow_id: str) -> dict:
        return self._request("PATCH", f"/workflows/{workflow_id}", json={"active": True})

    def deactivate_workflow(self, workflow_id: str) -> dict:
        return self._request("PATCH", f"/workflows/{workflow_id}", json={"active": False})
