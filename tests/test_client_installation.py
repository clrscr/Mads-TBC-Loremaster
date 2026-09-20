import json
from pathlib import Path
import tempfile
import unittest

from mads_loremaster.client_installation import inspect_client_installation


class QuestieInstallationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "config").mkdir()
        self.questie = self.root / "client/Interface/AddOns/Questie"
        self.questie.mkdir(parents=True)
        (self.root / "Mads_TBCLoremaster.toc").write_text("## Interface: 20506\n")
        build_info = self.root / "build.info"
        build_info.write_text("Product!STRING:0|Version!STRING:0\nwow_anniversary|2.5.6\n")
        (self.root / "config/client_installation.json").write_text(json.dumps({
            "client_root": str(self.root / "client"), "build_info": str(build_info),
            "product": "wow_anniversary", "expected_version": "2.5.6",
            "expected_interface": "20506",
            # Older configuration must not reintroduce a version requirement.
            "questie_version": "old-release",
        }))

    def write_toc(self, version, interface="20506"):
        (self.questie / "Questie-BCC.toc").write_text(
            f"## Interface: {interface}\n## Version: {version}\n")

    def test_versions_and_data_updates_do_not_gate_installation(self):
        for version in ("11.32.1", "11.38.0", "future-release"):
            with self.subTest(version=version):
                self.write_toc(version)
                (self.questie / "Database").mkdir(exist_ok=True)
                (self.questie / "Database/updated.lua").write_text(version)
                result = inspect_client_installation(self.root)
                self.assertTrue(all(result["checks"].values()))
                self.assertEqual(result["dependencies"]["Questie"]["Version"], version)
                self.assertNotIn("questie_version", result["checks"])
                self.assertNotIn("questie_source_parity", result["checks"])
                # No source checkout/config is needed to inspect an installation.
                self.assertEqual(result["status"], "runtime_not_deployed")

    def test_missing_or_wrong_client_dependency_still_fails(self):
        result = inspect_client_installation(self.root)
        self.assertFalse(result["checks"]["questie_installed"])
        self.assertFalse(result["checks"]["questie_interface"])
        self.write_toc("new-release", "11508")
        result = inspect_client_installation(self.root)
        self.assertTrue(result["checks"]["questie_installed"])
        self.assertFalse(result["checks"]["questie_interface"])

    def test_multi_interface_declaration_accepts_target_client(self):
        self.write_toc("new-release", "20505, 20506")
        self.assertTrue(inspect_client_installation(self.root)["checks"]["questie_interface"])
