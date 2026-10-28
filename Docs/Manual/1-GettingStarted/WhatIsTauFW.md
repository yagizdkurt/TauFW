# What is TauFW?

TauFW is the code the CMS Tau group uses for tau measurements. Things like the tau energy scale or tau ID scale
factors. It takes CMS data and simulation in the NanoAOD format, and at the end of the chain it gives you fitted
numbers, plus a lot of plots along the way.

This page gives you the big picture. There are no commands to run here. Once you know what the pieces are, the
tutorials will make a lot more sense.

## The chain, from NanoAOD to a result

Every tau analysis in TauFW goes through roughly the same steps:

```text
  NanoAOD (on the grid, huge)
     │
     │  1. PicoProducer: select events, compute what you need, keep only that
     ▼
  pico tuples (small ROOT ntuples, one per sample)
     │
     │  2. Histogrammer: fill histograms, normalise MC, estimate QCD
     ▼
  histograms
     │
     ├──▶ 3. Plotter: draw control plots (data vs. MC)
     │
     │  4. Histogrammer: make the input shapes for the fit
     ▼
  fit shapes
     │
     │  5. Fitter: run the fit with Combine
     ▼
  results (fitted values, scale factors, correction files)
```

Here's what each step does, and why it's there.

**1. PicoProducer** reads NanoAOD. NanoAOD is big and general: it has everything for everyone. PicoProducer goes
through it event by event, picks the events that fit your channel (for example one muon and one hadronic tau for
`mutau`), applies corrections and writes a much smaller file with just the variables you care about. That small
file is called a **pico tuple** ("pico" because it's even smaller than "nano"). This is the slow part. It runs as
many jobs on the batch system (HTCondor on lxplus) and can take hours.

**2. Histogrammer** reads the pico tuples and fills histograms. It knows about samples: which file is Drell-Yan,
which is ttbar, what their cross sections are. So it can scale every simulated sample to the right luminosity. It
also estimates backgrounds that simulation can't describe well, like QCD multijet, from data.

**3. Plotter** draws those histograms as control plots, the usual stacked MC with data on top and a ratio panel
below. Control plots are how you check that your selection and your simulation make sense before you trust a fit.

**4. Fit shapes** are histograms again, but made for the fit: one per region, working point and systematic variation,
in the format Combine expects. The Histogrammer makes them too.

**5. Fitter** runs [Combine](https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/) on the shapes and pulls out
the numbers you're measuring. Today the main workflow is the combined fit of the tau energy scale (TES) and the tau
ID scale factor, with a Z→μμ control region.

You don't have to run the whole chain every time. If someone already made the pico tuples you need, you can start
at step 2. If the shapes already exist, you can go straight to the fit.

## The Framework ties it together

Each of those steps is its own package, and you can still run each one by hand with its own scripts. People did that
for years. But it means remembering a lot of commands, the right order, and which output goes where.

The **Framework** does that bookkeeping for you. You describe your analysis once, in a short YAML file called a
**recipe**, and the Framework runs the steps in order:

```yaml
name: my_first_analysis
stages:
  - stage: production          # step 1: make pico tuples
    id: production
    inputs: null
    eras: [2022_postEE]
    channels: [mutau]
    samples: ["DY*", "TT*"]
```

Each step in the recipe is called a **stage**. The recipe, together with any config files it uses, lives in one
folder under `Analyses/`. That folder is called an **analysis bundle**. If you send it to a colleague, they have
your whole analysis.

When you start a recipe, you get a **run**: a folder that keeps everything from that attempt, including the outputs,
the logs and a record of where each stage is. Production takes hours, so TauFW doesn't sit there waiting. It submits
the jobs and stops. Later, maybe tomorrow, you tell it to continue. It checks the jobs, resubmits the ones that
failed, and moves on to the next stage once everything is done.

You can follow your analysis from the menu in the terminal. For shell commands, see
[Using FW with commands](../4-Concepts/UsingFWWithCommands.md).

## Where things are in the repository

You'll mostly touch the first two. The rest you'll get to know over time.

| Folder | What's in it |
| --- | --- |
| `Analyses/` | The analysis bundles: example recipes, and later your own |
| `Configs/` | Ready-made config files that recipes can use as a starting point |
| `PicoProducer/` | Step 1: NanoAOD → pico tuples. Includes the sample lists for each era |
| `Histogrammer/` | Steps 2 and 4: histograms and fit shapes |
| `Plotter/` | Step 3: drawing plots from histogram files |
| `Fitter/` | Step 5: the fits |
| `Framework/` | The part that reads recipes and runs the stages |
| `Utilities/` | Shared code: drawing style, the menu, helpers |
| `Tests/` | Automated tests |
| `Legacy/` | Old code we keep around for reference. You can ignore it |
| `Docs/` | This Manual, plus docs for developers |

## A few words you'll see a lot

- **Era**: a data-taking period with its own conditions, like `2022_postEE`. Samples, corrections and luminosity
  all depend on the era.
- **Channel**: which final state you select, like `mutau` (a muon and a hadronic tau) or `mumu`.
- **Sample**: one dataset, like Drell-Yan or ttbar simulation, or one run period of real data.
- **Working point (WP)**: how tight the tau ID cut is, like `Medium` or `VTight`.

There are more in the [Glossary](../4-Concepts/Glossary.md).

## What's next

Get TauFW installed with [FastSetup](../FastSetup.md). After that, [Your first session](FirstSession.md) walks you
through the menu and your first look at a recipe.
