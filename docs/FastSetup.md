# FastSetup

[`FastSetup.sh`](../FastSetup.sh) automates the software installation described
in the [README](../README.md#manual) around an existing TauFW clone.

## Requirements

Run on a Linux CMS node or container with bash 4.4 or newer, CMS software
(normally via CVMFS), Git and network access. The script detects EL8/EL9 for
`SCRAM_ARCH`, or respects an explicitly set `el8_amd64_gcc12` or
`el9_amd64_gcc12`. `CMS_SETUP` can override the default CMS setup script,
`/cvmfs/cms.cern.ch/cmsset_default.sh`.

## Usage

```bash
git clone https://github.com/cms-tau-pog/TauFW TauFW
cd TauFW
bash FastSetup.sh
```

The script creates `CMSSW_14_1_0_pre4` beside the checkout and moves the entire
checkout, including `.git` and local changes, to `CMSSW_14_1_0_pre4/src/TauFW`.
The release location depends on where the checkout already is:

| Checkout location | Release used |
| --- | --- |
| Anywhere inside `CMSSW_14_1_0_pre4` | That release; the checkout is moved to its `src/TauFW` if needed |
| Inside another release, e.g. `CMSSW_13_3_0/src/TauFW` | A new `CMSSW_14_1_0_pre4` beside that release |
| Anywhere else | A new `CMSSW_14_1_0_pre4` beside the checkout |

A release is never created inside another release area. If the destination is
on another filesystem (e.g. a different AFS volume), the checkout is copied and
the original is removed only after the copy is complete.

It installs TauIDSFs, HTT lepton efficiencies, Combine `v10.6.1` and
CombineHarvester `v3.1.0`, then builds with four jobs. The fitting tool
versions follow the [Combine v10 installation instructions](https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/v10.6.1/)
and [CombineHarvester's CMSSW 14_1_X recommendation](https://github.com/cms-analysis/CombineHarvester).
TauIDSFs and the HTT efficiencies follow their default branches. The default
uses CMSSW's built-in NanoAODTools.

## Existing files

The script never force-overwrites or deletes your work:

- An existing `src/TauFW` destination is never overwritten.
- Existing dependency checkouts are reused as they are, without pulling or
  switching versions. If Combine or CombineHarvester is not at the tested tag,
  or a dependency is a clone of a fork, the script prints a warning and repeats
  it at the end.
- The bundled HTT directory is backed up outside `src` before it is replaced.
  TauFW's Git is then told to ignore that directory, so `git status` stays clean
  and `git add -A` cannot commit the swap. To undo this, run
  `git update-index --no-skip-worktree -- PicoProducer/data/lepton/HTT/README.md`
  and remove its line from `.git/info/exclude`.

## Options

| Option | Effect |
| --- | --- |
| `--cmssw-dir PATH` | Use this full release path, ending in `CMSSW_14_1_0_pre4`. |
| `--jobs N` | Set build parallelism (default: 4). |
| `--run2-jme` | Install standalone NanoAODTools for the [Run 2 JEC/JER workflows](../README.md#run-2-jetmet-corrections-backward-compatibility). |
| `--help` | Show usage and requirements. |

`--cmssw-dir=PATH` and `--jobs=N` are also accepted.

Use `--run2-jme` only when those Run 2 workflows are needed, because standalone
NanoAODTools overrides the release's framework. If it is already installed,
the script requires this flag or asks you to move that checkout outside `src`.

## After installation

Activate the environment using the commands printed by the script. A script
cannot set the environment of its parent terminal. Repeat these commands in
each new session:

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH=el9_amd64_gcc12 # use el8_amd64_gcc12 on EL8
cd /path/to/CMSSW_14_1_0_pre4/src
cmsenv
```

## Interrupted or failed runs

On failure the script prints the exact command to rerun from the checkout's
current location. Completed steps are skipped. The build starts clean only when
the run cloned new packages; otherwise it resumes the previous build.

The [TauPOG-internal JSON and ROOT correction production](../README.md#taupog-corrections)
requires measured SF values and manual edits, so it is not performed by the
setup script.
