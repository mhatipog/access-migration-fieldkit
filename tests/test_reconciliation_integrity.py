"""Reconciliation regressions using synthetic JSONL; no Java or network required."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from access_fieldkit.landing import load, reconcile


class ReconciliationIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / "export"
        self.folder.mkdir()
        self.data = self.folder / "table-0001.jsonl"
        self.data.write_bytes(b'["hello","world"]\n')
        self.manifest_path = self.folder / "manifest.json"
        self.manifest = {
            "format": "access-fieldkit-v1",
            "exported": True,
            "file_sha256": "synthetic-fixture",
            "tables": [{
                "name": "Odd table",
                "columns": [{"name": "A", "type": "TEXT"}, {"name": "B", "type": "TEXT"}],
                "data_file": self.data.name,
                "sha256": hashlib.sha256(self.data.read_bytes()).hexdigest(),
                "rows": 1,
            }],
        }
        self.write_manifest()
        self.target = Path(self.tmp.name) / "landing.sqlite"
        load(self.folder, self.target)

    def write_manifest(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def execute(self, sql, args=()):
        with closing(sqlite3.connect(self.target)) as db, db:
            db.execute(sql, args)

    def assert_invalid(self, fragment):
        result = reconcile(self.folder, self.target)
        self.assertFalse(result["valid"], result)
        self.assertTrue(any(fragment in item for item in result["issues"]), result)

    def test_unchanged_landing(self):
        self.assertTrue(reconcile(self.folder, self.target)["valid"])

    def test_dropped_trailing_column(self):
        self.execute('ALTER TABLE "Odd table" DROP COLUMN "B"')
        self.assert_invalid("column schema")

    def test_renamed_column(self):
        self.execute('ALTER TABLE "Odd table" RENAME COLUMN "B" TO "Different"')
        self.assert_invalid("column schema")

    def test_added_column(self):
        self.execute('ALTER TABLE "Odd table" ADD COLUMN "Unexpected" TEXT')
        self.assert_invalid("column schema")

    def test_extra_source_record_beyond_manifest_count(self):
        # Even matching file checksums and declared counts cannot excuse an
        # unconsumed source record. Keep both fingerprints internally consistent.
        self.data.write_bytes(self.data.read_bytes() + b'["extra","record"]\n')
        digest = hashlib.sha256(self.data.read_bytes()).hexdigest()
        self.manifest["tables"][0]["sha256"] = digest
        self.write_manifest()
        self.execute("UPDATE _af_metadata SET sha256 = ?", (digest,))
        self.assert_invalid("row streams differ")

    def test_uri_special_character_in_read_only_target(self):
        special = self.target.with_name("landing # fragment.sqlite")
        self.target.rename(special)
        before = set(special.parent.iterdir())
        self.assertTrue(reconcile(self.folder, special)["valid"])
        self.assertEqual(set(special.parent.iterdir()), before)


if __name__ == "__main__":
    unittest.main()
