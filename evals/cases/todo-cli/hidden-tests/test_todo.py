"""Hidden tests for todo-cli. Each test runs the program in a fresh empty folder, as separate processes."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

APP = Path(os.environ.get("EVAL_APP", ".")) / "todo.py"


class Todo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def run_todo(self, *args):
        return subprocess.run([sys.executable, str(APP), *args], cwd=self.dir.name, capture_output=True, text=True,
                              timeout=30)

    def out(self, *args):
        result = self.run_todo(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def test_stated_add_prints_number_and_text(self):
        self.assertEqual(self.out("add", "buy", "more", "flour"), "Added 1: buy more flour")

    def test_stated_numbers_go_up(self):
        self.out("add", "a")
        self.assertEqual(self.out("add", "b"), "Added 2: b")

    def test_stated_empty_list(self):
        self.assertEqual(self.out("list"), "Nothing to do.")

    def test_stated_list_format(self):
        self.out("add", "buy flour")
        self.out("add", "clean oven")
        self.assertEqual(self.out("list"), "1. [ ] buy flour\n2. [ ] clean oven")

    def test_stated_done_prints(self):
        self.out("add", "buy flour")
        self.assertEqual(self.out("done", "1"), "Done 1: buy flour")

    def test_stated_done_item_marked_with_x(self):
        self.out("add", "buy flour")
        self.out("done", "1")
        self.assertEqual(self.out("list"), "1. [x] buy flour")

    def test_stated_saved_in_todo_json_in_the_folder(self):
        self.out("add", "buy flour")
        self.assertTrue((Path(self.dir.name) / "todo.json").is_file())

    def test_stated_remove_prints(self):
        self.out("add", "buy flour")
        self.assertEqual(self.out("remove", "1"), "Removed 1: buy flour")

    def test_stated_removed_item_not_listed(self):
        self.out("add", "a")
        self.out("add", "b")
        self.out("remove", "1")
        self.assertEqual(self.out("list"), "2. [ ] b")

    def test_stated_numbers_never_reused(self):
        self.out("add", "a")
        self.out("add", "b")
        self.out("remove", "2")
        self.assertEqual(self.out("add", "c"), "Added 3: c")

    def test_stated_done_unknown_number(self):
        result = self.run_todo("done", "7")
        self.assertEqual((result.returncode, result.stderr.strip()), (1, "No item 7."))

    def test_stated_remove_unknown_number(self):
        self.out("add", "a")
        result = self.run_todo("remove", "7")
        self.assertEqual((result.returncode, result.stderr.strip()), (1, "No item 7."))

    def test_ask_restore_prints(self):
        """F1"""
        self.out("add", "buy flour")
        self.out("remove", "1")
        self.assertEqual(self.out("restore", "1"), "Restored 1: buy flour")

    def test_ask_restore_keeps_number_and_state(self):
        """F1"""
        self.out("add", "a")
        self.out("add", "b")
        self.out("done", "1")
        self.out("remove", "1")
        self.out("restore", "1")
        self.assertEqual(self.out("list"), "2. [ ] b\n1. [x] a")

    def test_ask_open_items_first(self):
        """F2"""
        for text in ("a", "b", "c", "d"):
            self.out("add", text)
        self.out("done", "1")
        self.out("done", "3")
        self.assertEqual(self.out("list"), "2. [ ] b\n4. [ ] d\n1. [x] a\n3. [x] c")

    def test_ask_restore_not_removed(self):
        """F3"""
        self.out("add", "a")
        result = self.run_todo("restore", "1")
        self.assertEqual((result.returncode, result.stderr.strip()), (1, "No removed item 1."))
