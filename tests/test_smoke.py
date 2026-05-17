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


if __name__ == "__main__":
    unittest.main()
