"""Regression tests for the 0.2 security, history, and release hardening."""

from __future__ import annotations

import json
import sqlite3
from importlib.resources import files

import pytest
from fastapi.testclient import TestClient

from n8nManager import __version__
from n8nManager.core.database import Database
from n8nManager.core.n8n_client import N8nClient, normalize_server_url
from n8nManager.core.workflow_parser import validate_workflow, workflow_to_vis_graph
from n8nManager.n8n_manager import _safe_filename
from n8nManager.setup.ssh_helper import SSHHelper


def workflow(name="Example", active=False):
    return {
        "name": name,
        "active": active,
        "nodes": [
            {
                "id": "node-1",
                "name": "Start",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [0, 0],
                "parameters": {},
            }
        ],
        "connections": {},
        "settings": {"executionOrder": "v1"},
    }


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "manager.db")


@pytest.fixture
def api_client(tmp_path):
    import n8nManager.api.server as server

    previous = server._db
    server._db = Database(tmp_path / "api.db")
    with TestClient(server.app, base_url="http://127.0.0.1") as client:
        yield client, server._db
    server._db = previous


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://localhost:5678", "http://localhost:5678"),
        ("http://localhost:5678/", "http://localhost:5678"),
        ("https://n8n.example.com", "https://n8n.example.com"),
        ("https://n8n.example.com/tenant/", "https://n8n.example.com/tenant"),
        ("http://127.0.0.1", "http://127.0.0.1"),
        ("http://[::1]:5678", "http://[::1]:5678"),
        (" https://n8n.example.org ", "https://n8n.example.org"),
        ("https://sub.domain.example:8443/n8n", "https://sub.domain.example:8443/n8n"),
    ],
)
def test_normalize_server_url_valid(raw, expected):
    assert normalize_server_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ftp://example.com",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user@example.com",
        "https://user:pass@example.com",
        "https://example.com?secret=1",
        "https://example.com#fragment",
        "https://example.com/api/v1",
        "https://example.com/n8n/api/v1",
        "example.com",
        "http://",
        "http://example.com:bad",
        "http://example.com:99999",
        "http://exam\nple.com",
        "ssh://example.com",
    ],
)
def test_normalize_server_url_rejects_unsafe_values(raw):
    with pytest.raises(ValueError):
        normalize_server_url(raw)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda data: data.pop("nodes"),
        lambda data: data.pop("connections"),
        lambda data: data.update(nodes={}),
        lambda data: data.update(connections=[]),
        lambda data: data["nodes"].append("not-an-object"),
        lambda data: data["nodes"][0].update(name=""),
        lambda data: data["nodes"][0].pop("name"),
        lambda data: data["nodes"][0].update(type=""),
        lambda data: data["nodes"][0].update(parameters=[]),
        lambda data: data["nodes"][0].update(position=[1]),
        lambda data: data["nodes"].append({**data["nodes"][0], "id": "2"}),
        lambda data: data.update(connections={"Missing": {"main": []}}),
        lambda data: data.update(connections={"Start": []}),
        lambda data: data.update(connections={"Start": {"main": {}}}),
        lambda data: data.update(connections={"Start": {"main": [{}]}}),
        lambda data: data.update(connections={"Start": {"main": [["bad"]]}}),
        lambda data: data.update(connections={"Start": {"main": [[{"node": "Missing"}]]}}),
    ],
)
def test_workflow_validator_rejects_structural_damage(mutation):
    data = workflow()
    mutation(data)
    valid, error = validate_workflow(data)
    assert not valid
    assert error


@pytest.mark.parametrize(
    "read_only_field",
    ["id", "active", "createdAt", "updatedAt", "versionId", "triggerCount", "shared", "tags"],
)
def test_remote_payload_drops_read_only_fields(read_only_field):
    data = workflow()
    data[read_only_field] = "server-owned"
    clean = N8nClient._clean_workflow_payload(data)
    assert read_only_field not in clean
    assert clean["name"] == "Example"


@pytest.mark.parametrize(
    ("method_name", "http_method", "path"),
    [
        ("activate_workflow", "POST", "/workflows/42/activate"),
        ("deactivate_workflow", "POST", "/workflows/42/deactivate"),
        ("delete_workflow", "DELETE", "/workflows/42"),
        ("get_workflow", "GET", "/workflows/42"),
    ],
)
def test_n8n_client_uses_official_method_and_path(monkeypatch, method_name, http_method, path):
    client = N8nClient("https://n8n.example", "key")
    calls = []
    monkeypatch.setattr(client, "_request", lambda method, url, **kwargs: calls.append((method, url)) or {})
    getattr(client, method_name)("42")
    assert calls == [(http_method, path)]


@pytest.mark.parametrize("decision", [" ", "\t", "\r\n"])
def test_database_requires_nonempty_create_decision(db, decision):
    with pytest.raises(ValueError):
        db.add_workflow("A", json.dumps(workflow()), decision=decision)


def test_database_create_update_rollback_history(db):
    workflow_id = db.add_workflow("A", json.dumps(workflow("A")), decision="Initial design")
    changed = workflow("B")
    db.update_workflow(
        workflow_id,
        name="B",
        workflow_json=json.dumps(changed),
        decision="Rename after review",
    )
    versions = db.get_versions(workflow_id)
    assert [row["version_number"] for row in versions] == [2, 1]
    assert [row["action"] for row in db.get_decisions(workflow_id)] == ["update", "create"]
    db.update_workflow(
        workflow_id,
        workflow_json=versions[-1]["workflow_json"],
        decision="Restore initial state",
        action="rollback",
    )
    assert db.get_versions(workflow_id)[0]["version_number"] == 3
    assert db.get_decisions(workflow_id)[0]["action"] == "rollback"


def test_delete_cleans_foreign_keys_and_keeps_decision_audit(db):
    server_id = db.add_server("local", "http://127.0.0.1:5678")
    workflow_id = db.add_workflow("A", json.dumps(workflow()), decision="Create")
    db.add_version(workflow_id, json.dumps(workflow("Version two")), "Version two")
    db.add_sync_entry(workflow_id, server_id, "push")
    assert db.delete_workflow(workflow_id, "No longer used")
    assert db.get_workflow(workflow_id) is None
    assert db.get_versions(workflow_id) == []
    assert db.get_decisions(workflow_id)[0]["action"] == "delete"
    assert db.get_sync_history(server_id=server_id)[0]["workflow_id"] is None


def test_existing_workflow_gets_migration_baseline_history(tmp_path):
    path = tmp_path / "legacy.db"
    original = Database(path)
    workflow_id = original.add_workflow("Legacy", json.dumps(workflow()))
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM workflow_versions WHERE workflow_id = ?", (workflow_id,))
        connection.execute("DELETE FROM workflow_decisions WHERE workflow_id = ?", (workflow_id,))
    migrated = Database(path)
    assert migrated.get_versions(workflow_id)[0]["change_note"].startswith("Baseline")
    assert migrated.get_decisions(workflow_id)[0]["action"] == "migration"


def test_remote_identity_is_server_scoped(db):
    first = db.add_server("one", "https://one.example")
    second = db.add_server("two", "https://two.example")
    one_id = db.add_workflow("One", json.dumps(workflow()), server_id=first, n8n_id="7")
    two_id = db.add_workflow("Two", json.dumps(workflow()), server_id=second, n8n_id="7")
    assert db.get_workflow_by_remote(first, "7")["id"] == one_id
    assert db.get_workflow_by_remote(second, "7")["id"] == two_id


def test_legacy_remote_columns_migrate_to_mapping_table(tmp_path):
    path = tmp_path / "legacy-remotes.db"
    original = Database(path)
    server_id = original.add_server("legacy", "https://legacy.example")
    workflow_id = original.add_workflow(
        "Legacy", json.dumps(workflow()), server_id=server_id, n8n_id="legacy-id"
    )
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM workflow_remotes")
    migrated = Database(path)
    assert migrated.get_workflow_remote(workflow_id, server_id)["n8n_id"] == "legacy-id"


def test_legacy_duplicate_remote_binding_keeps_newest_and_audits_older(tmp_path):
    path = tmp_path / "legacy-duplicates.db"
    original = Database(path)
    server_id = original.add_server("legacy", "https://legacy.example")
    older = original.add_workflow("Older", json.dumps(workflow("Older")))
    newer = original.add_workflow("Newer", json.dumps(workflow("Newer")))
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM workflow_remotes")
        connection.execute(
            "UPDATE workflows SET server_id = ?, n8n_id = ?, updated_at = ? WHERE id = ?",
            (server_id, "duplicate-id", "2026-01-01T00:00:00+00:00", older),
        )
        connection.execute(
            "UPDATE workflows SET server_id = ?, n8n_id = ?, updated_at = ? WHERE id = ?",
            (server_id, "duplicate-id", "2026-02-01T00:00:00+00:00", newer),
        )
    migrated = Database(path)
    assert migrated.get_workflow_by_remote(server_id, "duplicate-id")["id"] == newer
    assert migrated.get_workflow(older)["server_id"] is None
    assert migrated.get_workflow(older)["n8n_id"] == ""
    assert migrated.get_decisions(older)[0]["action"] == "migration-remote-conflict"


def test_server_filter_uses_all_remote_bindings(db):
    first = db.add_server("first", "https://first.example")
    second = db.add_server("second", "https://second.example")
    workflow_id = db.add_workflow(
        "Both", json.dumps(workflow()), server_id=first, n8n_id="first-id"
    )
    db.bind_workflow_remote(workflow_id, second, "second-id", "Bind second server")
    assert [item["id"] for item in db.list_workflows(server_id=first)] == [workflow_id]
    assert [item["id"] for item in db.list_workflows(server_id=second)] == [workflow_id]


@pytest.mark.parametrize("field", ["drop table workflows", "unknown", "created_at", "id"])
def test_database_rejects_dynamic_unknown_fields(db, field):
    workflow_id = db.add_workflow("A", json.dumps(workflow()))
    with pytest.raises(ValueError):
        db.update_workflow(workflow_id, decision="Attempt invalid field", **{field: "bad"})


@pytest.mark.parametrize("limit", [-10, 0, 1, 50, 500, 999999])
def test_history_limit_is_bounded(db, limit):
    assert isinstance(db.get_sync_history(limit=limit), list)


def test_bundled_templates_are_valid_and_resource_backed(db):
    resources = {item.name for item in files("n8nManager.templates").iterdir()}
    templates = db.list_templates(category="bundled")
    assert {"webhook_forwarder.json", "scheduled_http_check.json"} <= resources
    assert len(templates) >= 2
    assert all(validate_workflow(json.loads(item["template_json"]))[0] for item in templates)


def test_graph_retains_node_and_connection_metadata():
    data = workflow()
    data["nodes"].append({
        "id": "node-2", "name": "Target", "type": "n8n-nodes-base.set",
        "typeVersion": 3, "position": [100, 200], "parameters": {"x": 1},
    })
    data["connections"] = {"Start": {"main": [[{"node": "Target", "type": "main", "index": 2}]]}}
    graph = workflow_to_vis_graph(data)
    assert graph["nodes"][1]["type_version"] == 3
    assert graph["nodes"][1]["n8n_params"] == {"x": 1}
    assert graph["edges"][0]["target_input"] == 2


def test_cross_origin_browser_mutation_is_denied(api_client):
    client, _ = api_client
    response = client.post(
        "/api/workflows",
        headers={"Origin": "https://attacker.example"},
        json={"name": "X", "workflow_json": json.dumps(workflow()), "decision": "attack"},
    )
    assert response.status_code == 403


def test_same_origin_browser_mutation_is_allowed(api_client):
    client, _ = api_client
    response = client.post(
        "/api/workflows",
        headers={"Origin": "http://127.0.0.1"},
        json={"name": "X", "workflow_json": json.dumps(workflow()), "decision": "create"},
    )
    assert response.status_code == 200


def test_matching_attacker_origin_and_host_is_rejected(api_client):
    client, _ = api_client
    response = client.post(
        "/api/servers",
        headers={"Host": "attacker.example", "Origin": "http://attacker.example"},
        json={"name": "rebound", "url": "https://attacker.example", "api_key": "stored-key"},
    )
    assert response.status_code == 400
    assert "Invalid host header" in response.text


@pytest.mark.parametrize(
    "host",
    ["[2001:db8::1]", "attacker.example", "attacker.example@localhost", "localhost#attacker"],
)
def test_untrusted_or_malformed_host_headers_are_rejected(api_client, host):
    client, _ = api_client
    response = client.get("/api/status", headers={"Host": host})
    assert response.status_code == 400


def test_ipv6_loopback_host_header_is_supported(api_client):
    client, _ = api_client
    response = client.get("/api/status", headers={"Host": "[::1]:8100"})
    assert response.status_code == 200


@pytest.mark.parametrize("url", ["file:///etc/passwd", "https://u:p@example.com", "ftp://host", "http://host/api/v1"])
def test_server_api_rejects_unsafe_url(api_client, url):
    client, _ = api_client
    response = client.post("/api/servers", json={"name": "unsafe", "url": url})
    assert response.status_code in {400, 422}


def test_server_api_duplicate_is_conflict(api_client):
    client, _ = api_client
    payload = {"name": "same", "url": "https://n8n.example"}
    assert client.post("/api/servers", json=payload).status_code == 200
    assert client.post("/api/servers", json=payload).status_code == 409


@pytest.mark.parametrize("raw", ["not json", "[]", '{"nodes": []}', '{"connections": {}}'])
def test_template_api_rejects_invalid_workflow_json(api_client, raw):
    client, _ = api_client
    response = client.post("/api/templates", json={"name": f"bad-{len(raw)}", "template_json": raw})
    assert response.status_code == 400


def test_template_substitution_preserves_typed_exact_values(api_client):
    client, db = api_client
    template_id = db.add_template(
        "Typed",
        json.dumps({
            "name": "{{NAME}}",
            "nodes": [{
                "name": "Start", "type": "n8n-nodes-base.manualTrigger",
                "parameters": {"enabled": "{{ENABLED}}", "count": "{{COUNT}}"},
            }],
            "connections": {},
        }),
    )
    response = client.post(
        f"/api/templates/{template_id}/instantiate",
        json={"values": {"NAME": "Typed WF", "ENABLED": True, "COUNT": 3}, "decision": "Test types"},
    )
    assert response.status_code == 200
    data = json.loads(db.get_workflow(response.json()["id"])["workflow_json"])
    assert data["nodes"][0]["parameters"] == {"enabled": True, "count": 3}


def test_api_crud_history_rollback_delete(api_client):
    client, _ = api_client
    created = client.post(
        "/api/workflows",
        json={"name": "One", "workflow_json": json.dumps(workflow("One")), "decision": "Initial"},
    )
    assert created.status_code == 200
    workflow_id = created.json()["id"]
    changed = client.put(
        f"/api/workflows/{workflow_id}",
        json={"name": "Two", "workflow_json": json.dumps(workflow("Two")), "decision": "Rename"},
    )
    assert changed.status_code == 200
    history = client.get(f"/api/workflows/{workflow_id}/history").json()
    assert len(history["versions"]) == 2
    assert len(history["decisions"]) == 2
    rolled = client.post(
        f"/api/workflows/{workflow_id}/rollback/1", json={"decision": "Restore"}
    )
    assert rolled.status_code == 200
    deleted = client.delete(f"/api/workflows/{workflow_id}?decision=Retire")
    assert deleted.status_code == 200
    assert client.get(f"/api/workflows/{workflow_id}").status_code == 404


def test_api_active_delete_requires_explicit_confirmation(api_client):
    client, _ = api_client
    created = client.post(
        "/api/workflows",
        json={"name": "Active", "workflow_json": json.dumps(workflow(active=True)), "decision": "Initial"},
    )
    workflow_id = created.json()["id"]
    assert client.delete(f"/api/workflows/{workflow_id}?decision=Retire").status_code == 409
    assert client.delete(
        f"/api/workflows/{workflow_id}?decision=Retire&confirm_active=true"
    ).status_code == 200


def test_pull_updates_existing_server_scoped_workflow(api_client, monkeypatch):
    client, db = api_client
    server_id = db.add_server("remote", "https://n8n.example", "key", is_default=True)
    existing_id = db.add_workflow(
        "Old",
        json.dumps({**workflow("Old"), "id": "remote-1"}),
        server_id=server_id,
        n8n_id="remote-1",
        source="pull",
    )
    remote = {**workflow("New"), "id": "remote-1"}
    monkeypatch.setattr(N8nClient, "list_all_workflows", lambda self: {"data": [remote]})
    response = client.post(f"/api/pull/{server_id}")
    assert response.status_code == 200
    assert response.json()["updated"] == 1
    assert len(db.list_workflows()) == 1
    assert db.get_workflow(existing_id)["name"] == "New"
    assert db.get_decisions(existing_id)[0]["action"] == "pull"


def test_pull_does_not_dedupe_identical_content_across_servers(api_client, monkeypatch):
    client, db = api_client
    first = db.add_server("first", "https://first.example", "key")
    second = db.add_server("second", "https://second.example", "key")
    remote = {**workflow("Same"), "id": "shared-id"}
    db.add_workflow(
        "Same", json.dumps(remote), server_id=first, n8n_id="shared-id", source="pull"
    )
    monkeypatch.setattr(N8nClient, "list_all_workflows", lambda self: {"data": [remote]})
    response = client.post(f"/api/pull/{second}")
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert len(db.list_workflows()) == 2


def test_push_preserves_independent_bindings_for_multiple_servers(api_client, monkeypatch):
    client, db = api_client
    first = db.add_server("first", "https://first.example", "key")
    second = db.add_server("second", "https://second.example", "key")
    workflow_id = db.add_workflow(
        "Move", json.dumps(workflow("Move")), server_id=first, n8n_id="old-id"
    )
    calls = []
    monkeypatch.setattr(
        N8nClient,
        "create_workflow",
        lambda self, data: calls.append("create") or {"id": "new-id"},
    )
    monkeypatch.setattr(
        N8nClient,
        "update_workflow",
        lambda self, remote_id, data: calls.append("update") or {"id": remote_id},
    )
    response = client.post(
        f"/api/export/{workflow_id}/to-server?server_id={second}&decision=Deploy"
    )
    assert response.status_code == 200
    assert calls == ["create"]
    bindings = {item["server_id"]: item["n8n_id"] for item in db.list_workflow_remotes(workflow_id)}
    assert bindings == {first: "old-id", second: "new-id"}
    response = client.post(
        f"/api/export/{workflow_id}/to-server?server_id={first}&decision=Redeploy"
    )
    assert response.status_code == 200
    assert calls == ["create", "update"]
    bindings = {item["server_id"]: item["n8n_id"] for item in db.list_workflow_remotes(workflow_id)}
    assert bindings == {first: "old-id", second: "new-id"}


def test_push_failure_is_sanitized_and_audited(api_client, monkeypatch):
    client, db = api_client
    server_id = db.add_server("remote", "https://n8n.example", "key", is_default=True)
    workflow_id = db.add_workflow("Fail", json.dumps(workflow("Fail")))
    monkeypatch.setattr(
        N8nClient,
        "create_workflow",
        lambda self, data: {"error": True, "detail": "upstream secret traceback"},
    )
    response = client.post(
        f"/api/export/{workflow_id}/to-server?server_id={server_id}&decision=Try+deploy"
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Push failed"
    assert "secret" not in response.text
    assert db.get_decisions(workflow_id)[0]["action"] == "push-failed"


def test_static_build_route_is_not_shadowed_by_integer_route(api_client):
    client, _ = api_client
    response = client.post(
        "/api/workflows/build",
        json={
            "name": "Built",
            "nodes": [{"type": "n8n-nodes-base.manualTrigger", "name": "Start"}],
            "connections": [],
            "decision": "Build test",
        },
    )
    assert response.status_code == 200


def test_viewer_escapes_stored_script_payload(api_client):
    client, db = api_client
    data = workflow("</script><script>window.PWN=1</script>")
    data["nodes"][0]["name"] = "</script><script>window.PWN=1</script>"
    workflow_id = db.add_workflow(data["name"], json.dumps(data))
    response = client.get(f"/viewer/{workflow_id}")
    assert response.status_code == 200
    assert "</script><script>window.PWN=1</script>" not in response.text
    assert "\\u003c/script\\u003e" in response.text


@pytest.mark.parametrize("host", ["bad host", "x;id", "x$(id)", "x`id`", "x/../../y", ""])
def test_ssh_helper_rejects_unsafe_hosts(host):
    with pytest.raises(ValueError):
        SSHHelper(host)


@pytest.mark.parametrize("user", ["bad user", "root;id", "$(id)", "a/b", ""])
def test_ssh_helper_rejects_unsafe_users(user):
    with pytest.raises(ValueError):
        SSHHelper("host.example", user=user)


def test_ssh_command_enforces_host_key_and_batch_mode():
    command = SSHHelper("host.example", user="deploy", port=2222)._ssh_cmd()
    assert "StrictHostKeyChecking=accept-new" in command
    assert "BatchMode=yes" in command
    assert "StrictHostKeyChecking=no" not in command
    assert command[-1] == "deploy@host.example"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Normal", "Normal"),
        ("two words", "two_words"),
        ("../../secret", "secret"),
        ("CON<>file", "CON_file"),
        ("ümlaut", "mlaut"),
        ("a/b\\c", "a_b_c"),
        ("...", "workflow"),
        ("", "workflow"),
    ],
)
def test_export_filename_is_confined(name, expected):
    assert _safe_filename(name) == expected
    assert "/" not in _safe_filename(name)
    assert "\\" not in _safe_filename(name)


def test_runtime_and_package_versions_match():
    metadata = (__import__("pathlib").Path(__file__).parents[1] / "pyproject.toml").read_text()
    assert f'version = "{__version__}"' in metadata


def test_container_contract_is_nonroot_persistent_and_loopback_published():
    root = __import__("pathlib").Path(__file__).parents[1]
    dockerfile = (root / "Dockerfile").read_text()
    compose = (root / "docker-compose.yml").read_text()
    assert "USER manager" in dockerfile
    assert 'VOLUME ["/config", "/data"]' in dockerfile
    assert "127.0.0.1:8100:8100" in compose
    assert "/config" in compose and "/data" in compose


def test_remote_n8n_container_is_pinned_and_loopback_only():
    source = (__import__("pathlib").Path(__file__).parents[1] / "n8nManager/setup/n8n_installer.py").read_text()
    assert "docker.n8n.io/n8nio/n8n:2.26.8" in source
    assert "-p 127.0.0.1:" in source
    assert "N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true" in source
    assert "curl -fsSL" not in source


def test_github_actions_are_pinned_to_full_commit_shas():
    root = __import__("pathlib").Path(__file__).parents[1]
    for workflow_file in (root / ".github/workflows").glob("*.yml"):
        for line in workflow_file.read_text().splitlines():
            if "uses:" not in line:
                continue
            reference = line.split("uses:", 1)[1].strip().split()[0]
            assert "@" in reference
            revision = reference.rsplit("@", 1)[1]
            assert len(revision) == 40
            assert all(char in "0123456789abcdef" for char in revision)


def test_json_export_is_atomic_on_serialization_failure(tmp_path, monkeypatch):
    from n8nManager.export import json_export

    target = tmp_path / "workflow.json"
    target.write_text("SENTINEL", encoding="utf-8")
    monkeypatch.setattr(json_export.json, "dump", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError):
        json_export.export_workflow_json(
            {"workflow_json": json.dumps(workflow()), "name": "Example"}, str(target)
        )
    assert target.read_text(encoding="utf-8") == "SENTINEL"
    assert list(tmp_path.glob(".workflow.json.*")) == []


def test_json_and_markdown_exports_end_with_newline(tmp_path):
    from n8nManager.export.json_export import export_workflow_json
    from n8nManager.export.markdown import export_workflow_markdown

    stored = {
        "workflow_json": json.dumps(workflow()),
        "name": "Example",
        "description": "",
        "trigger_type": "",
        "source": "local",
    }
    json_path = export_workflow_json(stored, str(tmp_path / "workflow.json"))
    md_path = export_workflow_markdown(stored, str(tmp_path / "workflow.md"))
    assert __import__("pathlib").Path(json_path).read_bytes().endswith(b"\n")
    assert __import__("pathlib").Path(md_path).read_bytes().endswith(b"\n")


def test_csp_headers_and_vendored_vis_network():
    from n8nManager.api.server import app
    client = TestClient(app, base_url="http://127.0.0.1")
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Content-Security-Policy" in resp.headers
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
    assert "X-Content-Type-Options" in resp.headers
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "/static/js/vis-network.min.js" in resp.text
    assert "unpkg.com" not in resp.text

    vis_resp = client.get("/static/js/vis-network.min.js")
    assert vis_resp.status_code == 200
    assert len(vis_resp.content) > 500000
