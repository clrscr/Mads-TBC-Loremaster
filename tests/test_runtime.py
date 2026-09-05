"""Runtime tests are independent of the optional Questie source checkout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def test_runtime_behavior(self):
        lua = os.environ.get("LUA") or shutil.which("lua5.1") or shutil.which("lua")
        if not lua:
            self.skipTest("Supply a Lua 5.1 executable with LUA=/path/to/lua")
        result = subprocess.run([lua, str(ROOT / "tests/runtime_spec.lua"), str(ROOT)],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_all_toc_paths_exist_with_exact_case(self):
        for line in (ROOT / "Mads_TBCLoremaster.toc").read_text().splitlines():
            if line and not line.startswith("#"):
                path = ROOT
                for component in line.replace("\\", "/").split("/"):
                    self.assertIn(component, [p.name for p in path.iterdir()], line)
                    path /= component
                self.assertTrue(path.is_file(), line)

    def test_every_source_row_has_a_coverage_decision(self):
        audit = json.loads((ROOT / "data/evidence/runtime-coverage.json").read_text())
        self.assertEqual(len(audit["records"]), audit["sourceRows"])
        self.assertEqual(len({r["id"] for r in audit["records"]}), audit["sourceRows"])
        self.assertEqual(sum(audit["counts"].values()), audit["sourceRows"])
        for row in audit["records"]:
            self.assertIn(row["status"], ("included", "excluded"))
            if row["status"] == "excluded":
                self.assertTrue(row["reason"])
