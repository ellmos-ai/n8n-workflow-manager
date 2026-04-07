<img src="assets/n8n_workflow_manager_logo.jpg" alt="n8n Workflow Manager banner" width="350">

# n8n Workflow Manager

**🇩🇪 [Deutsche Version](README_de.md)**

*Part of the [ellmos-ai](https://github.com/ellmos-ai) family.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)

**The only open-source n8n workflow manager with a visual graph viewer, REST API, and multi-server sync -- all in one Python package.**

> Manage, visualize, and sync n8n workflows across multiple servers from a single dashboard.

## Screenshots

*Screenshots coming soon. Start the server with `n8n-manager serve` and open http://localhost:8100 to see the dashboard, workflow viewer, and editor.*

## Features

- **Visual Workflow Viewer** -- Interactive graph visualization powered by vis.js. Zoom, pan, click nodes for details.
- **Web Dashboard** -- Overview of all workflows with status, tags, and quick actions.
- **Workflow Editor** -- Add, connect, and configure nodes in-browser with drag-and-drop.
- **Multi-Server Management** -- Connect to multiple n8n instances. Push/pull workflows between them.
- **REST API + Swagger** -- Full CRUD API with auto-generated documentation at `/docs`.
- **CLI** -- Manage workflows from the terminal: import, export, push, pull, list, and more.
- **Duplicate Detection** -- Content-hash based deduplication prevents importing the same workflow twice.
- **Version History** -- Track changes to workflows over time with automatic versioning.
- **Workflow Builder API** -- Programmatically create workflows via POST request (great for AI agents).
- **Remote n8n Setup** -- Install n8n on remote servers via SSH + Docker with a single command.
- **JSON + Markdown Export** -- Export workflows as clean JSON or human-readable Markdown documentation.
- **Workflow Templates** -- Pre-built templates for common automation patterns.

## Quick Start

### Installation

```bash
pip install n8n-workflow-manager
```

Or from source:

```bash
git clone https://github.com/lukisch/n8n-workflow-manager.git
cd n8n-workflow-manager
pip install -e .
```

### Usage

```bash
# Start the web UI + API server
n8n-manager serve

# Open in browser: http://localhost:8100
# Swagger API docs: http://localhost:8100/docs
```

### CLI Examples

```bash
# Import a workflow from JSON file
n8n-manager import my-workflow.json

# List all workflows
n8n-manager list

# Export as Markdown documentation
n8n-manager export 1 --format md

# Add an n8n server
n8n-manager servers --add production https://n8n.example.com:5678 YOUR_API_KEY --default

# Push workflow to server
n8n-manager push 1

# Pull all workflows from server
n8n-manager pull

# Check system status
n8n-manager status

# Install n8n on a remote server
n8n-manager setup --host 1.2.3.4 --ssh-key ~/.ssh/id_ed25519
```

### Docker

```bash
docker-compose up -d
# Open http://localhost:8100
```

## API for AI Agents

The `/api/workflows/build` endpoint allows programmatic workflow creation:

```bash
curl -X POST http://localhost:8100/api/workflows/build \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Workflow",
    "nodes": [
      {"type": "n8n-nodes-base.webhook", "name": "Trigger", "parameters": {"path": "/hook"}},
      {"type": "n8n-nodes-base.httpRequest", "name": "Fetch", "parameters": {"url": "https://api.example.com"}}
    ],
    "connections": [{"from_node": "Trigger", "to_node": "Fetch"}]
  }'
```

Full API documentation available at `/docs` (Swagger UI) when the server is running.

## Architecture

```
n8n-workflow-manager/
├── core/           # Config, Database, Parser, n8n Client, Builder
├── api/            # FastAPI server + REST routes
├── web/            # Jinja2 templates + vis.js frontend
├── setup/          # SSH helper + n8n Docker installer
├── export/         # JSON, Markdown export
├── templates/      # Pre-built workflow templates
├── data/           # SQLite database (auto-created)
└── docs/           # Documentation
```

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.10+ / FastAPI / Uvicorn |
| Frontend | Jinja2 / vis.js (CDN) / Vanilla JS |
| Database | SQLite (WAL mode) |
| n8n Client | httpx |
| Remote Setup | SSH + Docker |

### Node Color Coding

| Color | Category | Examples |
|-------|----------|----------|
| Orange | Trigger | Webhook, Schedule, Manual |
| Blue | Processing | HTTP Request, Code, Set |
| Yellow | Logic | IF, Switch, Merge |
| Purple | AI | LangChain Agent, LLM Chain |
| Green | Action | Email, Slack, Telegram |

## Configuration

```bash
# Show current config
n8n-manager config --show

# Change API port
n8n-manager config --set api_port 9000
```

Configuration is stored in `config.json`. Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `api_port` | 8100 | Web UI / API port |
| `db_path` | `data/n8n_manager.db` | SQLite database path |
| `default_server` | null | Default n8n server name |

## Remote n8n Setup

Install n8n on any Linux server with Docker:

```bash
n8n-manager setup --host your-server-ip --ssh-key ~/.ssh/id_ed25519

# After installation:
# 1. Open http://your-server-ip:5678 in browser
# 2. Create n8n account
# 3. Go to Settings > API > Create API Key
# 4. Register in n8n-manager:
n8n-manager servers --add myserver http://your-server-ip:5678 YOUR_API_KEY --default
```

## MCP Server

An MCP (Model Context Protocol) server is available as a separate package for AI-powered workflow management:

```bash
npm install -g n8n-manager-mcp
```

See [n8n-manager-mcp](https://github.com/lukisch/n8n-manager-mcp) for details.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [n8n](https://n8n.io/) -- The workflow automation platform
- [vis.js](https://visjs.org/) -- Network visualization library
- [FastAPI](https://fastapi.tiangolo.com/) -- Modern Python web framework
