"""Erlaubt: python -m n8nManager"""
import sys
from pathlib import Path
_parent = str(Path(__file__).resolve().parent.parent)
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from n8nManager.n8n_manager import main  # noqa: E402
sys.exit(main())
