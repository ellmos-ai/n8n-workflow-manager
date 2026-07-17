"""Configuration and runtime-path handling for n8n Workflow Manager."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

APP_NAME = "n8n-workflow-manager"
PACKAGE_DIR = Path(__file__).resolve().parent.parent
LEGACY_CONFIG_PATH = PACKAGE_DIR / "config.json"

DEFAULT_CONFIG = {
    "api_host": "127.0.0.1",
    "api_port": 8100,
    "cors_origins": [],
    "trusted_hosts": ["127.0.0.1", "localhost", "[::1]"],
    "default_server": None,
    "db_path": "n8n_manager.db",
    "n8n": {
        "api_version": "v1",
        "default_port": 5678,
    },
}


def get_config_dir() -> Path:
    """Return the per-user configuration directory without creating it."""
    override = os.environ.get("N8N_MANAGER_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return root / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / APP_NAME


def get_data_dir() -> Path:
    """Return the per-user data directory without creating it."""
    override = os.environ.get("N8N_MANAGER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / APP_NAME
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return root / APP_NAME


def get_config_path() -> Path:
    override = os.environ.get("N8N_MANAGER_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return get_config_dir() / "config.json"


def load_config(config_path=None) -> dict:
    """Load JSON configuration and merge it with safe defaults.

    A package-local configuration is read only as a compatibility fallback for
    older editable installs. New writes always go to the per-user path.
    """
    explicit_path = config_path is not None
    path = Path(config_path).expanduser() if explicit_path else get_config_path()
    if not path.exists() and not explicit_path and LEGACY_CONFIG_PATH.exists():
        path = LEGACY_CONFIG_PATH

    config = _deep_merge({}, DEFAULT_CONFIG)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                user_config = json.load(handle)
            if not isinstance(user_config, dict):
                raise ValueError("the configuration root must be an object")
            config = _deep_merge(config, user_config)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            print(f"[n8n-manager] Warning: configuration could not be loaded: {exc}")
    return config


def save_config(config: dict, config_path=None) -> Path:
    """Atomically save configuration outside the installed package."""
    path = Path(config_path).expanduser() if config_path else get_config_path()
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(config, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        _restrict_permissions(path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path


def get_db_path(config=None) -> Path:
    """Return the database path, resolving relative paths inside user data."""
    config = load_config() if config is None else config
    value = config.get("db_path", DEFAULT_CONFIG["db_path"])
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = get_data_dir() / path
    return path.resolve()


def get_export_dir() -> Path:
    return (get_data_dir() / "exports").resolve()


def _restrict_permissions(path: Path) -> None:
    if os.name != "nt":
        try:
            path.chmod(0o600)
        except OSError:
            pass


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge dictionaries without mutating either input."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
