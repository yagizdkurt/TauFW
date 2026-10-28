# Manual installation

## Table of Contents

* [CMSSW environment](#cmssw-environment)<br>
* [TauFW](#taufw)<br>
* [PicoProducer](#picoproducer)<br>
* [Combine](#combine)<br>
* [TauPOG corrections](#taupog-corrections)<br>

## CMSSW environment
First, setup the reference CMSSW release, `CMSSW_14_1_0_pre4` (Python 3.9, ROOT 6.30):
```bash
export SCRAM_ARCH=el9_amd64_gcc12 # on an EL8 node, use el8_amd64_gcc12 instead
cmsrel CMSSW_14_1_0_pre4
cd CMSSW_14_1_0_pre4/src
cmsenv
```

TauFW and its [tests](../../Tests/README.md) are validated with this release.
Other releases may work, but are not tested; some features need at least ROOT 6.30.
Older python2 releases (e.g. `CMSSW_11_3_4`) are no longer supported by `pico.py`.
The old python2 launcher `pico2.py` is kept as `pico2.sh`, unmaintained, in `Legacy/PicoProducer/python/scripts/`.

## TauFW
To install `TauFW`:
```
cd $CMSSW_BASE/src/
git clone https://github.com/cms-tau-pog/TauFW TauFW
scram b -j4
```
With each new session, do
```
cd CMSSW_14_1_0_pre4/src
cmsenv
```

## PicoProducer
`PicoProducer` uses the `NanoAODTools` framework, which is part of CMSSW since `CMSSW_13_3_0`
(`PhysicsTools/NanoAODTools`), so no separate installation is needed.
This covers all analysis channels and the `skim` channel.
Do not clone the standalone [`nanoAOD-tools`](https://github.com/cms-nanoAOD/nanoAOD-tools) repository by default:
it overrides the release's framework with an older version
(e.g. no LFN-to-PFN conversion of `/store/` input paths, no `Short_t` output branches).

### Run 2 jet/MET corrections (backward compatibility)
Re-applying Run 2 JEC/JER and their uncertainties uses the JME modules (`modules/jme`)
that exist only in the standalone repository. This concerns
* the `skim-jec` channel, or `skimjob.py` with `--jec`/`--jec-sys`, which adds branches like `Jet_pt_nom`;
* analysis modules run with `jec=True` on such skims (e.g. `ModuleHighPT`, where it is the default).

Only if you need these Run 2 workflows, install the standalone repository:
```
cd $CMSSW_BASE/src/
git clone https://github.com/cms-nanoAOD/nanoAOD-tools.git PhysicsTools/NanoAODTools
scram b -j4
```
To return to the release's version, remove `$CMSSW_BASE/src/PhysicsTools/NanoAODTools` and run `scram b` again.
To check which version is used:
```
python3 -c "import PhysicsTools.NanoAODTools.postprocessing.framework.postprocessor as m; print(m.__file__)"
```
If you want to use tau ID SFs, please install [`TauIDSFs` tool](https://github.com/cms-tau-pog/TauIDSFs):
```
cd $CMSSW_BASE/src/
git clone https://github.com/cms-tau-pog/TauIDSFs TauPOG/TauIDSFs
cmsenv
scram b -j4
```
If you want to use the lepton SFs from the HTT group, please do
```
cd $CMSSW_BASE/src/TauFW/PicoProducer/data/lepton/
rm -rf HTT
git clone https://github.com/CMS-HTT/LeptonEfficiencies HTT
```

## Combine
If you want to use the `combine` tools in `Fitter`, install combine following the
[latest instructions](https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/#setting-up-the-environment-and-installation),
for example
```
cd $CMSSW_BASE/src
git clone https://github.com/cms-analysis/HiggsAnalysis-CombinedLimit.git HiggsAnalysis/CombinedLimit
cd HiggsAnalysis/CombinedLimit
git fetch origin
git checkout <v10.x tag> # Combine v10 series for CMSSW_14_1_X; check the Combine docs for the exact tag
```
and then [`CombineHarvester`](https://github.com/cms-analysis/CombineHarvester),
using the version its documentation recommends for Combine v10:
```
cd $CMSSW_BASE/src
git clone https://github.com/cms-analysis/CombineHarvester.git CombineHarvester
scramv1 b clean; scramv1 b
```

## TauPOG corrections
For TauPOG-internal work: To create JSON files with TauPOG corrections for
[`correctionlib`](https://github.com/cms-nanoAOD/correctionlib),
please follow the instructions
[here](https://gitlab.cern.ch/cms-tau-pog/jsonpog-integration/-/blob/TauPOG_v2/POG/TAU/README4UPDATES.md).
From at least `CMSSW_11_3_X`, `correctionlib` should be pre-installed.

To create ROOT files including the measured SFs please install [`TauIDSFs` tool](https://github.com/cms-tau-pog/TauIDSFs).
Modify the `TauIDSFs/utils/createSFFiles.py` script to include your measured SFs into the script.
Finally, run the `TauFW/scripts/tau_createROOT.sh` to generate your ROOT files. They will be created into `TauFW/scripts/data/`
IMPORTANT: please comment and do not delete older SFs

The latest code used to create root files for SF can be taken from [here](https://github.com/saswatinandan/TauFW/blob/master/Fitter/createroot_TES.py)
