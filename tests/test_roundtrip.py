"""End-to-end: synthetic ACCDB -> inspect -> export -> assess -> load-sqlite -> reconcile.

Needs Java (javac) and, on the first run, network access to fetch the pinned Jackcess JAR
(or ACCESS_FIELDKIT_JACKCESS_JAR pointing at a verified local copy). Run: python -m unittest discover -s tests
"""
import hashlib
import json
import os
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from access_fieldkit.runtime import java_classpath

FIXTURES = Path(__file__).parent / "fixtures"
JAR = os.environ.get("ACCESS_FIELDKIT_JACKCESS_JAR") or None


def cli(*args):
    extra = ["--jackcess-jar", JAR] if JAR else []
    return subprocess.run([sys.executable, "-m", "access_fieldkit", *extra, *args],
                          check=True, capture_output=True, text=True)


class RoundTrip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.work = Path(cls.tmp.name)
        classpath = java_classpath(JAR)
        jackcess = classpath.split(os.pathsep)[-1]
        build = cls.work / "fixture-classes"
        build.mkdir()
        subprocess.run(["javac", "-encoding", "UTF-8", "-cp", jackcess, "-d", str(build),
                        str(FIXTURES / "MakeSample.java")], check=True)
        cls.source = cls.work / "sample.accdb"
        subprocess.run(["java", "-cp", os.pathsep.join((str(build), jackcess)), "MakeSample",
                        str(cls.source)], check=True)
        cls.source_sha = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pipeline(self):
        cli("inspect", str(self.source), "--out", str(self.work / "inventory"))
        inventory = json.loads((self.work / "inventory" / "manifest.json").read_text(encoding="utf-8"))
        names = {t["name"] for t in inventory["tables"]}
        self.assertEqual(names, {"Klanten", "Import log"})
        self.assertFalse(any((self.work / "inventory").glob("table-*.jsonl")), "inspect must not export rows")

        export = self.work / "export"
        cli("export", str(self.source), "--out", str(export))
        manifest = json.loads((export / "manifest.json").read_text(encoding="utf-8"))
        rows = {t["name"]: t["rows"] for t in manifest["tables"]}
        self.assertEqual(rows, {"Klanten": 3, "Import log": 3}, "duplicates in a keyless table must be kept")

        cli("assess", str(export), "--out", str(self.work / "assessment.md"))
        self.assertIn("Import log", (self.work / "assessment.md").read_text(encoding="utf-8"))

        landing = self.work / "landing.sqlite"
        cli("load-sqlite", str(export), str(landing))
        result = cli("reconcile", str(export), str(landing))
        self.assertEqual(result.returncode, 0)

        with closing(sqlite3.connect(landing)) as db, db:
            saldo = [r[0] for r in db.execute('SELECT "Saldo" FROM "Klanten" ORDER BY "ID"')]
            gemeente = [r[0] for r in db.execute('SELECT "Gemeente" FROM "Klanten" ORDER BY "ID"')]
        self.assertEqual(saldo[:2], ["1234.5678", "-0.0001"], "Currency must keep four decimals exactly")
        self.assertEqual(gemeente, ["Liège", "", None], "NULL and empty text must stay different")

        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_sha,
                         "the source file must not change")

    def test_reconcile_catches_a_changed_value(self):
        export = self.work / "export-tamper"
        cli("export", str(self.source), "--out", str(export))
        landing = self.work / "tamper.sqlite"
        cli("load-sqlite", str(export), str(landing))
        with closing(sqlite3.connect(landing)) as db, db:
            db.execute('UPDATE "Klanten" SET "Saldo" = \'1234.5600\' WHERE "Naam" = \'Voorbeeld BV\'')
        with self.assertRaises(subprocess.CalledProcessError):
            cli("reconcile", str(export), str(landing))


if __name__ == "__main__":
    unittest.main()
