from pathlib import Path
import unittest


class TaskModuleCleanupTests(unittest.TestCase):
    def test_legacy_core_task_module_has_been_removed(self):
        project_root = Path(__file__).resolve().parents[1]

        self.assertFalse((project_root / "core" / "task.py").exists())
