"""The desktop extension bundle (mcpb/) must match the package version."""
import json
import re
from pathlib import Path

import mathguard

ROOT = Path(__file__).resolve().parents[1]


def test_mcpb_versions_match_package():
    manifest = json.loads((ROOT / "mcpb" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == mathguard.__version__
    pyproject = (ROOT / "mcpb" / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{mathguard.__version__}"' in pyproject
    assert re.search(rf'"mathguard=={re.escape(mathguard.__version__)}"', pyproject)


def test_mcpb_tools_exist_in_server():
    manifest = json.loads((ROOT / "mcpb" / "manifest.json").read_text(encoding="utf-8"))
    source = (ROOT / "src" / "mathguard" / "mcp_server.py").read_text(encoding="utf-8")
    for tool in manifest["tools"]:
        assert f"def {tool['name']}(" in source
