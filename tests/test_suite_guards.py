"""Guards on the test suite itself, not on switchdeck.py.

Standard library only: this file never imports switchdeck, so it needs no
rumps. Run it with the rest of the suite from the repo root:

    ~/.switchdeck-venv/bin/python -m unittest discover -s tests -v

test_readme_states_the_count_the_suite_runs keeps the README's test count
(the tests badge and the Features line) equal to what the suite runs, so
adding or removing a test without updating the README fails here.
"""
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
README = os.path.join(os.path.dirname(HERE), "README.md")

BADGE_RE = re.compile(r"badge/tests-(\d+)%20unittest")
FEATURES_RE = re.compile(r"\(`tests/`, (\d+) cases\)")


def _iter_tests(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


class SuiteGuards(unittest.TestCase):
    def test_readme_states_the_count_the_suite_runs(self):
        # A fresh loader: defaultTestLoader carries the -k patterns of the
        # outer run, which would shrink the count.
        suite = unittest.TestLoader().discover(HERE, top_level_dir=HERE)
        failed = [t.id() for t in _iter_tests(suite)
                  if isinstance(t, unittest.loader._FailedTest)]
        if failed:
            self.fail("a test module did not import (%s); run with "
                      "~/.switchdeck-venv/bin/python" % ", ".join(failed))
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
