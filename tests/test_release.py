import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from mads_loremaster.guides import ADDON_NAME, toc_all_lua_files
from mads_loremaster.reports import build_zip, release_archive_name, write_release_metadata

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_wowup_archive_and_metadata_match_final_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = build_zip(ROOT, Path(directory) / release_archive_name(ROOT))
            metadata = json.loads(write_release_metadata(ROOT, archive).read_text())
            release = metadata["releases"][0]
            self.assertEqual(release["filename"], archive.name)
            self.assertTrue(archive.name.endswith("-bcc.zip"))
            self.assertIs(release["nolib"], False)
            self.assertEqual(release["metadata"], [{"flavor": "bcc", "interface": 20506}])
            with zipfile.ZipFile(archive) as package:
                self.assertIsNone(package.testzip())
                self.assertEqual({name.split("/")[0] for name in package.namelist()}, {ADDON_NAME})
                self.assertIn(f"{ADDON_NAME}/{ADDON_NAME}.toc", package.namelist())
                for source in toc_all_lua_files(ROOT):
                    self.assertEqual(package.read(f"{ADDON_NAME}/{source.relative_to(ROOT).as_posix()}"), source.read_bytes())
                for name in package.namelist():
                    self.assertNotIn("/.git/", name)
                    self.assertNotIn("/tests/", name)
                    self.assertNotIn("/WTF/", name)
