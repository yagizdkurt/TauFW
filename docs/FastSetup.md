# FastSetup

[`setup.sh`](../setup.sh) automates the software installation described
in the [README](../README.md#manual) around an existing TauFW clone.

## Requirements

Run from a standalone TauFW clone on a Linux CMS node or container with bash
4.4 or newer, Python 3, CMS software (normally via CVMFS), Git and network
access. The interactive checklist also requires Python curses. Linked Git
worktree checkouts are not supported. A main clone that owns linked worktrees
is also rejected when it would need to move; use a separate clone instead.
The script detects EL8/EL9 for
`SCRAM_ARCH`, or respects an explicitly set `el8_amd64_gcc12` or
`el9_amd64_gcc12`. `CMS_SETUP` can override the default CMS setup script,
`/cvmfs/cms.cern.ch/cmsset_default.sh`.

## Usage

```bash
git clone https://github.com/cms-tau-pog/TauFW TauFW
cd TauFW
source setup.sh
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
the original is retained. Setup prints its location; finish any edits in that
original before manually removing it. Copying is not a snapshot of concurrent edits.

By default, TauIDSFs, HTT lepton efficiencies, Combine `v10.6.1` and
CombineHarvester `v3.1.0` are selected for installation, then the release is
built with four jobs. The fitting tool
versions follow the [Combine v10 installation instructions](https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/v10.6.1/)
and [CombineHarvester's CMSSW 14_1_X recommendation](https://github.com/cms-analysis/CombineHarvester).
Fresh downloads use shallow histories and fixed versions. The remaining pins,
captured from the upstream default branches on 2026-10-13, are:

| Dependency | Commit |
| --- | --- |
| Standalone NanoAODTools | `d163c18096fe2c5963ff5a9764bb420b46632178` |
| TauIDSFs | `34f69acfd17c1655a67a709135c594512b84a76f` |
| HTT LeptonEfficiencies | `a31ca914227f109e08c192d3a1b1c9ea07f929b2` |

These pins provide reproducible source versions, not a claim of full analysis
validation. The default uses CMSSW's built-in NanoAODTools. Each installed or
reused dependency's actual commit is printed during setup.


## Existing files

The script never force-overwrites or deletes your work:

- An existing `src/TauFW` destination is never overwritten.
- Existing dependency checkouts must have a valid commit, the expected upstream
  remote (or a same-name fork/mirror), and nonempty required source/data files.
  They are never pulled, reset or switched. Different commits, forks and local
  changes produce warnings repeated in the summary.
- Known conflicts and incomplete checkouts are checked before TauFW is moved.
- New downloads are validated in temporary directories before being renamed
  into place. Interrupted downloads do not leave a partial dependency at its
  final path. Temporary downloads are removed on normal failure or cancellation.
- New HTT installs live at `<release>/external/LeptonEfficiencies`. Only the
  `Electron` and `Muon` correction directories are linked into the bundled HTT
  directory; tracked files such as its README are preserved. The two untracked
  links are locally excluded through `.git/info/exclude`.
- Existing HTT Git checkouts and complete local correction directories are
  preserved. Local directories without Git metadata produce a version warning.
  Selecting HTT also clears the old installer's `skip-worktree` flags, so edits
  to TauFW's tracked HTT files remain visible. Old `FastSetup-backup.*` directories
  are left untouched.

## Options

| Option | Effect |
| --- | --- |
| `--install` | Reopen installation even if a successful setup is recorded. |
| `--cmssw-dir PATH` | Use this full release path, ending in `CMSSW_14_1_0_pre4`. |
| `--jobs N` | Set build parallelism (default: 4). |
| `--run2-jme` | Install standalone NanoAODTools for the [Run 2 JEC/JER workflows](../README.md#run-2-jetmet-corrections-backward-compatibility). |
| `--non-interactive` | Skip the checklist and use defaults plus command-line options. |
| `--skip-tauidsfs` | Do not install or verify TauIDSFs. |
| `--skip-htt` | Do not install or verify HTT lepton efficiencies. |
| `--skip-combine` | Do not install or verify Combine/CombineHarvester. |
| `--help` | Show usage and requirements. |

`--cmssw-dir=PATH` and `--jobs=N` are also accepted.

Use `--run2-jme` only when those Run 2 workflows are needed, because standalone
NanoAODTools overrides the release's framework. If it is already installed,
select it in the checklist or use this flag in noninteractive mode; otherwise
the script asks you to move that checkout outside `src`.

## After installation

The installer runs in a subprocess and keeps its interactive checklist and run
screen. After you close a successful result screen, the sourced wrapper activates
CMSSW in your terminal and enters the installed `src/TauFW` checkout.

In each new session, source the wrapper from that checkout (or use its full path):

```bash
source setup.sh
```

A verified success record under `.git/taufw-setup-state` allows subsequent calls
to activate directly without installation or full dependency checks. Missing or
stale records run installation; older/manual installations therefore run the
installer once. A retained original from a cross-filesystem copy also records
the installed location, so sourcing its wrapper activates the installed copy.

Use `source setup.sh --install` to reopen installation. Supplying any installer
options also runs installation explicitly. `--help` only prints usage. Execute
neither `bash setup.sh` nor `./setup.sh`: sourcing is required to activate your
current shell. The worker lives at `Utilities/FastSetup.sh` and must be run with
Bash if used directly; direct execution cannot activate your parent terminal.

If installation fails or is cancelled, the wrapper returns a nonzero status
without attempting activation. Completion records are invalidated before
installation work and rewritten only after verification succeeds.

Manual activation remains available as a fallback:

```bash
source /cvmfs/cms.cern.ch/cmsset_default.sh
export SCRAM_ARCH=el9_amd64_gcc12 # use el8_amd64_gcc12 on EL8
cd /path/to/CMSSW_14_1_0_pre4/src
cmsenv
cd TauFW
```

## Interrupted or failed runs

On failure the script prints the exact command to rerun from the checkout's
current location, preserving the chosen components for a noninteractive retry.
Completed steps are validated and reused. Only adding fitting packages requests
a global clean, recorded in `<release>/.FastSetup-needs-clean` before downloading.
That marker survives retries and is removed only after `scram b clean` succeeds.
An interrupted clean is retried; an interrupted build resumes without another
clean. Installing TauIDSFs, HTT or NanoAODTools alone does not request a clean.

Final checks import TauFW's packages and the actual selected Python tools from
their expected locations: the source checkout or its corresponding
`<release>/python/<subsystem>/<package>` directory populated by SCRAM. Imports
from other releases or unrelated package directories are rejected. They also
exercise CombineHarvester's native bindings, run the local Combine executable's
help command, and open the HTT ROOT correction
files. These checks establish basic installation usability, not physics validation.

The [TauPOG-internal JSON and ROOT correction production](../README.md#taupog-corrections)
requires measured SF values and manual edits, so it is not performed by the
setup script.

