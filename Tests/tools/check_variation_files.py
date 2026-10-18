#!/usr/bin/env python3
# Author: Yagizhan Dinckurt (October 2026) (yagizdkurt)
"""Compare the variation tuples that the shapes preflight expects with the ones the real sample code asks for
(ModuleIsolationFinalizations §3 A; lxplus, needs ROOT and the nominal tuples).

The preflight (TauFW.Histogrammer.api.TESShapes.variation_problems) names the files without ROOT, by replaying the
sample set on names (TauFW.Histogrammer.sample.variations). This tool builds the real SampleSet as
Histogrammer/shapes/TauES/createinputsTES.py does (getsampleset with the config's samples options, split, rename),
makes every shifted set the script makes (SampleSet.shift for each TES value and each shape systematic with
sampleAppend) and collects the file names of the shifted samples. Sample.setnevents is switched off for the shifted
sets, so no variation file is opened: a missing one is still named (the nominal tuples are opened as in the script).

    cd $CMSSW_BASE/src/TauFW && cmsenv
    python3 Tests/tools/check_variation_files.py -c Analyses/tes_id_2025/config_coarse_TT.yml \\
        --samples Analyses/tes_id_2025/v15_2025.yml -y 2025 \\
        --tuples '/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/$ERA/$GROUP'

Prints SAME and the number of files, or the files only one side names. Exit status 0 when both sides name the same
files, 1 otherwise.
"""
import argparse
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HISTOGRAMMER = REPO / "Histogrammer"


def expected(config, samples, era, tuples):
    """The files of the preflight: {tag: set of paths}."""
    import yaml
    from TauFW.Histogrammer.api.control_hists import _tuple_file
    from TauFW.Histogrammer.sample import model
    from TauFW.Histogrammer.sample.variations import variations
    with open(config) as stream:
        setup = yaml.safe_load(stream)
    files = {}
    for variation in variations(setup, model.pick(samples, era), era):
        for group, sample in variation.samples:
            nominal = _tuple_file(tuples, era, group, sample, setup['channel'])
            path = nominal if variation.tag in nominal else nominal.replace(".root", variation.tag + ".root")
            files.setdefault(variation.tag, set()).add(os.path.normpath(path))
    return files


def actual(config, samples, era, tuples):
    """The files the real SampleSet asks for: {tag: set of paths} (createinputsTES.py's calls, ROOT)."""
    import yaml
    sys.path.insert(0, str(HISTOGRAMMER))  # config.samples_v15, as createinputsTES.py finds it
    from config.samples_v15 import getsampleset
    from TauFW.Histogrammer.sample.Sample import Sample
    with open(config) as stream:
        setup = yaml.safe_load(stream)
    sampleset = getsampleset(setup['channel'], era, fname=setup["samples"]["filename"], join=setup["samples"]["join"],
                             split=[], table=False, rmsf=setup["samples"].get("removeSFs", []),
                             addsf=setup["samples"].get("addSFs", []), tuples=tuples, samples=samples)
    for name, parts in (setup["samples"].get("split") or {}).items():
        sampleset.split(name, parts)
    for old, new in (setup["samples"].get("rename") or {}).items():
        sampleset.rename(old, new)
    shifts = [(("_TES%.3f" % value).replace(".", "p"), setup["TESvariations"]["processes"])
              for value in (setup.get("TESvariations") or {}).get("values", [])]
    for syst in (setup.get("systematics") or {}).values():
        if syst["effect"] == "shape" and "sampleAppend" in syst:
            shifts += [(tag, syst["processes"]) for tag in syst["sampleAppend"]]
    Sample.setnevents = lambda self, *args, **kwargs: self.nevents  # do not open the variation files
    files = {}
    for tag, processes in shifts:
        if not tag:
            continue
        shifted = sampleset.shift(processes, tag, split=True, filter=False, share=True)
        for sample in shifted.mcsamples:
            for path in _filenames(sample):
                if path.endswith(tag + ".root"):
                    files.setdefault(tag, set()).add(os.path.normpath(path))  # a pattern ending in /
    return files


def _filenames(sample):
    """The file names of a sample, its merged samples and its split parts (what Sample.appendfilename changes)."""
    from TauFW.Histogrammer.sample.MergedSample import MergedSample
    names = []
    if isinstance(sample, MergedSample):
        for sub in sample.samples:
            names += _filenames(sub)
    else:
        names.append(sample.filename)
    for part in sample.splitsamples:
        names += _filenames(part)
    return names


def compare(expected_files, actual_files):
    """(number of files, list of differences)."""
    differences = []
    for tag in sorted(set(expected_files) | set(actual_files)):
        want, got = expected_files.get(tag, set()), actual_files.get(tag, set())
        differences += ["%s: only the preflight names %s" % (tag, path) for path in sorted(want - got)]
        differences += ["%s: only the sample code asks for %s" % (tag, path) for path in sorted(got - want)]
    return sum(len(paths) for paths in expected_files.values()), differences


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument('-c', '--config', required=True, help="channel config (createinputsTES.py -c)")
    parser.add_argument('-y', '--era', required=True)
    parser.add_argument('--samples', required=True, nargs='+', help="sample model files (createinputsTES.py --samples)")
    parser.add_argument('--tuples', required=True, help="tuple pattern with $ERA, $GROUP (absolute)")
    args = parser.parse_args(argv)
    samples = [os.path.abspath(path) for path in args.samples]
    want = expected(args.config, samples, args.era, args.tuples)
    got = actual(args.config, samples, args.era, args.tuples)
    total, differences = compare(want, got)
    for line in differences:
        print(line)
    if differences:
        print("DIFFERENT: %d difference(s)" % (len(differences)))
        return 1
    print("SAME: %d variation file(s) in %d shifted set(s)" % (total, len(want)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
