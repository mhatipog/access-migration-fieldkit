"""Reconciliation regression tests independent of Java or a real Access file."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from access_fieldkit.landing import load, reconcile


class ReconcileSchema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        data = b'["alpha", 7]\n'
        (self.folder / "table-0001.jsonl").write_bytes(data)
        manifest = {
            "format": "access-fieldkit-v1", "exported": True,
            "file_sha256": "0" * 64,
            "tables": [{
                "name": "Source table",
                "columns": [{"name": "Label", "type": "TEXT"},
                            {"name": "Amount", "type": "LONG"}],
                "rows": 1, "data_file": "table-0001.jsonl",
                "sha256": hashlib.sha256(data).hexdigest(),
            }],
        }
        (self.folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.target = self.folder / "landing.sqlite"
        load(self.folder, self.target)

    def change(self, sql):
        with closing(sqlite3.connect(self.target)) as db, db:
            db.execute(sql)

    def test_unchanged_landing_passes(self):
        self.assertTrue(reconcile(self.folder, self.target)["valid"])

    def test_extra_column_is_not_ignored(self):
        self.change('ALTER TABLE "Source table" ADD COLUMN "Extra" TEXT')
        result = reconcile(self.folder, self.target)
        self.assertFalse(result["valid"])
        self.assertTrue(any("column schema" in issue for issue in result["issues"]))

    def test_renamed_column_is_not_compared_by_position(self):
        self.change('ALTER TABLE "Source table" RENAME COLUMN "Label" TO "Renamed"')
        result = reconcile(self.folder, self.target)
        self.assertFalse(result["valid"])
        self.assertTrue(any("column schema" in issue for issue in result["issues"]))

    def test_extra_physical_table_is_not_ignored(self):
        self.change('CREATE TABLE unexpected (id INTEGER)')
        result = reconcile(self.folder, self.target)
        self.assertFalse(result["valid"])
        self.assertTrue(any("Physical table inventory" in issue for issue in result["issues"]))

    def test_missing_physical_table_is_detected(self):
        self.change('DROP TABLE "Source table"')
        self.assertFalse(reconcile(self.folder, self.target)["valid"])

    def test_uri_reserved_characters_in_filename(self):
        target = self.folder / "landing #100% test.sqlite"
        load(self.folder, target)
        self.assertTrue(reconcile(self.folder, target)["valid"])


if __name__ == "__main__":
    unittest.main()
