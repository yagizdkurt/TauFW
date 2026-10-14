# TauFW Fitter

## Installation

See [the README.md in the parent directory](../../../#taufw).

## General comments:

* important information about samples, processes, systematics, variations etc. given in config file in yaml format
* an example yaml file is given in TauES/config/defaultFitSetupTES_mutau.yml 
  -- explanations are given as comments within the file
* this file is currently being used in TauES/createinputsTES.py and as the default `-c` of the TauES_ID harvest/fit scripts
  -- it can (and will) be used in further scipts / routines in the future
* each config file defines the setup for one specific channel
  -- combinations of channels can be done at datacard level, e.g. to include a mumu-CR
* you can easily make changes on cuts, observables, regions, etc. through the config file

## Creating inputs:

./TauES/createinputsTES.py -y UL2018 -c TauES/config/defaultFitSetupTES_mutau.yml

## Running the fit:

The TES-only fit (`doTES.sh`, `harvestDatacards_TES.py`, `makeFitTES.py`) is no longer maintained.
Its remaining scripts are in [Legacy/Fitter/TauES/](../../Legacy/Fitter/TauES/).
The current measurement is the combined TES + TauID fit; see
[../TauES_ID/README_2DTES_TauID_Fit.md](../TauES_ID/README_2DTES_TauID_Fit.md).
