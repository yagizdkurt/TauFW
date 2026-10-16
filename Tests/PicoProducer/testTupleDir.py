"""Where merge writes the tuples: picodir of the configuration, or JobRequest.tupledir (PicoProducer.tuple_pattern,
merge_sample(picodir=...)). No batch system and no files: the storage and the status check are replaced."""
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from TauFW.PicoProducer.api import PicoProducer
from TauFW.PicoProducer.jobs import merge
from TauFW.PicoProducer.jobs.merge import TUPLE_LAYOUT, merge_sample, merge_target


def sample(name="DYJets", group="DY"):
    """What merge_target reads of a sample loaded from its job config."""
    jobcfg = dict(postfix="_mutau_DYJets", outdir="/jobs/out", cfgdir="/jobs/cfg", logdir="/jobs/log",
                  config="/jobs/cfg/jobconfig.json", jobdir="/jobs")
    return SimpleNamespace(name=name, group=group, paths=["/DYJets/Run3/NANOAODSIM"], jobcfg=jobcfg)


class TupleDirTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='taufw-tupledir-')
        self.addCleanup(temporary.cleanup)
        self.base = temporary.name

    def pico(self, picodir):
        return PicoProducer.from_config({'picodir': picodir}, basedir=self.base)

    def test_tuple_pattern(self):
        stage = os.path.join(self.base, "run", "stages", "production")
        pico = self.pico("/eos/user/u/user/analysis/$ERA/$GROUP")
        self.assertEqual(TUPLE_LAYOUT, "$ERA/$GROUP")
        self.assertEqual(pico.tuple_pattern(pico.request(tupledir=stage)), os.path.join(stage, "$ERA", "$GROUP"))
        self.assertEqual(pico.tuple_pattern(pico.request()), "/eos/user/u/user/analysis/$ERA/$GROUP")
        self.assertEqual(self.pico("analysis/$ERA/$GROUP").tuple_pattern(pico.request()),  # merge runs in basedir
                         os.path.normpath(os.path.join(self.base, "analysis/$ERA/$GROUP")))
        for picodir in ("$PICODIR/$ERA", "root://eosuser.cern.ch//eos/user/u/user/$ERA"):
            self.assertEqual(self.pico(picodir).tuple_pattern(pico.request()), picodir)
        self.assertIsNone(pico.request().tupledir)  # pico.py never sets it

    def test_merge_target_below_the_tupledir(self):
        pattern = os.path.join("/run", "stages", "production", "$ERA", "$GROUP")
        target = merge_target(sample(), pattern, "2025", "mutau", "")
        self.assertEqual(target.storedir, os.path.join("/run", "stages", "production", "2025", "DY"))
        self.assertEqual(target.outfile, "DYJets_mutau.root")

    def test_merge_sample_uses_the_given_picodir(self):
        refused = SimpleNamespace(mergeable=False, resubfiles=["chunk"])  # stops before hadd: nothing runs
        config = SimpleNamespace(picodir="/eos/config/$ERA/$GROUP")
        with mock.patch.object(merge, 'getstorage') as getstorage, \
                mock.patch.object(merge, 'check_sample', return_value=refused):
            given = merge_sample(sample(), config, 'hadd', "2025", "mutau", "", picodir="/run/stages/p/$ERA/$GROUP")
            default = merge_sample(sample(), config, 'hadd', "2025", "mutau", "")
        self.assertTrue(given.refused)
        self.assertEqual(given.target.storedir, "/run/stages/p/2025/DY")
        self.assertEqual(default.target.storedir, "/eos/config/2025/DY")  # without picodir: the configuration's
        self.assertEqual([c.args[0] for c in getstorage.call_args_list], ["/run/stages/p/2025/DY", "/eos/config/2025/DY"])


if __name__ == '__main__':
    unittest.main()
