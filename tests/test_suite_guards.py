"""Guards on the test suite itself, not on switchdeck.py.

Standard library only: this file never imports switchdeck, so it needs no
rumps. Run it with the rest of the suite from the repo root:

    ~/.switchdeck-venv/bin/python -m unittest discover -s tests -v

test_readme_states_the_count_the_suite_runs keeps the README's test count
(the tests badge and the Features line) equal to what the suite runs, so
adding or removing a test without updating the README fails here.

test_no_duplicate_class_or_test_names catches what the count cannot: a
second class with the same name replaces the first, and its tests vanish
from the run and from the count alike (205a60b hid five tests that way).
"""
import ast
import glob
import os
import re
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
README = os.path.join(os.path.dirname(HERE), "README.md")

BADGE_RE = re.compile(r"badge/tests-(\d+)%20unittest")
FEATURES_RE = re.compile(r"\(`tests/`, (\d+) cases\)")


def duplicate_names(paths):
    """Problems found in the given test files, as strings: a top-level class
    name defined twice (in one file or across files), or a test method name
    defined twice in one class. Empty when there is none."""
    problems = []
    seen_classes = {}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        name = os.path.basename(path)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            where = "%s:%d" % (name, node.lineno)
            if node.name in seen_classes:
                problems.append("class %s at %s and %s"
                                % (node.name, seen_classes[node.name], where))
            else:
                seen_classes[node.name] = where
            seen_tests = {}
            for item in node.body:
                if (isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name.startswith("test")):
                    if item.name in seen_tests:
                        problems.append("test %s.%s at %s:%d and %s:%d" % (
                            node.name, item.name, name, seen_tests[item.name],
                            name, item.lineno))
                    else:
                        seen_tests[item.name] = item.lineno
    return problems


class SuiteGuards(unittest.TestCase):
    def test_no_duplicate_class_or_test_names(self):
        paths = sorted(glob.glob(os.path.join(HERE, "*.py")))
        self.assertTrue(paths, "no test files found")
        self.assertEqual(duplicate_names(paths), [])

    def test_detector_catches_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            a = os.path.join(d, "test_a.py")
            b = os.path.join(d, "test_b.py")
            with open(a, "w", encoding="utf-8") as f:
                f.write("class Once:\n"
                        "    def test_x(self): pass\n"
                        "    def test_x(self): pass\n"
                        "    def helper(self): pass\n"
                        "    def helper(self): pass\n")
            with open(b, "w", encoding="utf-8") as f:
                f.write("class Once:\n"
                        "    def test_y(self): pass\n")
            problems = duplicate_names([a, b])
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(problems[0].startswith("test Once.test_x"), problems)
        self.assertTrue(problems[1].startswith("class Once"), problems)

    def test_readme_states_the_count_the_suite_runs(self):
        # A fresh loader: defaultTestLoader carries the -k patterns of the
        # outer run, which would shrink the count.
        loader = unittest.TestLoader()
        suite = loader.discover(HERE, top_level_dir=HERE)
        if loader.errors:
            self.fail("a test module did not import (%s); run with "
                      "~/.switchdeck-venv/bin/python"
                      % "; ".join(e.splitlines()[0] for e in loader.errors))
        count = suite.countTestCases()
        with open(README, encoding="utf-8") as f:
            text = f.read()
        badge = BADGE_RE.findall(text)
        features = FEATURES_RE.findall(text)
        self.assertEqual(len(badge), 1, "README tests badge not found once")
        self.assertEqual(len(features), 1,
                         "README Features test count not found once")
        self.assertEqual(int(badge[0]), count,
                         "README tests badge says %s, the suite runs %d"
                         % (badge[0], count))
        self.assertEqual(int(features[0]), count,
                         "README Features line says %s cases, the suite runs %d"
                         % (features[0], count))


if __name__ == "__main__":
    unittest.main()
