"""
Smoke tests for n8n-workflow-manager.

Tests that can run without a real n8n server connection.
Covers: imports, config loading, database init, workflow parsing, client API shape.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure the package root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class TestImports(unittest.TestCase):
    """All core submodules must import without error."""

    def test_import_core_config(self):
        import n8nManager.core.config  # noqa: F401

    def test_import_core_database(self):
        import n8nManager.core.database  # noqa: F401

    def test_import_core_workflow_parser(self):
        import n8nManager.core.workflow_parser  # noqa: F401

    def test_import_core_n8n_client(self):
        import n8nManager.core.n8n_client  # noqa: F401

    def test_import_package_init(self):
        import n8nManager  # noqa: F401

    def test_import_api_server(self):
        import importlib
        if importlib.util.find_spec("fastapi") is None:
            self.skipTest("fastapi not installed")
        import n8nManager.api.server  # noqa: F401


class TestConfig(unittest.TestCase):
    """Config loading and default values."""

    def setUp(self):
        from n8nManager.core.config import load_config, get_db_path, DEFAULT_CONFIG
        self.load_config = load_config
        self.get_db_path = get_db_path
        self.DEFAULT_CONFIG = DEFAULT_CONFIG

    def test_load_config_returns_dict(self):
        cfg = self.load_config()
        self.assertIsInstance(cfg, dict)

    def test_load_config_has_required_keys(self):
        cfg = self.load_config()
        self.assertIn("api_port", cfg)
        self.assertIn("db_path", cfg)
        self.assertIn("n8n", cfg)

    def test_default_api_port(self):
        cfg = self.load_config()
        self.assertEqual(cfg["api_port"], 8100)

    def test_load_config_custom_path_missing_file(self):
        """A missing config file should return the defaults without crashing."""
        cfg = self.load_config(config_path="/nonexistent/config.json")
        self.assertEqual(cfg["api_port"], self.DEFAULT_CONFIG["api_port"])

    def test_load_config_custom_path_invalid_json(self):
        """A broken config file should fall back to defaults without crashing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            f.write("NOT VALID JSON {{{")
            tmp_path = f.name
        cfg = self.load_config(config_path=tmp_path)
        self.assertIn("api_port", cfg)

    def test_get_db_path_returns_absolute(self):
        cfg = self.load_config()
        db_path = self.get_db_path(cfg)
        self.assertTrue(db_path.is_absolute())

    def test_deep_merge(self):
        from n8nManager.core.config import _deep_merge
        base = {"a": 1, "b": {"x": 10, "y": 20}}
        override = {"b": {"y": 99, "z": 30}, "c": 3}
        result = _deep_merge(base, override)
        self.assertEqual(result["a"], 1)
        self.assertEqual(result["b"]["x"], 10)
        self.assertEqual(result["b"]["y"], 99)
        self.assertEqual(result["b"]["z"], 30)
        self.assertEqual(result["c"], 3)


class TestDatabase(unittest.TestCase):
    """Database creation and basic CRUD without a real n8n server."""

    def setUp(self):
        from n8nManager.core.database import Database
        self.tmp = tempfile.mkdtemp()
        self.db = Database(Path(self.tmp) / "test.db")

    def test_db_file_created(self):
        self.assertTrue((Path(self.tmp) / "test.db").exists())

    def test_list_workflows_empty(self):
        workflows = self.db.list_workflows()
        self.assertIsInstance(workflows, list)
        self.assertEqual(len(workflows), 0)

    def test_list_servers_empty(self):
        servers = self.db.list_servers()
        self.assertIsInstance(servers, list)
        self.assertEqual(len(servers), 0)

    def test_add_and_retrieve_server(self):
        self.db.add_server("local", "http://localhost:5678", "testkey")
        servers = self.db.list_servers()
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0]["name"], "local")
        self.assertEqual(servers[0]["url"], "http://localhost:5678")

    def test_server_verify_tls_default_on(self):
        srv_id = self.db.add_server("tlsdefault", "https://host:5678", "key")
        srv = self.db.get_server(srv_id)
        self.assertEqual(srv["verify_tls"], 1)

    def test_server_verify_tls_opt_out(self):
        srv_id = self.db.add_server("tlsoff", "https://host:5678", "key", verify_tls=False)
        srv = self.db.get_server(srv_id)
        self.assertEqual(srv["verify_tls"], 0)

    def test_verify_tls_migration_adds_column(self):
        """Databases created before verify_tls existed get the column on init."""
        import sqlite3
        legacy = Path(self.tmp) / "legacy.db"
        conn = sqlite3.connect(str(legacy))
        conn.execute("""CREATE TABLE servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            url TEXT NOT NULL,
            api_key TEXT DEFAULT '',
            is_default INTEGER DEFAULT 0,
            n8n_version TEXT DEFAULT '',
            last_ping TEXT,
            status TEXT DEFAULT 'unknown',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("INSERT INTO servers (name, url) VALUES ('old', 'http://h:5678')")
        conn.commit()
        conn.close()
        from n8nManager.core.database import Database
        db = Database(legacy)
        srv = db.get_server_by_name("old")
        self.assertEqual(srv["verify_tls"], 1)

    def test_add_duplicate_server_raises(self):
        import sqlite3
        self.db.add_server("dup", "http://host:5678", "key")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_server("dup", "http://host:5678", "key")

    def test_save_and_list_workflow(self):
        wf_json = json.dumps({
            "name": "Test WF",
            "nodes": [{"type": "n8n-nodes-base.manualTrigger", "name": "start"}],
            "connections": {},
        })
        self.db.add_workflow(
            name="Test WF",
            workflow_json=wf_json,
            source="local",
        )
        workflows = self.db.list_workflows()
        self.assertEqual(len(workflows), 1)
        self.assertEqual(workflows[0]["name"], "Test WF")

    def test_double_init_idempotent(self):
        """Re-initialising DB with same path must not raise."""
        from n8nManager.core.database import Database
        db2 = Database(Path(self.tmp) / "test.db")
        self.assertIsNotNone(db2)

    def test_list_templates_empty(self):
        templates = self.db.list_templates()
        self.assertIsInstance(templates, list)
        self.assertEqual(len(templates), 0)

    def test_add_and_get_template(self):
        tpl_json = json.dumps({"name": "{{name}}", "nodes": [], "connections": {}})
        tpl_id = self.db.add_template(
            name="My Template",
            template_json=tpl_json,
            description="A test template",
            category="testing",
            placeholders=["name"],
        )
        tpl = self.db.get_template(tpl_id)
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl["name"], "My Template")
        self.assertEqual(tpl["category"], "testing")
        # placeholders are stored as JSON string
        self.assertEqual(json.loads(tpl["placeholders"]), ["name"])

    def test_get_template_missing_returns_none(self):
        self.assertIsNone(self.db.get_template(99999))

    def test_list_templates_category_filter(self):
        tpl_json = json.dumps({"nodes": [], "connections": {}})
        self.db.add_template(name="A", template_json=tpl_json, category="alpha")
        self.db.add_template(name="B", template_json=tpl_json, category="beta")
        self.assertEqual(len(self.db.list_templates()), 2)
        alpha = self.db.list_templates(category="alpha")
        self.assertEqual(len(alpha), 1)
        self.assertEqual(alpha[0]["name"], "A")

    def test_add_duplicate_template_raises(self):
        import sqlite3
        tpl_json = json.dumps({"nodes": [], "connections": {}})
        self.db.add_template(name="dup", template_json=tpl_json)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_template(name="dup", template_json=tpl_json)

    def test_delete_template(self):
        tpl_json = json.dumps({"nodes": [], "connections": {}})
        tpl_id = self.db.add_template(name="gone", template_json=tpl_json)
        self.db.delete_template(tpl_id)
        self.assertIsNone(self.db.get_template(tpl_id))

    def test_node_catalog_seeded(self):
        """Default node catalog entries must be present after init."""
        nodes = self.db.list_node_catalog()
        self.assertGreater(len(nodes), 0)
        node_types = [n["node_type"] for n in nodes]
        self.assertIn("n8n-nodes-base.webhook", node_types)
        self.assertIn("node_type", nodes[0])
        self.assertIn("display_name", nodes[0])

    def test_node_catalog_category_filter(self):
        triggers = self.db.list_node_catalog(category="trigger")
        self.assertGreater(len(triggers), 0)
        self.assertTrue(all(n["category"] == "trigger" for n in triggers))


class TestWorkflowParser(unittest.TestCase):
    """Workflow JSON parsing and validation."""

    def setUp(self):
        from n8nManager.core.workflow_parser import (
            validate_workflow, load_workflow_file,
            compute_content_hash, extract_metadata,
        )
        self.validate_workflow = validate_workflow
        self.load_workflow_file = load_workflow_file
        self.compute_content_hash = compute_content_hash
        self.extract_metadata = extract_metadata

    def _make_wf(self, **kwargs):
        base = {
            "name": "My Workflow",
            "nodes": [{"type": "n8n-nodes-base.start", "name": "Start"}],
            "connections": {},
        }
        base.update(kwargs)
        return base

    def test_validate_valid_workflow(self):
        valid, err = self.validate_workflow(self._make_wf())
        self.assertTrue(valid)
        self.assertEqual(err, "")

    def test_validate_missing_nodes(self):
        valid, err = self.validate_workflow({"connections": {}})
        self.assertFalse(valid)
        self.assertIn("nodes", err)

    def test_validate_missing_connections(self):
        valid, err = self.validate_workflow({"nodes": []})
        self.assertFalse(valid)
        self.assertIn("connections", err)

    def test_validate_nodes_not_list(self):
        valid, err = self.validate_workflow({"nodes": "wrong", "connections": {}})
        self.assertFalse(valid)

    def test_validate_connections_not_dict(self):
        valid, err = self.validate_workflow({"nodes": [], "connections": "wrong"})
        self.assertFalse(valid)

    def test_validate_not_a_dict(self):
        valid, err = self.validate_workflow("not-a-dict")
        self.assertFalse(valid)

    def test_load_workflow_file_not_found(self):
        data, err = self.load_workflow_file("/nonexistent/file.json")
        self.assertIsNone(data)
        self.assertIn("nicht gefunden", err.lower())

    def test_load_workflow_file_valid(self):
        wf = self._make_wf()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            json.dump(wf, f)
            tmp_path = f.name
        data, err = self.load_workflow_file(tmp_path)
        self.assertIsNotNone(data)
        self.assertEqual(err, "")

    def test_load_workflow_file_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         delete=False, encoding="utf-8") as f:
            f.write("{broken json")
            tmp_path = f.name
        data, err = self.load_workflow_file(tmp_path)
        self.assertIsNone(data)
        self.assertIn("JSON", err)

    def test_compute_content_hash_deterministic(self):
        wf_json = json.dumps(self._make_wf())
        h1 = self.compute_content_hash(wf_json)
        h2 = self.compute_content_hash(wf_json)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex

    def test_compute_content_hash_order_independent(self):
        wf_a = json.dumps({"connections": {}, "nodes": [], "name": "X"})
        wf_b = json.dumps({"name": "X", "nodes": [], "connections": {}})
        self.assertEqual(
            self.compute_content_hash(wf_a),
            self.compute_content_hash(wf_b),
        )

    def test_extract_metadata_node_count(self):
        wf = self._make_wf(nodes=[
            {"type": "n8n-nodes-base.start", "name": "A"},
            {"type": "n8n-nodes-base.httpRequest", "name": "B"},
        ])
        meta = self.extract_metadata(wf)
        self.assertEqual(meta["node_count"], 2)

    def test_extract_metadata_trigger_detected(self):
        wf = self._make_wf(nodes=[
            {"type": "n8n-nodes-base.webhookTrigger", "name": "Hook"},
        ])
        meta = self.extract_metadata(wf)
        self.assertIn("webhook", meta["trigger_type"].lower())

    def test_extract_metadata_no_trigger(self):
        wf = self._make_wf(nodes=[
            {"type": "n8n-nodes-base.httpRequest", "name": "Req"},
        ])
        meta = self.extract_metadata(wf)
        self.assertEqual(meta["trigger_type"], "")

    def test_extract_metadata_tags(self):
        wf = self._make_wf(tags=[{"name": "prod"}, {"name": "test"}])
        meta = self.extract_metadata(wf)
        self.assertIn("prod", meta["tags"])
        self.assertIn("test", meta["tags"])


class TestN8nClientShape(unittest.TestCase):
    """N8nClient instantiation and URL building -- no network calls."""

    def setUp(self):
        from n8nManager.core.n8n_client import N8nClient
        self.client = N8nClient("http://localhost:5678", "dummykey")

    def test_instantiation(self):
        self.assertIsNotNone(self.client)

    def test_base_url_stored(self):
        self.assertEqual(self.client.base_url, "http://localhost:5678")

    def test_url_builder(self):
        url = self.client._url("/workflows")
        self.assertEqual(url, "http://localhost:5678/api/v1/workflows")

    def test_trailing_slash_stripped(self):
        from n8nManager.core.n8n_client import N8nClient
        c = N8nClient("http://localhost:5678/", "key")
        self.assertFalse(c.base_url.endswith("/"))

    def test_verify_tls_default_true(self):
        """TLS verification must be enabled by default."""
        self.assertTrue(self.client.verify_tls)

    def test_verify_tls_opt_out(self):
        from n8nManager.core.n8n_client import N8nClient
        c = N8nClient("https://localhost:5678", "key", verify_tls=False)
        self.assertFalse(c.verify_tls)


class TestN8nClientPagination(unittest.TestCase):
    """list_all_workflows must follow the n8n cursor across pages -- no network."""

    def _client_with_pages(self, pages):
        from n8nManager.core.n8n_client import N8nClient
        client = N8nClient("http://localhost:5678", "key")
        calls = []

        def fake_list(limit=100, cursor=""):
            calls.append(cursor)
            return pages[len(calls) - 1]

        client.list_workflows = fake_list
        return client, calls

    def test_follows_cursor_across_pages(self):
        pages = [
            {"data": [{"id": "1"}, {"id": "2"}], "nextCursor": "abc"},
            {"data": [{"id": "3"}], "nextCursor": "def"},
            {"data": [{"id": "4"}], "nextCursor": None},
        ]
        client, calls = self._client_with_pages(pages)
        result = client.list_all_workflows()
        self.assertEqual(len(result["data"]), 4)
        self.assertEqual(calls, ["", "abc", "def"])

    def test_single_page_without_cursor(self):
        pages = [{"data": [{"id": "1"}]}]
        client, calls = self._client_with_pages(pages)
        result = client.list_all_workflows()
        self.assertEqual(len(result["data"]), 1)
        self.assertEqual(calls, [""])

    def test_error_is_propagated(self):
        pages = [
            {"data": [{"id": "1"}], "nextCursor": "abc"},
            {"error": True, "detail": "boom"},
        ]
        client, calls = self._client_with_pages(pages)
        result = client.list_all_workflows()
        self.assertTrue(result.get("error"))
        self.assertEqual(calls, ["", "abc"])


class TestApiRoutes(unittest.TestCase):
    """FastAPI TestClient smoke tests against the real app with a temp database."""

    @classmethod
    def setUpClass(cls):
        import importlib
        if importlib.util.find_spec("fastapi") is None:
            raise unittest.SkipTest("fastapi not installed")
        from fastapi.testclient import TestClient
        import n8nManager.api.server as server_module
        from n8nManager.core.database import Database
        cls.tmp = tempfile.mkdtemp()
        cls.server_module = server_module
        cls._old_db = server_module._db
        server_module._db = Database(Path(cls.tmp) / "api_test.db")
        cls.db = server_module._db
        cls.client = TestClient(server_module.app)

    @classmethod
    def tearDownClass(cls):
        cls.server_module._db = cls._old_db

    def test_api_status(self):
        resp = self.client.get("/api/status")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "running")

    def test_templates_list_empty_ok(self):
        resp = self.client.get("/api/templates")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("data", body)
        self.assertIsInstance(body["data"], list)

    def test_template_create_get_instantiate(self):
        tpl_json = json.dumps({
            "name": "{{name}}",
            "nodes": [{"type": "n8n-nodes-base.manualTrigger", "name": "Start"}],
            "connections": {},
        })
        resp = self.client.post("/api/templates", json={
            "name": "Smoke Template",
            "description": "via TestClient",
            "category": "smoke",
            "template_json": tpl_json,
            "placeholders": ["name"],
        })
        self.assertEqual(resp.status_code, 200)
        tpl_id = resp.json()["id"]

        resp = self.client.get(f"/api/templates/{tpl_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "Smoke Template")

        resp = self.client.post(
            f"/api/templates/{tpl_id}/instantiate", json={"name": "Instantiated WF"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("id", resp.json())

    def test_template_missing_returns_404(self):
        resp = self.client.get("/api/templates/99999")
        self.assertEqual(resp.status_code, 404)

    def test_template_duplicate_returns_409(self):
        tpl_json = json.dumps({"nodes": [], "connections": {}})
        payload = {"name": "Dup Template", "template_json": tpl_json}
        resp = self.client.post("/api/templates", json=payload)
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post("/api/templates", json=payload)
        self.assertEqual(resp.status_code, 409)

    def test_servers_api_redacts_key(self):
        secret = "supersecret-api-key-9876"
        resp = self.client.post("/api/servers", json={
            "name": "redact-test",
            "url": "https://n8n.example.com:5678",
            "api_key": secret,
        })
        self.assertEqual(resp.status_code, 200)
        srv_id = resp.json()["id"]

        resp = self.client.get("/api/servers")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(secret, resp.text)
        entry = [s for s in resp.json()["data"] if s["id"] == srv_id][0]
        self.assertEqual(entry["api_key"], "***9876")

        resp = self.client.get(f"/api/servers/{srv_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(secret, resp.text)
        self.assertEqual(resp.json()["api_key"], "***9876")

        # the stored key must remain intact in the database
        self.assertEqual(self.db.get_server(srv_id)["api_key"], secret)

    def test_servers_page_does_not_leak_key(self):
        secret = "another-secret-key-4321"
        self.db.add_server("page-redact", "https://n8n.example.org:5678", secret)
        resp = self.client.get("/servers")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(secret, resp.text)

    def test_redact_server_short_and_empty_keys(self):
        from n8nManager.api.routes_servers import redact_server
        self.assertEqual(redact_server({"api_key": "abc"})["api_key"], "***")
        self.assertEqual(redact_server({"api_key": ""})["api_key"], "")
        self.assertEqual(redact_server({})["api_key"], "")

    def test_creator_page_renders(self):
        resp = self.client.get("/creator")
        self.assertEqual(resp.status_code, 200)

    def test_editor_page_renders(self):
        wf_json = json.dumps({
            "name": "Editor WF",
            "nodes": [{"type": "n8n-nodes-base.manualTrigger", "name": "Start",
                       "position": [0, 0]}],
            "connections": {},
        })
        wf_id = self.db.add_workflow(name="Editor WF", workflow_json=wf_json)
        resp = self.client.get(f"/editor/{wf_id}")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
