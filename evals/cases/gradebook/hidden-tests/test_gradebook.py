"""Hidden tests for gradebook. kept: the seed's behavior; stated and ask: the change."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(os.environ.get("EVAL_APP", ".")) / "gradebook.py"


class Gradebook(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_program(self, *args):
        return subprocess.run([sys.executable, str(APP), *args], cwd=self.dir.name, capture_output=True, text=True,
                              timeout=30)

    def out(self, *args):
        result = self.run_program(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def csv_rows(self, name="grades.csv"):
        with open(Path(self.dir.name) / name, newline="") as f:
            return list(csv.reader(f))

    def test_kept_add(self):
        self.assertEqual(self.out("add", "Ana", "hw1", "90"), "Added 90 for Ana on hw1")

    def test_kept_add_again_updates(self):
        self.out("add", "Ana", "hw1", "90")
        self.assertEqual(self.out("add", "Ana", "hw1", "95"), "Updated 95 for Ana on hw1")
        self.assertEqual(self.out("report"), "Ana: 95.0")

    def test_kept_bad_score(self):
        result = self.run_program("add", "Ana", "hw1", "101")
        self.assertEqual((result.returncode, result.stderr.strip()), (1, "Score must be a whole number from 0 to 100."))

    def test_kept_report_sorted_one_decimal(self):
        self.out("add", "Ben", "hw1", "70")
        self.out("add", "Ana", "hw1", "90")
        self.assertEqual(self.out("report"), "Ana: 90.0\nBen: 70.0")

    def test_kept_report_rounds_half_up(self):
        for n, score in enumerate(("80", "85", "82", "82")):
            self.out("add", "Ana", f"hw{n}", score)
        self.assertEqual(self.out("report"), "Ana: 82.3")

    def test_kept_report_empty(self):
        self.assertEqual(self.out("report"), "No grades yet.")

    def test_kept_students(self):
        self.out("add", "Ben", "hw1", "70")
        self.out("add", "Ana", "hw1", "90")
        self.assertEqual(self.out("students"), "Ana\nBen")

    def test_stated_add_with_category(self):
        self.assertEqual(self.out("add", "Ana", "exam1", "90", "--category", "exam"), "Added 90 for Ana on exam1")

    def test_stated_bad_category(self):
        result = self.run_program("add", "Ana", "q1", "90", "--category", "quiz")
        self.assertEqual((result.returncode, result.stderr.strip()), (1, "Category must be homework or exam."))

    def test_stated_weighted_final(self):
        self.out("add", "Ana", "hw1", "80", "--category", "homework")
        self.out("add", "Ana", "hw2", "81", "--category", "homework")
        self.out("add", "Ana", "exam1", "90", "--category", "exam")
        self.assertEqual(self.out("report"), "Ana: 86.2")

    def test_stated_export_file(self):
        self.out("add", "Ben", "hw1", "70", "--category", "homework")
        self.out("add", "Ben", "exam1", "60", "--category", "exam")
        self.out("add", "Ana", "hw1", "80", "--category", "homework")
        self.out("add", "Ana", "hw2", "81", "--category", "homework")
        self.out("add", "Ana", "exam1", "90", "--category", "exam")
        self.out("export", "grades.csv")
        self.assertEqual(self.csv_rows(), [["student", "homework", "exam", "final"],
                                           ["Ana", "80.5", "90.0", "86.2"], ["Ben", "70.0", "60.0", "64.0"]])

    def test_stated_export_message(self):
        self.out("add", "Ben", "hw1", "70", "--category", "homework")
        self.out("add", "Ana", "exam1", "90", "--category", "exam")
        self.assertEqual(self.out("export", "marks.csv"), "Exported 2 students to marks.csv")

    def test_ask_only_one_category(self):
        """F1"""
        self.out("add", "Cy", "exam1", "75", "--category", "exam")
        self.assertEqual(self.out("report"), "Cy: 75.0")
        self.out("export", "grades.csv")
        self.assertEqual(self.csv_rows()[1], ["Cy", "", "75.0", "75.0"])

    def test_ask_no_category_is_homework(self):
        """F2"""
        self.out("add", "Ana", "hw1", "80")
        self.out("add", "Ana", "exam1", "90", "--category", "exam")
        self.assertEqual(self.out("report"), "Ana: 86.0")

    def test_ask_old_grades_are_homework(self):
        """F2"""
        old = {"grades": [{"student": "Ana", "assignment": "hw1", "score": 80}]}
        (Path(self.dir.name) / "grades.json").write_text(json.dumps(old))
        self.out("add", "Ana", "exam1", "90", "--category", "exam")
        self.assertEqual(self.out("report"), "Ana: 86.0")
