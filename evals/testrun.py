"""Run a case's hidden tests against one program and print one JSON result per test.

Usage: python3 testrun.py <hidden-tests dir> <app dir>

Runs as its own process, so a hanging or crashing program cannot take the harness down. The tests find the program
through EVAL_APP. A test's tag is the word after test_ (stated, ask or kept); the brief facts it checks are the F<n>
ids in its docstring. A test file that fails to import shows as an untagged error: a broken case.
"""
import json
import os
import re
import sys
import traceback
import unittest

TAGS = ("stated", "ask", "kept")


class Collect(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.rows = []

    def _row(self, test, outcome, detail=""):
        name = test.id().rsplit(".", 1)[-1]
        tag = name.split("_")[1] if name.count("_") >= 2 else "untagged"
        doc = test._testMethodDoc or ""
        self.rows.append({"test": test.id(), "tag": tag if tag in TAGS else "untagged",
                          "facts": re.findall(r"\bF\d+\b", doc), "outcome": outcome, "detail": detail[-1500:]})

    def addSuccess(self, test):
        self._row(test, "pass")

    def addFailure(self, test, err):
        self._row(test, "fail", _trace(err))

    def addError(self, test, err):
        self._row(test, "error", _trace(err))

    def addSkip(self, test, reason):
        self._row(test, "skip", reason)


def _trace(err) -> str:
    return "".join(traceback.format_exception(*err))


def main(tests: str, app: str) -> None:
    os.environ["EVAL_APP"] = os.path.abspath(app)
    suite = unittest.defaultTestLoader.discover(tests, top_level_dir=tests)
    result = Collect()
    suite.run(result)
    print(json.dumps(result.rows))


if __name__ == "__main__":
    main(*sys.argv[1:3])
