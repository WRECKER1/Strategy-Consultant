"""Register the orgfit connector with the Claude desktop app (Windows and macOS).

Run once, from the repository folder, with the virtual environment active:
    python mcp_server\\install_windows.py

It adds an "orgfit" entry to the desktop app's claude_desktop_config.json,
keeps every other entry, and saves a backup first. Then quit Claude fully
(system tray → Quit) and reopen it.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def config_path() -> Path:
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def main() -> int:
    if not (REPO / ".venv").exists() and "VIRTUAL_ENV" not in os.environ:
        print("Warning: no virtual environment detected. Activate .venv first so the connector uses the right packages.")
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if p.exists():
        shutil.copy(p, p.with_suffix(".json.bak"))
        cfg = json.loads(p.read_text(encoding="utf-8") or "{}")
    cfg.setdefault("mcpServers", {})["orgfit"] = {
        "command": sys.executable,
        "args": [str(REPO / "mcp_server" / "server.py")],
        "env": {"PYTHONIOENCODING": "utf-8"},
    }
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Registered 'orgfit' in {p}")
    print(f"  python: {sys.executable}")
    print(f"  server: {REPO / 'mcp_server' / 'server.py'}")
    print("Now quit the Claude desktop app completely (system tray icon → Quit) and open it again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
