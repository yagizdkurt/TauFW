# TauFW Manual

Welcome! This is the place to start if you're new to TauFW.
TauFW is the framework the CMS Tau group uses to go from NanoAOD all the way to a fit result!

## Where to start

If you've never used TauFW before, go through these in order:

1. **[What is TauFW?](1-GettingStarted/WhatIsTauFW.md)**: the big picture in ten minutes. What the pieces are and how
   data flows through them.
2. **Setting up:** [FastSetup](FastSetup.md) does the installation for you with one command. If you'd rather do it by
   hand, or something goes wrong, there's the [manual installation guide](ManualInstallation.md).
3. **[Your first session](1-GettingStarted/FirstSession.md)**: log in to lxplus, open the TauFW menu and look
   around without breaking anything.
4. **[Tutorial 1: your first production](2-Tutorials/01-FirstProduction.md)**: make real analysis ntuples with one
   of the example analyses.

Keep the **[Glossary](4-Concepts/Glossary.md)** open in another tab. TauFW has a lot of its own words (bundle,
stage, chunk, era...) and they're all explained there in plain language.

## What's in here

| Folder | What you'll find | Read it when... |
| --- | --- | --- |
| `1-GettingStarted/` | The big picture and your first steps | you're brand new |
| `2-Tutorials/` | Step-by-step lessons with real commands and real output | you want to learn by doing |
| `3-HowTo/` | Short answers to "how do I...?" questions | you know the basics and need to get something done |
| `4-Concepts/` | How things work under the hood, and why | something surprised you and you want to understand it |
| `Troubleshooting.md` | Error messages and what to do about them *(coming soon)* | something broke |
| `PicoProducer/` | Reference for the PicoProducer Python API and its files | you're writing code against PicoProducer |

The Manual is still being written. Pages marked *coming soon* don't exist yet.

## Other docs in the repository

The Manual is the gentle introduction. When you need every option and every detail, these are the full
references:

- [Analyses/README.md](../../Analyses/README.md): everything about writing recipes and analysis bundles.
- [Framework/README.md](../../Framework/README.md): how the Framework runs a pipeline, in detail.
- The package READMEs: [Histogrammer](../../Histogrammer/README.md), [Plotter](../../Plotter/README.md),
  [Fitter](../../Fitter/README.md), [Utilities](../../Utilities/README.md).
- [Tests/README.md](../../Tests/README.md): how to run the tests.
- `Docs/Develop/` is for people changing TauFW itself. You don't need it to use TauFW.
