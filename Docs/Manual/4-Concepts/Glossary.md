# Glossary

TauFW uses a lot of its own words. Here's what they mean, in plain language. Terms are in alphabetical order. Words
in *italics* have their own entry.

---

**advance**
"Do whatever can be done now." You run `python3 taufw.py advance <run folder>` on an existing *run*. TauFW checks
where each *stage* is and pushes it forward as far as it can: it checks batch jobs, resubmits failed ones, merges
finished ones and starts the next stages. When there's nothing left to do right now, it stops.

**analysis bundle** (or just *bundle*)
A folder under `Analyses/` with everything one analysis needs: the `recipe.yml`, the config files it uses and any
Python scripts of your own. All paths in the recipe are relative to this folder. If you copy the folder, you've copied
the analysis.

**artifact**
Something a *stage* produced that the next stage can use. For production, that's one merged *pico tuple* per sample.
For the fit, it's the fitted values. TauFW keeps a list of them in the *run record*.

**attempt**
How many times production has submitted jobs so far, counting the first submission and every resubmission. The
recipe option `max_tries` says how many attempts you allow before TauFW gives up.

**batch system**
The cluster that runs your jobs, so they don't run on the machine you're logged into. On lxplus it's HTCondor.
Production uses it. The other stages run directly on your machine.

**chunk**
One batch job of one *sample*. A sample with hundreds of input files gets split into many chunks, and each chunk
processes a few files. If a chunk fails, only that chunk is resubmitted.

**channel**
The final state you select in production. For example, `mutau` is one muon plus one hadronic tau, and `mumu` is two
muons. Each channel has its own analysis module in PicoProducer.

**CMSSW**
The CMS software release. TauFW lives inside one (`CMSSW_.../src/TauFW`). Before using TauFW in a new terminal, run
`cmsenv` in that release to set up the environment.

**Combine**
The CMS statistics tool that does the fits. The *Fitter* calls it for you. You install it once, during setup.

**config template**
A ready-made config file in `Configs/`, for the Histogrammer or the Fitter. A recipe can use one directly, or you can
copy it into your *bundle* and edit the copy.

**control plots**
Stacked plots of simulation with data on top, usually with a ratio panel. You make them to check that your selection
and simulation look right, before you trust a fit. In a recipe, the `controlhists` stage fills the histograms and the
`controlplots` stage draws them.

**cutflow**
A histogram stored in every *pico tuple* that counts events through the selection. One of its bins holds the
*sum of weights*, which is needed to normalise simulation.

**DAS**
The CMS Data Aggregation System, the catalog of all official datasets. PicoProducer asks DAS which files belong to a
sample. You need a valid *grid proxy* for that.

**era**
A data-taking period with its own detector conditions, like `2022_postEE`. Samples, corrections and luminosity are
all set per era.

**external tuples**
*Pico tuples* that weren't made by a run of your recipe. Maybe a colleague made them, or you made them last month.
You point a recipe at them with `inputs: {tuples: {external: /path/to/$ERA/$GROUP}}`.

**fit shapes**
The histograms the fit reads: one per region, *working point* and systematic variation, in the format Combine
expects. The `shapes` stage makes them.

**grid proxy** (or *grid certificate*)
A short-lived credential that proves who you are to grid services like DAS and remote storage. You make one with your
grid certificate password, and it expires after a while. The TauFW menu shows if yours is still valid and can renew
it.

**group**
A family of samples that go together in one folder, for example all Drell-Yan samples. Merged pico tuples are stored
as `<era>/<group>/`.

**Histogrammer**
The package that turns *pico tuples* into histograms. It also makes the *fit shapes*.

**inputs**
The line in each *stage* that says where its data comes from. For example, `inputs: {hists: hists}` means "read the
histograms made by the stage with *stage id* `hists`". Every stage needs it. A stage that reads nothing, like
production, says `inputs: null`.

**lxplus**
CERN's shared Linux login service. TauFW is made to run there.

**menu**
The text-based menu you get when you run `python3 taufw.py` with no arguments. From there you can start runs,
continue runs, check status and renew your *grid proxy*.

**merge**
The last step of production. All the *chunks* of one sample are added together (with `hadd`) into one *pico tuple*.

**NanoAOD**
The compact, standard CMS data format. It's TauFW's starting point. It's still large and has much more than one
analysis needs.

**pico tuple**
A small ROOT file made by PicoProducer from NanoAOD. It has one flat tree with just the events and variables your
channel needs, plus a *cutflow* histogram. There's one per sample, era and channel. "Pico" because it's smaller than
"nano".

**PicoProducer**
The package that makes *pico tuples* from NanoAOD. Its old command-line tool, `pico.py`, still works.

**plan**
`python3 taufw.py plan <bundle>` shows what a recipe *would* do: which samples, how many jobs, which commands, which
files. Nothing is submitted or written. Run it before every `start`.

**Plotter**
The package that draws plots from histogram files. It doesn't read tuples.

**preflight**
A quick check TauFW does before running a local *stage*: is `cmsenv` set up, is ROOT there, is Combine installed, do
the input files exist? If something is missing, the stage doesn't start. It stays `NEW` and tells you what's wrong.
Fix it and *advance* again.

**python step**
A stage that runs a Python file from your own *bundle*, with a function `run(ctx)`. Use it for things TauFW doesn't
do for you, like making a summary table of fit results.

**recipe**
The `recipe.yml` file in a *bundle*. It says which *stages* to run, in which order, with which options. TauFW checks
the whole recipe for mistakes before anything runs. `python3 taufw.py check <bundle>` lists every problem at once.

**run**
One execution of a *recipe*. Each run gets its own folder, `<run_root>/<recipe name>_<date-time>/`, with the outputs
of every stage, the logs and the *run record*. Runs don't change when you edit the recipe later. To use your edits,
start a new run.

**run record**
The file `run.json` inside a *run* folder. It remembers where every stage is, so you can stop and continue later,
even from a different terminal or on a different day.

**run_root**
The folder where your *runs* are created. Set it in the recipe. On lxplus, pick a place with enough space, like
your `/afs/cern.ch/work/...` area. The home directory is too small for tuples. If you don't set it, runs go to
`taufw_runs/` in the folder you started from, and TauFW warns you about it.

**sample**
One dataset. For example a Drell-Yan simulation sample, or one period of real data. Each era has a list of its
samples, the *sample catalog*.

**sample catalog**
The Python file that lists all samples of an era for PicoProducer, for example
`PicoProducer/samples/samples_2022_postEE.py`. In a recipe you pick samples from it by name, with patterns like
`DY*`.

**stage**
One step of a recipe. The types are `production`, `controlhists`, `controlplots`, `shapes`, `fit` and `python`.

**stage id**
The name you give a stage in your recipe (`id: production`). Other stages refer to it in their *inputs*, and its
output ends up in `stages/<id>/` inside the run folder. Every stage needs one, and they must all be different.

**stage state**
Where a stage is right now. `NEW` means it hasn't started. `SUBMITTED` and `WAITING` mean batch jobs are running.
`MERGING` means the jobs finished and the tuples are being merged. `DONE` means finished. `FAILED` means it went
wrong and won't be retried.

**sum of weights** (sumw)
The total generator weight of all simulated events a sample started with, before any selection. It's needed to scale
simulation to the right luminosity. PicoProducer stores it in the *cutflow*.

**tag**
An optional extra label that ends up in job and file names, so two productions with different settings don't
overwrite each other.

**TES**
Tau energy scale: how much the measured energy of a hadronic tau differs between data and simulation. It's one of
the main things TauFW measures.

**tau ID scale factor** (tau ID SF)
The ratio of tau identification efficiency in data to that in simulation, for a given *working point*. You multiply
simulation by it to correct it.

**working point** (WP)
How tight a tau ID cut is, for example `Loose`, `Medium` or `VTight`. Tighter means fewer fake taus, but also fewer
real ones. TauFW uses DeepTau working points against jets (VSjet), electrons (VSe) and muons (VSmu).
