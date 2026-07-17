"""Programmatisches Erstellen von n8n Workflows."""
import json


class WorkflowBuilder:
    """Builder-Pattern fuer n8n Workflow JSON."""

    def __init__(self, name: str = "Neuer Workflow"):
        self.name = name
        self.nodes = []
        self.connections = {}
        self.settings = {"executionOrder": "v1"}
        self._node_counter = 0

    def add_node(self, node_type: str, name: str = "", parameters: dict = None,
                 position: list = None) -> str:
        """Node hinzufuegen. Gibt den Node-Namen zurueck."""
        if not name:
            self._node_counter += 1
            name = f"Node_{self._node_counter}"

        if position is None:
            position = [250 * len(self.nodes), 300]

        node = {
            "parameters": parameters or {},
            "type": node_type,
            "typeVersion": 1,
            "position": position,
            "id": f"node-{len(self.nodes)}",
            "name": name,
        }
        self.nodes.append(node)
        return name

    def connect(self, source_name: str, target_name: str,
                source_output: int = 0, target_input: int = 0):
        """Zwei Nodes verbinden."""
        if source_name not in self.connections:
            self.connections[source_name] = {"main": []}

        main = self.connections[source_name]["main"]
        while len(main) <= source_output:
            main.append([])

        main[source_output].append({
            "node": target_name,
            "type": "main",
            "index": target_input,
        })

    def build(self) -> dict:
        """Workflow-dict zurueckgeben."""
        return {
            "name": self.name,
            "nodes": self.nodes,
            "connections": self.connections,
            "settings": self.settings,
            "active": False,
            "tags": [],
        }

    def to_json(self, indent: int = 2) -> str:
        """Als JSON-String."""
        return json.dumps(self.build(), indent=indent, ensure_ascii=False)

    # ── Convenience-Methoden fuer haeufige Patterns ──

    def add_webhook_trigger(self, path: str = "/webhook", http_method: str = "POST",
                            name: str = "Webhook") -> str:
        return self.add_node(
            "n8n-nodes-base.webhook", name,
            parameters={"path": path, "httpMethod": http_method},
            position=[250, 300]
        )

    def add_schedule_trigger(self, cron: str = "0 9 * * *",
                             name: str = "Schedule Trigger") -> str:
        return self.add_node(
            "n8n-nodes-base.scheduleTrigger", name,
            parameters={"rule": {"interval": [{"field": "cronExpression", "expression": cron}]}},
            position=[250, 300]
        )

    def add_http_request(self, url: str, method: str = "GET",
                         name: str = "HTTP Request") -> str:
        return self.add_node(
            "n8n-nodes-base.httpRequest", name,
            parameters={"url": url, "method": method}
        )

    def add_code_node(self, code: str, name: str = "Code") -> str:
        return self.add_node(
            "n8n-nodes-base.code", name,
            parameters={"jsCode": code}
        )

    def add_if_node(self, field: str, operation: str = "equal",
                    value: str = "", name: str = "IF") -> str:
        return self.add_node(
            "n8n-nodes-base.if", name,
            parameters={"conditions": {"string": [{"value1": f"={{{{$json[\"{field}\"]}}}}", "operation": operation, "value2": value}]}}
        )
