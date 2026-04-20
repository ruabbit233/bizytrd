import subprocess
import sys
from pathlib import Path


def test_bizytrd_imports_from_parent_source_layout():
    project_root = Path(__file__).resolve().parents[1]
    parent = project_root.parent

    script = f"""
import sys
sys.path = [{str(parent)!r}] + [
    path for path in sys.path
    if path not in {{'', {str(project_root)!r}, {str(parent)!r}}}
]
import bizytrd
classes, displays = bizytrd.get_node_mappings()
assert classes
assert displays
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
