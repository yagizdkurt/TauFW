"""ROOT expression helpers: results recorded from TauFW.Plotter.plot.string before the helpers moved to
TauFW.Utilities.Expressions (2026-10-14). Latent bugs are recorded as they behave today (Plotter BUGS L05-L07)."""

import unittest
from unittest import mock

import checkout  # noqa: F401  (must precede TauFW.Utilities imports)
from TauFW.Utilities.Drawing import LOG
from TauFW.Utilities.Expressions import cleanbool, getselstr, joincuts, joinweights, replacepattern


class Warnings:
    """Collect LOG.warn messages instead of printing them."""
    def __enter__(self):
        self.patch = mock.patch.object(LOG, "warn")
        self.warn = self.patch.start()
        return self

    def __exit__(self, *exc):
        self.patch.stop()

    @property
    def messages(self):
        return [call.args[0] for call in self.warn.call_args_list]


class SelectionTests(unittest.TestCase):
    def test_getselstr(self):
        class Selection:
            selection = "pt_1>20"
        self.assertEqual(getselstr("pt>1"), "pt>1")
        self.assertEqual(getselstr(Selection()), "pt_1>20")
        self.assertIsNone(getselstr(None))

    def test_joincuts(self):
        self.assertEqual(joincuts(), "")
        self.assertEqual(joincuts(""), "")
        self.assertEqual(joincuts("a>1"), "a>1")
        self.assertEqual(joincuts("a>1", "b<2"), "a>1 && b<2")
        self.assertEqual(joincuts("a>1", None, 5, "b<2"), "a>1 && b<2")
        self.assertEqual(joincuts("a>1", "(b||c)"), "a>1 && (b||c)")
        self.assertEqual(joincuts("a>1", verb=3), "a>1")

    def test_joincuts_weight(self):
        self.assertEqual(joincuts("a>1", weight="w"), "(a>1)*w")
        self.assertEqual(joincuts("a>1", "b<2", weight="w1*w2"), "(a>1 && b<2)*w1*w2")
        self.assertEqual(joincuts("a>1", weight="a+b"), "(a>1)*(a+b)")
        self.assertEqual(joincuts("a>1", weight="(a>1)*w"), "(a>1)*(a>1)*w")
        self.assertEqual(joincuts("a>1", weight="(x)+y"), "(a>1)*((x)+y)")
        self.assertEqual(joincuts(weight="w"), "w")
        self.assertEqual(joincuts(weight="q_1*q_2<0"), "(q_1*q_2<0)")
        self.assertEqual(joincuts("(x)||y", weight="w"), "((x)||y)*w")

    def test_joincuts_or(self):
        with Warnings() as log:
            self.assertEqual(joincuts("a>1", "b||c"), "a>1 && (b||c)")
        self.assertEqual(log.messages, ['joincuts: Be careful with those "or" statements in [\'a>1\', \'b||c\']! '
                                        'Not sure how to join...'])
        # L07: a cut with any parentheses is not wrapped, so && binds before the unbracketed ||
        with Warnings() as log:
            self.assertEqual(joincuts("a>1", "(x)||y"), "a>1 && (x)||y")
        self.assertEqual(log.messages, [])

    def test_cleanbool(self):
        self.assertEqual(cleanbool("a && && b"), "a && b")
        self.assertEqual(cleanbool("a || && b"), "a && b")
        self.assertEqual(cleanbool("&& a"), "a")
        self.assertEqual(cleanbool(" a && "), "a")
        self.assertEqual(cleanbool("a&&||b"), "a&&b")
        self.assertEqual(cleanbool(""), "")


class WeightTests(unittest.TestCase):
    def test_joinweights(self):
        self.assertEqual(joinweights(), "")
        self.assertEqual(joinweights("w1", "w2"), "w1*w2")
        self.assertEqual(joinweights("w1", 1, "w2"), "w1*w2")
        self.assertEqual(joinweights(2, "w"), "2*w")
        self.assertEqual(joinweights(1.5), "1.5")
        self.assertEqual(joinweights("w1", "/w2"), "w1/w2")
        self.assertEqual(joinweights("", None, "w"), "w")
        with Warnings() as log:
            self.assertEqual(joinweights(["w"], "v"), "v")
        self.assertEqual(log.messages, ["joinweights: Ignoring ['w'] (type <class 'list'>) because it is not a "
                                        "string or number?"])

    def test_joinweights_zero(self):
        # L05: the warning for a zero weight has one %r for two values
        with self.assertRaisesRegex(TypeError, "not all arguments converted during string formatting"):
            joinweights(0, "w")

    def test_replacepattern(self):
        self.assertEqual(replacepattern("w1*w2*10", ("w1", "x")), "x*w2*10")
        self.assertEqual(replacepattern("w1*w2", []), "w1*w2")
        self.assertEqual(replacepattern("w1*w2", ("w1", "")), "w2")
        self.assertEqual(replacepattern("wgt_1*wgt_2", [(r"wgt_(\d)", r"new\1", True)]), "new1*new2")
        # L06: every pattern starts again from the original string, so only the last one applies
        self.assertEqual(replacepattern("w1*w2*w3", [("w1", "a"), ("w3", "b")]), "w1*w2*b")
        with self.assertRaisesRegex(OSError, r"Pattern must be of form .* Got oldstr='a\*b', patargs=\('a',\)"):
            replacepattern("a*b", [("a",)])


if __name__ == "__main__":
    unittest.main()
