import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROGRAM = Path(__file__).resolve().parent.parent / "gradebook.py"


class GradebookTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_program(self, *args):
        return subprocess.run([sys.executable, str(PROGRAM), *args], cwd=self.dir.name, capture_output=True,
                              text=True)

    def out(self, *args):
        result = self.run_program(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_add(self):
        self.assertEqual(self.out("add", "Ana", "hw1", "90"), "Added 90 for Ana on hw1")

    def test_add_again_updates(self):
        self.out("add", "Ana", "hw1", "90")
        self.assertEqual(self.out("add", "Ana", "hw1", "95"), "Updated 95 for Ana on hw1")
        self.assertEqual(self.out("report"), "Ana: 95.0")

    def test_bad_score(self):
        result = self.run_program("add", "Ana", "hw1", "101")
        self.assertEqual((result.returncode, result.stderr.strip()), (1, "Score must be a whole number from 0 to 100."))

    def test_report_sorted_one_decimal(self):
        self.out("add", "Ben", "hw1", "70")
        self.out("add", "Ana", "hw1", "90")
        self.assertEqual(self.out("report"), "Ana: 90.0\nBen: 70.0")

    def test_report_rounds_half_up(self):
        for n, score in enumerate(("80", "85", "82", "82")):
            self.out("add", "Ana", f"hw{n}", score)
        self.assertEqual(self.out("report"), "Ana: 82.3")

    def test_report_empty(self):
        self.assertEqual(self.out("report"), "No grades yet.")

    def test_students(self):
        self.out("add", "Ben", "hw1", "70")
        self.out("add", "Ana", "hw1", "90")
        self.assertEqual(self.out("students"), "Ana\nBen")


if __name__ == "__main__":
    unittest.main()
