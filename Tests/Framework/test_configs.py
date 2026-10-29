"""Config templates (configs.py): headers, the lock and `update`, the warnings for old copies in a bundle, and the
templates of this checkout's Configs/ (lock up to date, every template readable by its module's reader)."""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

import checkout
from TauFW.Framework import check_recipe
from TauFW.Framework._internal.recipes.configs import (scan, lock_changes, update, copy_warnings, read_header,
                                                       renamed_id, content_hash, ConfigError, LOCK_NAME)
from TauFW.Framework._internal.defaults import CONFIGS_DIR
from TauFW.Histogrammer.sample.model import load_sample_model

STEP = {"stage": "python", "id": "check", "inputs": None, "file": "steps/check.py"}

# The reader of each kind of template, by the start of its id: a function(path) that raises if it cannot read the
# file. Every template of Configs/ must have one (RepositoryConfigsTests); add the module's reader with its first
# template.
READERS = {
    'histogrammer.samples_': lambda path: load_sample_model(path),  # Configs/Histogrammer/samples/ (sample.model)
    'histogrammer.setup_': lambda path: read_setup(path),           # Configs/Histogrammer/setups/ (fillhists.py)
    'fitter.tes_id_': lambda path: read_tes_id(path),               # Configs/Fitter/tes_id/ (createinputsTES.py, fit)
}


def read_tes_id(path):
    """A TES / tau ID channel config with the keys its two readers take without a default (Docs/Develop/contracts/
    tes-shapes.md; CL §22 D1): createinputsTES.py (channel, baselineCuts, samples.filename/join/data, observables
    with binning and fitRegions in regions, processes; regions with definition and title; TES variations and shape
    systematics with their fields) and the fit scripts (channel, tag, observables, processes, systematics)."""
    import yaml
    with open(path) as stream:
        setup = yaml.safe_load(stream)
    problems = ["no %s" % (key) for key in ('channel', 'tag', 'baselineCuts', 'samples', 'observables', 'processes',
                                            'systematics') if key not in setup]
    problems += ["no samples.%s" % (key) for key in ('filename', 'join', 'data') if key not in setup.get('samples', {})]
    regions = setup.get('regions', {'baseline': {'definition': '1', 'title': 'Baseline'}})  # the script's default
    problems += ["region %s: no %s" % (name, key) for name, region in regions.items()
                 for key in ('definition', 'title') if key not in region]
    for name, observable in setup.get('observables', {}).items():
        problems += ["observable %s: no binning" % (name)] if 'binning' not in observable else []
        problems += ["observable %s: fit region %s is not a region" % (name, region)
                     for region in observable.get('fitRegions', ()) if region not in regions]
    if 'TESvariations' in setup:
        problems += ["no TESvariations.%s" % (key) for key in ('values', 'processes') if key not in setup['TESvariations']]
    for name, systematic in setup.get('systematics', {}).items():
        needed = ('effect', 'processes') + (('name', 'title', 'variations') if systematic.get('effect') == 'shape' else ())
        problems += ["systematic %s: no %s" % (name, key) for key in needed if key not in systematic]
    if problems:
        raise ValueError("%s: %s" % (path, "; ".join(problems)))
    return setup


def read_setup(path):
    """A channel setup as fillhists.py reads it (yaml.safe_load), with the keys every run needs."""
    import yaml
    with open(path) as stream:
        setup = yaml.safe_load(stream)
    missing = [key for key in ('channel', 'baselineCuts') if key not in setup]
    if missing:
        raise ValueError("%s: no %s" % (path, ", ".join(missing)))
    return setup


def template(config_id="plotter.samples_test", version=1, body="xsec: 1.5\n", newline="\n", header=None):
    """The text of a template with a block header."""
    header = header or ("taufw_config:   # set by the maintainers\n"
                        "  id: %s\n"
                        "  version: %d\n"
                        "  schema: 1\n"
                        "  description: a test template\n" % (config_id, version))
    return (header + body).replace("\n", newline)


class ConfigsCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="taufw-test-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.configs = os.path.join(self.root, "Configs")
        os.makedirs(self.configs)

    def write(self, relative, text, base=None):
        path = os.path.join(base or self.configs, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", newline="") as stream:
            stream.write(text)
        return path

    def read(self, relative, base=None):
        with open(os.path.join(base or self.configs, relative), newline="") as stream:
            return stream.read()

    def kinds(self, changes):
        return [(change.config_id, change.kind, change.version) for change in changes]


class HeaderTests(unittest.TestCase):
    def test_valid_header(self):
        header = read_header({"taufw_config": {"id": "plotter.samples_v15_2025", "version": 3, "schema": 1,
                                               "description": " samples "}, "x": 1})
        self.assertEqual((header.id, header.version, header.schema, header.description),
                         ("plotter.samples_v15_2025", 3, 1, "samples"))

    def test_no_header(self):
        self.assertIsNone(read_header({"x": 1}))
        self.assertIsNone(read_header([1, 2]))

    def test_invalid_headers(self):
        good = {"id": "plotter.a", "version": 1, "schema": 1, "description": "d"}
        for change, text in [({"id": "Plotter.a"}, "id must be"), ({"id": "plotter"}, "id must be"),
                             ({"version": 0}, "version must be"), ({"version": "2"}, "version must be"),
                             ({"version": True}, "version must be"), ({"schema": None}, "schema must be"),
                             ({"description": ""}, "description"), ({"owner": "me"}, "unknown")]:
            with self.subTest(change=change):
                with self.assertRaisesRegex(ConfigError, text):
                    read_header({"taufw_config": dict(good, **change)})
        with self.assertRaisesRegex(ConfigError, "must be a mapping"):
            read_header({"taufw_config": "plotter.a 1"})

    def test_hash_ignores_header_and_key_order(self):
        first = {"taufw_config": {"version": 1}, "a": 1, "b": [1.5, "x"]}
        second = {"b": [1.5, "x"], "a": 1, "taufw_config": {"version": 7}}
        self.assertEqual(content_hash(first), content_hash(second))
        self.assertNotEqual(content_hash(first), content_hash({"a": 1, "b": [1.5, "y"]}))


class LockTests(ConfigsCase):
    def test_new_template_is_locked(self):
        self.write("Plotter/samples/test.yml", template())
        configs, changes = update(self.configs)
        self.assertEqual(configs.problems, ())
        self.assertEqual(self.kinds(changes), [("plotter.samples_test", "new", 1)])
        self.assertEqual(lock_changes(self.configs)[1], [])
        self.assertIn("plotter.samples_test 1 ", self.read(LOCK_NAME))

    def test_changed_value_raises_the_version_in_the_file(self):
        text = template(body="xsec: 1.5   # pb\nother: [1, 2]\n", newline="\r\n")
        self.write("Plotter/test.yml", text)
        update(self.configs)
        self.write("Plotter/test.yml", text.replace("1.5", "1.6"))
        self.assertEqual(self.kinds(lock_changes(self.configs)[1]), [("plotter.samples_test", "changed", 2)])
        update(self.configs)
        self.assertEqual(self.read("Plotter/test.yml"), text.replace("1.5", "1.6").replace("version: 1", "version: 2"))
        self.assertEqual(lock_changes(self.configs)[1], [])

    def test_comments_and_layout_do_not_count(self):
        self.write("Plotter/test.yml", template(body="xsec: 1.5\n"))
        update(self.configs)
        self.write("Plotter/test.yml", template(body="# a comment\nxsec:   1.5    # pb\n\n"))
        self.assertEqual(lock_changes(self.configs)[1], [])

    def test_version_raised_by_hand_is_kept(self):
        self.write("Plotter/test.yml", template())
        update(self.configs)
        self.write("Plotter/test.yml", template(version=5, body="xsec: 2.0\n"))
        configs, changes = update(self.configs)
        self.assertEqual(self.kinds(changes), [("plotter.samples_test", "raised", 5)])
        self.assertIn("version: 5", self.read("Plotter/test.yml"))
        self.assertIn("plotter.samples_test 5 ", self.read(LOCK_NAME))

    def test_lowered_version_writes_nothing(self):
        self.write("Plotter/test.yml", template(version=3))
        self.write("Plotter/other.yml", template("plotter.other"))
        update(self.configs)
        lock = self.read(LOCK_NAME)
        self.write("Plotter/test.yml", template(version=2))
        self.write("Plotter/other.yml", template("plotter.other", body="xsec: 9\n"))
        configs, changes = update(self.configs)
        self.assertIn(("plotter.samples_test", "lowered", 3), self.kinds(changes))
        self.assertEqual(self.read(LOCK_NAME), lock)
        self.assertIn("version: 1", self.read("Plotter/other.yml"))  # not raised either

    def test_removed_template_leaves_the_lock(self):
        self.write("Plotter/test.yml", template())
        self.write("Plotter/other.yml", template("plotter.other"))
        update(self.configs)
        os.remove(os.path.join(self.configs, "Plotter", "other.yml"))
        configs, changes = update(self.configs)
        self.assertEqual(self.kinds(changes), [("plotter.other", "removed", 1)])
        self.assertNotIn("plotter.other", self.read(LOCK_NAME))

    def test_problems_write_nothing(self):
        cases = {
            "Plotter/samples.py": "x = 1\n",
            "Plotter/data.json": "{}\n",
            "top.yml": template("top.a"),
            "Fitter/wrong.yml": template("plotter.wrong"),
            "Plotter/flow.yml": "taufw_config: {id: plotter.flow, version: 1, schema: 1, description: d}\nx: 1\n",
            "Plotter/bare.yml": "x: 1\n",
            "Plotter/broken.yml": "taufw_config: [\n",
        }
        for relative, text in cases.items():
            with self.subTest(relative=relative):
                path = self.write(relative, text)
                configs, changes = update(self.configs)
                self.assertEqual(len(configs.problems), 1, configs.problems)
                self.assertIn(relative.split("/")[-1], configs.problems[0])
                self.assertFalse(os.path.exists(os.path.join(self.configs, LOCK_NAME)))
                os.remove(path)

    def test_duplicate_id(self):
        self.write("Plotter/a.yml", template())
        self.write("Plotter/b.yml", template())
        configs, _ = update(self.configs)
        self.assertEqual(len(configs.problems), 1)
        self.assertIn("also used by", configs.problems[0])

    def test_readme_and_lock_are_allowed(self):
        self.write("README.md", "# x\n")
        self.write("Plotter/README.md", "# x\n")
        self.assertEqual(update(self.configs)[0].problems, ())

    def test_bad_lock_line(self):
        self.write(LOCK_NAME, "# comment\nplotter.a one sha\n")
        self.assertIn("not '<id> <version> <sha256>'", scan(self.configs).problems[0])


class CopyWarningTests(ConfigsCase):
    def setUp(self):
        super().setUp()
        self.bundle = os.path.join(self.root, "tes")
        self.write("recipe.yml", json.dumps({"name": "tes", "pico": {"config": None}, "stages": [STEP]}), self.bundle)
        self.write("steps/check.py", "def run(ctx):\n    pass\n", self.bundle)
        self.write("Plotter/samples/test.yml", template(version=2))
        update(self.configs)

    def warnings(self):
        return copy_warnings(self.bundle, self.configs)

    def test_the_scan_is_kept_while_configs_is_unchanged(self):
        """The menu checks every recipe on each Start: Configs/ is scanned again only when one of its files
        changed (path, mtime, size), never with a FileIO of the caller."""
        from TauFW.Framework._internal.recipes import configs
        self.write("samples.yml", template(version=1), self.bundle)
        with mock.patch.object(configs, "scan", wraps=configs.scan) as scanned:
            self.assertEqual(len(self.warnings()), 1)
            self.assertEqual(len(self.warnings()), 1)
            self.assertEqual(scanned.call_count, 1)
            self.write("Plotter/samples/test.yml", template(version=1, body="xsec: 12345\n"))  # the maintainers
            self.assertEqual(self.warnings(), [])  # the copy is as new as the template now
            self.assertEqual(scanned.call_count, 2)
            self.write("Plotter/samples/other.yml", template("plotter.other"))
            self.warnings()
            self.assertEqual(scanned.call_count, 3)  # a new template
            copy_warnings(self.bundle, self.configs, files=configs.default_file_io())
            self.assertEqual(scanned.call_count, 4)

    def test_copy_of_the_current_version(self):
        self.write("samples.yml", template(version=2, body="xsec: 7\n"), self.bundle)  # values edited: fine
        self.assertEqual(self.warnings(), [])

    def test_older_copy(self):
        self.write("samples.yml", template(version=1), self.bundle)
        (relative, message), = self.warnings()
        self.assertEqual(relative, "samples.yml")
        self.assertIn("version 1, but Configs/Plotter/samples/test.yml is version 2", message)

    def test_newer_copy_and_unknown_id(self):
        self.write("a.yml", template(version=3), self.bundle)
        self.write("sub/b.yml", template("plotter.gone"), self.bundle)
        messages = dict(self.warnings())
        self.assertIn("never its taufw_config header", messages["a.yml"])
        self.assertIn("not in Configs/ any more", messages[os.path.join("sub", "b.yml")])

    def test_copy_with_the_id_from_before_a_rename(self):
        """BACKWARD COMPATIBILITY (changelog §21): plotter.samples_* became histogrammer.samples_*."""
        self.assertEqual(renamed_id("plotter.samples_v15_2025"), "histogrammer.samples_v15_2025")
        self.assertEqual(renamed_id("plotter.setup_mutau"), "histogrammer.setup_mutau")
        self.assertIsNone(renamed_id("fitter.tes_id"))
        self.write("Histogrammer/samples/new.yml", template("histogrammer.samples_new", version=2))
        update(self.configs)
        self.write("same.yml", template("plotter.samples_new", version=2), self.bundle)
        self.write("older.yml", template("plotter.samples_new", version=1), self.bundle)
        messages = {}
        for relative, message in self.warnings():
            messages.setdefault(relative, []).append(message)
        self.assertEqual(len(messages["same.yml"]), 1)  # only the rename: same version
        self.assertIn("renamed histogrammer.samples_new (Configs/Histogrammer/samples/new.yml", messages["same.yml"][0])
        self.assertEqual(len(messages["older.yml"]), 2)  # the rename, and the template is newer
        self.assertIn("version 1, but Configs/Histogrammer/samples/new.yml is version 2", messages["older.yml"][1])

    def test_invalid_header_and_plain_files(self):
        self.write("bad.yml", template(header="taufw_config:\n  id: plotter.x\n"), self.bundle)
        self.write("setup.yml", "channel: mutau\n", self.bundle)
        (relative, message), = self.warnings()
        self.assertEqual(relative, "bad.yml")
        self.assertIn("invalid taufw_config header", message)

    def test_check_recipe_shows_the_warning(self):
        self.write("samples.yml", template(version=1), self.bundle)
        with mock.patch("TauFW.Framework._internal.recipes.configs.CONFIGS_DIR", self.configs):
            check = check_recipe(self.bundle)
        self.assertTrue(check.ok)
        self.assertTrue(any(str(w).startswith("samples.yml: copy of plotter.samples_test version 1")
                            for w in check.warnings), check.warnings)


class RepositoryConfigsTests(unittest.TestCase):
    """The templates of this checkout's Configs/."""

    def test_lock_is_up_to_date(self):
        configs, changes = lock_changes(CONFIGS_DIR)
        self.assertEqual(configs.problems, (), "fix the templates of Configs/ (see Configs/README.md)")
        self.assertEqual([str(change) for change in changes], [],
                         "Configs/ changed since %s: run `taufw.py configs update` and commit the raised versions "
                         "with the lock" % (LOCK_NAME))

    def test_every_template_has_a_reader(self):
        for found in scan(CONFIGS_DIR).templates:
            with self.subTest(template=found.path):
                readers = [prefix for prefix in READERS if found.header.id.startswith(prefix)]
                self.assertTrue(readers, "no reader for %s in READERS of %s" % (found.header.id, __file__))
                READERS[max(readers, key=len)](os.path.join(CONFIGS_DIR, found.path))


if __name__ == "__main__":
    unittest.main()
