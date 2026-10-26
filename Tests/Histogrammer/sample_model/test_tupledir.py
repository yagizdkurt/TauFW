"""The scripts' old tuple default (TauFW.Histogrammer.sample.tupledir, CL §37 D1): picodir of the PicoProducer
configuration ($TAUFW_PICO_CONFIG, else PicoProducer/config/config.json), read as JSON without importing PicoProducer
(checkout.py registers no TauFW.PicoProducer, so an import of it fails here). With ROOT, also that the sample library
refuses $PICODIR without a tuple pattern (given, never found)."""
import importlib.util
import json
import os
import tempfile
import unittest

import checkout
from TauFW.Histogrammer.sample import tupledir


class ScriptDefaultTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def config(self, name, data):
        path = os.path.join(self.directory.name, name)
        with open(path, 'w') as stream:
            stream.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def test_environment_variable_first(self):
        chosen = self.config('chosen.json', {"picodir": "/eos/chosen/$ERA/$GROUP"})
        default = self.config('config.json', {"picodir": "/eos/default/$ERA/$GROUP"})
        self.assertEqual(tupledir.script_default_tuples({tupledir.ENVVAR: chosen}, default=default),
                         "/eos/chosen/$ERA/$GROUP")

    def test_default_configuration(self):
        default = self.config('config.json', {"picodir": "/eos/default/$ERA/$GROUP", "jobdir": "x"})
        self.assertEqual(tupledir.script_default_tuples({}, default=default), "/eos/default/$ERA/$GROUP")
        self.assertEqual(tupledir.script_default_tuples({tupledir.ENVVAR: ""}, default=default),
                         "/eos/default/$ERA/$GROUP")

    def test_default_path_is_the_picoproducer_config(self):
        self.assertEqual(os.path.normpath(tupledir.DEFAULT_CONFIG),
                         os.path.normpath(str(checkout.REPO / "PicoProducer" / "config" / "config.json")))
        self.assertEqual(tupledir.ENVVAR, "TAUFW_PICO_CONFIG")  # the name PicoProducer's getconfig reads

    def test_missing_file_names_the_option(self):
        missing = os.path.join(self.directory.name, 'none.json')
        for environ, default in (({tupledir.ENVVAR: missing}, None), ({}, missing)):
            with self.assertRaises(IOError) as raised:
                tupledir.script_default_tuples(environ, default=default)
            self.assertIn(missing, str(raised.exception))
            self.assertIn("--tuples", str(raised.exception))

    def test_unreadable_file(self):
        broken = self.config('broken.json', "{not json")
        with self.assertRaises(IOError) as raised:
            tupledir.script_default_tuples({tupledir.ENVVAR: broken})
        self.assertIn("cannot be read", str(raised.exception))

    def test_no_picodir(self):
        for data in ({"jobdir": "x"}, {"picodir": ""}, {"picodir": 3}, ["picodir"]):
            path = self.config('config.json', data)
            with self.assertRaises(ValueError) as raised:
                tupledir.script_default_tuples({tupledir.ENVVAR: path})
            self.assertIn("--tuples", str(raised.exception))


@unittest.skipUnless(importlib.util.find_spec("ROOT"), "the sample library needs ROOT (lxplus)")
class LibraryTests(unittest.TestCase):
    def test_picodir_without_tuples_is_refused(self):
        from TauFW.Histogrammer.sample.utils import getsampleset
        with self.assertRaises(ValueError) as raised:
            getsampleset(('Data', 'SingleMuon_Run2018A'), [('DY', 'DYJetsToLL_M-50', 'Drell-Yan', 1.0)],
                         channel='mutau', era='2018')
        self.assertIn("tuples", str(raised.exception))


if __name__ == '__main__':
    unittest.main()
