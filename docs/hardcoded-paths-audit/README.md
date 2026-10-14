# Hardcoded paths audit

Found **228 active absolute path, fixed suffix, or remote storage endpoint occurrences** in **86 files** in current code/configuration and tests. Documentation and Legacy entries have been removed from all inventories. Source code was not changed.

[Focused inventory (CSV)](absolute-paths-and-storage.csv) | [Full static inventory (CSV)](inventory.csv)

The full inventory contains 6202 static candidates, including relative filenames, resource paths, templates, comments/examples, web URLs, and CMS dataset identifiers. Each row includes the exact file, line, path, and source text. Documentation tooling, docstring examples, documentation file references, and Legacy entries are excluded. These are not counts of portability bugs; standard system paths, backend routing prefixes, and repo-relative resources are often intentional.

This report filters the original scan of 626 source/script/config files. Formatted templates are retained where parsing permits; otherwise static fragments and full source expressions are shown. Runtime-generated paths cannot be exhaustively enumerated statically. Binary data and notebooks are outside this scan.

## Notable current-code findings

- `Fitter/python/HighPT/utilsHighPT.py:13?27`: seven personal `/eos/user/r/rasp` and `/afs/cern.ch/.../rasp` locations for inputs, figures, and datacards.
- `Fitter/HighPT/{CombineCardsHighPT,RunCombineHighPT,RunImpactsHighPT}.bash:4`: fixed rasp datacard directory.
- `Fitter/Zpt/copy2www.sh:15?26`: fixed `/t3home/ineuteli/eos/www/Zpt/` publishing targets.
- `PicoProducer/samples/`: fixed EOS/PNFS storage templates and XRootD endpoints; user and era names occur in several catalogs.
- `PicoProducer/python/settings/defaults.py:39?56`, storage backends, and batch templates: site-specific storage, scratch, CVMFS and temporary-directory assumptions.
- `Tau_Trigger_SF/Efficiency_plotters/` and `helper_scripts/hadd_files.py`: user names are dynamic, but EOS directory structures and sample filenames are fixed.
- `PicoProducer/python/corrections/{MetTriggerSF,WmassCorrection}.py`: `CMSSW_BASE` is dynamic, with fixed `/src/TauFW/PicoProducer/data/...` suffixes.

## Active absolute paths, fixed suffixes, and storage endpoints

### Current code/config

| File:line | Category | Path |
| --- | --- | --- |
| [Fitter/HighPT/CombineCardsHighPT.bash:4](C:/Users/WWW/Desktop/TauFW/Fitter/HighPT/CombineCardsHighPT.bash:4) | Absolute filesystem path | `/afs/cern.ch/work/r/rasp/public/HighPT_v2/datacards` |
| [Fitter/HighPT/RunCombineHighPT.bash:4](C:/Users/WWW/Desktop/TauFW/Fitter/HighPT/RunCombineHighPT.bash:4) | Absolute filesystem path | `/afs/cern.ch/work/r/rasp/public/HighPT_v2/datacards` |
| [Fitter/HighPT/RunImpactsHighPT.bash:4](C:/Users/WWW/Desktop/TauFW/Fitter/HighPT/RunImpactsHighPT.bash:4) | Absolute filesystem path | `/afs/cern.ch/work/r/rasp/public/HighPT_v2/datacards` |
| [Fitter/TauES_ID/makecombinedfitTES_SF_postfit_corrTES.py:194](C:/Users/WWW/Desktop/TauFW/Fitter/TauES_ID/makecombinedfitTES_SF_postfit_corrTES.py:194) | Absolute filesystem path | `/dev/null` |
| [Fitter/Zpt/copy2www.sh:15](C:/Users/WWW/Desktop/TauFW/Fitter/Zpt/copy2www.sh:15) | Absolute filesystem path | `/t3home/ineuteli/eos/www/Zpt/` |
| [Fitter/Zpt/copy2www.sh:21](C:/Users/WWW/Desktop/TauFW/Fitter/Zpt/copy2www.sh:21) | Absolute filesystem path | `/t3home/ineuteli/eos/www/Zpt/${era}/` |
| [Fitter/Zpt/copy2www.sh:23](C:/Users/WWW/Desktop/TauFW/Fitter/Zpt/copy2www.sh:23) | Absolute filesystem path | `/t3home/ineuteli/eos/www/Zpt/${era}/` |
| [Fitter/Zpt/copy2www.sh:24](C:/Users/WWW/Desktop/TauFW/Fitter/Zpt/copy2www.sh:24) | Absolute filesystem path | `/t3home/ineuteli/eos/www/Zpt/${era}/` |
| [Fitter/Zpt/copy2www.sh:25](C:/Users/WWW/Desktop/TauFW/Fitter/Zpt/copy2www.sh:25) | Absolute filesystem path | `/t3home/ineuteli/eos/www/Zpt/${era}/` |
| [Fitter/Zpt/copy2www.sh:26](C:/Users/WWW/Desktop/TauFW/Fitter/Zpt/copy2www.sh:26) | Absolute filesystem path | `/t3home/ineuteli/eos/www/Zpt/${era}/` |
| [Fitter/python/HighPT/utilsHighPT.py:13](C:/Users/WWW/Desktop/TauFW/Fitter/python/HighPT/utilsHighPT.py:13) | Absolute filesystem path | `/eos/user/r/rasp/output/HighPT` |
| [Fitter/python/HighPT/utilsHighPT.py:18](C:/Users/WWW/Desktop/TauFW/Fitter/python/HighPT/utilsHighPT.py:18) | Absolute filesystem path | `/afs/cern.ch/user/r/rasp/public/HighPT_v2/FF` |
| [Fitter/python/HighPT/utilsHighPT.py:19](C:/Users/WWW/Desktop/TauFW/Fitter/python/HighPT/utilsHighPT.py:19) | Absolute filesystem path | `/afs/cern.ch/user/r/rasp/public/HighPT_v2/MetTrigger` |
| [Fitter/python/HighPT/utilsHighPT.py:20](C:/Users/WWW/Desktop/TauFW/Fitter/python/HighPT/utilsHighPT.py:20) | Absolute filesystem path | `/afs/cern.ch/user/r/rasp/public/HighPT_v2/Sys` |
| [Fitter/python/HighPT/utilsHighPT.py:21](C:/Users/WWW/Desktop/TauFW/Fitter/python/HighPT/utilsHighPT.py:21) | Absolute filesystem path | `/afs/cern.ch/user/r/rasp/public/HighPT_v2/WMuNu` |
| [Fitter/python/HighPT/utilsHighPT.py:22](C:/Users/WWW/Desktop/TauFW/Fitter/python/HighPT/utilsHighPT.py:22) | Absolute filesystem path | `/afs/cern.ch/user/r/rasp/public/HighPT_v2/WTauNu_eta` |
| [Fitter/python/HighPT/utilsHighPT.py:27](C:/Users/WWW/Desktop/TauFW/Fitter/python/HighPT/utilsHighPT.py:27) | Absolute filesystem path | `/afs/cern.ch/work/r/rasp/public/HighPT_v2/datacards_eta` |
| [Fitter/run_workflow_zmm_corrTES.sh:51](C:/Users/WWW/Desktop/TauFW/Fitter/run_workflow_zmm_corrTES.sh:51) | Absolute filesystem path | `/dev/null` |
| [Fitter/run_workflow_zmm_corrTES_2526.sh:55](C:/Users/WWW/Desktop/TauFW/Fitter/run_workflow_zmm_corrTES_2526.sh:55) | Absolute filesystem path | `/dev/null` |
| [Fitter/run_workflow_zmm_pnet.sh:70](C:/Users/WWW/Desktop/TauFW/Fitter/run_workflow_zmm_pnet.sh:70) | Absolute filesystem path | `/dev/null` |
| [PicoProducer/data/pileup/checkBuggyPileup2017.sh:24](C:/Users/WWW/Desktop/TauFW/PicoProducer/data/pileup/checkBuggyPileup2017.sh:24) | Absolute filesystem path | `/afs/cern.ch/user/g/gurpreet/public/Fall17_oldPU.txt` |
| [PicoProducer/python/analysis/SumWeights.py:91](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/analysis/SumWeights.py:91) | Absolute filesystem path | `/store/mc/RunIISummer20UL18NanoAODv9/DYJetsToLL_M-50_TuneCP5_13TeV-amcatnloFXFX-pythia8/NANOAODSIM/106X_upgrade2018_realistic_v16_L1v1-v2/230000/7B930101-EB91-4F4E-9B90-0861460DBD94.root` |
| [PicoProducer/python/batch/templates/submit_HTCondor.sh:54](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_HTCondor.sh:54) | Absolute filesystem path | `/cvmfs/cms.cern.ch/` |
| [PicoProducer/python/batch/templates/submit_HTCondor.sh:55](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_HTCondor.sh:55) | Absolute filesystem path | `/cvmfs/cms.cern.ch/cmsset_default.sh` |
| [PicoProducer/python/batch/templates/submit_HTCondor.sh:57](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_HTCondor.sh:57) | Absolute filesystem path | `/cvmfs/cms.cern.ch/` |
| [PicoProducer/python/batch/templates/submit_SLURM.sh:25](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM.sh:25) | Absolute filesystem path | `/nfs/scratch/fynu/$USER/$JOBID.$TASKID` |
| [PicoProducer/python/batch/templates/submit_SLURM.sh:27](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM.sh:27) | Absolute filesystem path | `/scratch/$USER/$JOBID.$TASKID` |
| [PicoProducer/python/batch/templates/submit_SLURM.sh:50](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM.sh:50) | Absolute filesystem path | `/bin/sh` |
| [PicoProducer/python/batch/templates/submit_SLURM.sh:50](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM.sh:50) | Absolute filesystem path | `/cvmfs/unpacked.cern.ch/registry.hub.docker.com/cmssw/el7:x86_64` |
| [PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:25](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:25) | Absolute filesystem path | `/nfs/scratch/fynu/$USER/$JOBID.$TASKID` |
| [PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:27](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:27) | Absolute filesystem path | `/scratch/$USER/$JOBID.$TASKID` |
| [PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:49](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:49) | Absolute filesystem path | `/bin/sh` |
| [PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:49](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/batch/templates/submit_SLURM_UCL.sh:49) | Absolute filesystem path | `/cvmfs/unpacked.cern.ch/registry.hub.docker.com/cmssw/el7:x86_64` |
| [PicoProducer/python/settings/defaults.py:39](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/settings/defaults.py:39) | Absolute filesystem path | `/eos/user/%s/%s/` |
| [PicoProducer/python/settings/defaults.py:41](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/settings/defaults.py:41) | Absolute filesystem path | `/pnfs/psi.ch/cms/trivcat/store/user/%s/` |
| [PicoProducer/python/settings/defaults.py:43](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/settings/defaults.py:43) | Absolute filesystem path | `/store/user/{}/` |
| [PicoProducer/python/settings/defaults.py:49](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/settings/defaults.py:49) | Absolute filesystem path | `/tmp/%s/` |
| [PicoProducer/python/settings/defaults.py:52](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/settings/defaults.py:52) | Absolute filesystem path | `/eos/user/%s/%s/` |
| [PicoProducer/python/settings/defaults.py:56](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/settings/defaults.py:56) | Absolute filesystem path | `/tmp/{}/` |
| [PicoProducer/python/storage/base.py:44](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/base.py:44) | Absolute filesystem path | `/tmp/` |
| [PicoProducer/python/storage/base.py:107](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/base.py:107) | Absolute filesystem path | `/dev/null` |
| [PicoProducer/python/storage/factory.py:24](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/factory.py:24) | Absolute filesystem path | `/eos/` |
| [PicoProducer/python/storage/factory.py:29](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/factory.py:29) | Absolute filesystem path | `/pnfs/psi.ch/` |
| [PicoProducer/python/storage/factory.py:32](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/factory.py:32) | Absolute filesystem path | `/pnfs/desy.de/` |
| [PicoProducer/python/storage/factory.py:35](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/factory.py:35) | Absolute filesystem path | `/store/user` |
| [PicoProducer/python/storage/factory.py:38](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/factory.py:38) | Absolute filesystem path | `/pnfs/lcg.cscs.ch/` |
| [PicoProducer/python/storage/gridka_nrg.py:29](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:29) | Absolute filesystem path | `/tmp/` |
| [PicoProducer/python/storage/gridka_nrg.py:31](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:31) | Absolute filesystem path | `/storage/gridka-nrg/` |
| [PicoProducer/python/storage/gridka_nrg.py:74](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:74) | Absolute filesystem path | `/store/user/` |
| [PicoProducer/python/storage/t2_psi.py:32](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_psi.py:32) | Absolute filesystem path | `/scratch/` |
| [PicoProducer/python/storage/t3_psi.py:32](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t3_psi.py:32) | Absolute filesystem path | `/scratch/` |
| [PicoProducer/python/workers/picojob.py:69](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/workers/picojob.py:69) | Absolute filesystem path | `/store/mc/RunIISummer20UL18NanoAODv2/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/NANOAODSIM/106X_upgrade2018_realistic_v15_L1v1-v1/50000/C9EAE9C3-7392-6B48-8FD2-A2DCA1C6B2C7.root` |
| [PicoProducer/python/workers/picojob.py:70](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/workers/picojob.py:70) | Absolute filesystem path | `/store/mc/RunIISummer20UL18NanoAODv2/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/NANOAODSIM/106X_upgrade2018_realistic_v15_L1v1-v1/50000/04BBC240-E6D5-824C-9688-835C8D1D9C12.root` |
| [PicoProducer/python/workers/skimjob.py:58](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/workers/skimjob.py:58) | Absolute filesystem path | `/store/mc/RunIISummer20UL18NanoAODv2/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/NANOAODSIM/106X_upgrade2018_realistic_v15_L1v1-v1/50000/C9EAE9C3-7392-6B48-8FD2-A2DCA1C6B2C7.root` |
| [PicoProducer/python/workers/skimjob.py:59](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/workers/skimjob.py:59) | Absolute filesystem path | `/store/mc/RunIISummer20UL18NanoAODv2/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/NANOAODSIM/106X_upgrade2018_realistic_v15_L1v1-v1/50000/04BBC240-E6D5-824C-9688-835C8D1D9C12.root` |
| [PicoProducer/samples/CMSDAS2020/samples_mutau_2018_preselected.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/CMSDAS2020/samples_mutau_2018_preselected.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/CMSDAS2020/nano/2018/$DAS` |
| [PicoProducer/samples/HighPT/samples_UL2018.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/HighPT/samples_UL2018.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nanoV10/Run2_2018/$SAMPLE` |
| [PicoProducer/samples/PODAS23/samples_2022_postEE.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/PODAS23/samples_2022_postEE.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22_postEE/$DAS` |
| [PicoProducer/samples/PODAS23/samples_2022_postEE.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/PODAS23/samples_2022_postEE.py:4) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22_postEE_new/$DAS` |
| [PicoProducer/samples/PODAS23/samples_2022_postEE.py:5](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/PODAS23/samples_2022_postEE.py:5) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22/$DAS` |
| [PicoProducer/samples/PODAS23/samples_2022_preEE.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/PODAS23/samples_2022_preEE.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22/$DAS` |
| [PicoProducer/samples/TauID/samples_2016.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_2016.py:3) | Absolute filesystem path | `/pnfs/psi.ch/cms/trivcat/store/user/ineuteli/samples/NANOAOD_2016/$PATH` |
| [PicoProducer/samples/TauID/samples_2016.py:5](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_2016.py:5) | Absolute filesystem path | `/pnfs/lcg.cscs.ch/cms/trivcat/store/user/areimers/NANOAOD/2016/LQTChannel/$PATH` |
| [PicoProducer/samples/TauID/samples_2017.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_2017.py:3) | Absolute filesystem path | `/pnfs/psi.ch/cms/trivcat/store/user/$USER/samples/NANOAOD_2017/$PATH` |
| [PicoProducer/samples/TauID/samples_2017.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_2017.py:4) | Absolute filesystem path | `/pnfs/lcg.cscs.ch/cms/trivcat/store/user/areimers/NANOAOD/LQTChannel/$PATH` |
| [PicoProducer/samples/TauID/samples_2018.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_2018.py:3) | Absolute filesystem path | `/pnfs/psi.ch/cms/trivcat/store/user/$USER/samples/NANOAOD_2018/$PATH` |
| [PicoProducer/samples/TauID/samples_2018.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_2018.py:4) | Absolute filesystem path | `/pnfs/lcg.cscs.ch/cms/trivcat/store/user/areimers/NANOAOD/2018/LQTChannel/$PATH` |
| [PicoProducer/samples/TauID/samples_UL2016_postVFP.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_UL2016_postVFP.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nano/UL2016_postVFP/$DAS` |
| [PicoProducer/samples/TauID/samples_UL2016_preVFP.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_UL2016_preVFP.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nano/UL2016_preVFP/$DAS` |
| [PicoProducer/samples/TauID/samples_UL2017.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_UL2017.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nano/UL2017/$DAS` |
| [PicoProducer/samples/TauID/samples_UL2018.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_UL2018.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nano/UL2018/$DAS` |
| [PicoProducer/samples/samples_2022_postEE.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2022_postEE.py:4) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22_postEE/$DAS` |
| [PicoProducer/samples/samples_2022_postEE.py:5](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2022_postEE.py:5) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22_postEE_new/$DAS` |
| [PicoProducer/samples/samples_2022_postEE.py:6](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2022_postEE.py:6) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22/$DAS` |
| [PicoProducer/samples/samples_2022_preEE.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2022_preEE.py:4) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22/$DAS` |
| [PicoProducer/samples/samples_UL2016_postVFP_nanoV10.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2016_postVFP_nanoV10.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nanoV10/Run2_2016/$DAS` |
| [PicoProducer/samples/samples_UL2016_preVFP_nanoV10.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2016_preVFP_nanoV10.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nanoV10/Run2_2016_HIPM/$DAS` |
| [PicoProducer/samples/samples_UL2017_nanoV10.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2017_nanoV10.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nanoV10/Run2_2017/$DAS` |
| [PicoProducer/samples/samples_UL2018.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2018.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nano/UL2018/$DAS` |
| [PicoProducer/samples/samples_UL2018_nanoV10.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2018_nanoV10.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nanoV10/Run2_2018/$DAS` |
| [PicoProducer/samples/samples_UL2018v10.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2018v10.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/TauFW/nanoV10/Run2_2018/$DAS` |
| [PicoProducer/samples/tutorial/samples_2022_postEE.py:3](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/tutorial/samples_2022_postEE.py:3) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22_postEE/$DAS` |
| [PicoProducer/samples/tutorial/samples_2022_postEE.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/tutorial/samples_2022_postEE.py:4) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22_postEE_new/$DAS` |
| [PicoProducer/samples/tutorial/samples_2022_postEE.py:5](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/tutorial/samples_2022_postEE.py:5) | Absolute filesystem path | `/eos/cms/store/group/phys_tau/irandreo/Run3_22/$DAS` |
| [PicoProducer/utils/cleanWNs_SLURM.sh:25](C:/Users/WWW/Desktop/TauFW/PicoProducer/utils/cleanWNs_SLURM.sh:25) | Absolute filesystem path | `/scratch/$USER/*/*/*` |
| [PicoProducer/utils/cleanWNs_SLURM.sh:37](C:/Users/WWW/Desktop/TauFW/PicoProducer/utils/cleanWNs_SLURM.sh:37) | Absolute filesystem path | `/scratch/$USER` |
| [PicoProducer/utils/setupVOMS.sh:10](C:/Users/WWW/Desktop/TauFW/PicoProducer/utils/setupVOMS.sh:10) | Absolute filesystem path | `/cvmfs/cms.cern.ch` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:39](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:39) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/{year}/Data` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:40](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:40) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/{year}/plots` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:66](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:66) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/2024/Data/era_wise/Muon_Run2024D_mutau.root` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:67](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_data_generic.py:67) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/2024/Data/era_wise/Muon_Run2024I_mutau.root` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_datavsmc.py:20](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_datavsmc.py:20) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/{year}/Data/Muon_Run{year}_mutau.root` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_datavsmc.py:21](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_datavsmc.py:21) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/{year}/DY/DYto2Tau-4Jets_Bin-MLL-50_Fil-MuTauh_mutau.root` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_datavsmc.py:23](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_datavsmc.py:23) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/{year}/plots` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_dtauvspnet.py:12](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_dtauvspnet.py:12) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/2024/Data/Muon_Run2024_mutau.root` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_dtauvspnet.py:13](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_dtauvspnet.py:13) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/2024/DY/DYto2Tau-4Jets_Bin-MLL-50_Fil-MuTauh_mutau.root` |
| [Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_dtauvspnet.py:15](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/Efficiency_plotters/Trigger_Efficiency_dtauvspnet.py:15) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/2024/plots` |
| [Tau_Trigger_SF/helper_scripts/hadd_files.py:57](C:/Users/WWW/Desktop/TauFW/Tau_Trigger_SF/helper_scripts/hadd_files.py:57) | Absolute filesystem path | `/eos/user/{user[0]}/{user}/analysis/{year}/Data` |
| [Utilities/FastSetup.sh:18](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:18) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:184](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:184) | Absolute filesystem path | `/etc/os-release` |
| [Utilities/FastSetup.sh:185](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:185) | Absolute filesystem path | `/cvmfs/cms.cern.ch/cmsset_default.sh` |
| [Utilities/FastSetup.sh:333](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:333) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:337](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:337) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:339](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:339) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:435](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:435) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:436](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:436) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:562](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:562) | Absolute filesystem path | `/etc/os-release` |
| [Utilities/FastSetup.sh:564](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:564) | Absolute filesystem path | `/etc/os-release` |
| [Utilities/FastSetup.sh:565](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:565) | Absolute filesystem path | `/etc/os-release` |
| [Utilities/FastSetup.sh:576](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:576) | Absolute filesystem path | `/cvmfs/cms.cern.ch/cmsset_default.sh` |
| [Utilities/FastSetup.sh:581](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:581) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:655](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:655) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:661](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:661) | Absolute filesystem path | `/dev/null` |
| [Utilities/FastSetup.sh:706](C:/Users/WWW/Desktop/TauFW/Utilities/FastSetup.sh:706) | Absolute filesystem path | `/dev/null` |
| [Utilities/_audit_io.py:141](C:/Users/WWW/Desktop/TauFW/Utilities/_audit_io.py:141) | Absolute filesystem path | `/storage/` |
| [Utilities/python/Installer/_python_environment.py:10](C:/Users/WWW/Desktop/TauFW/Utilities/python/Installer/_python_environment.py:10) | Absolute filesystem path | `/cvmfs` |
| [setup.sh:16](C:/Users/WWW/Desktop/TauFW/setup.sh:16) | Absolute filesystem path | `/dev/null` |
| [setup.sh:84](C:/Users/WWW/Desktop/TauFW/setup.sh:84) | Absolute filesystem path | `/dev/null` |
| [setup.sh:117](C:/Users/WWW/Desktop/TauFW/setup.sh:117) | Absolute filesystem path | `/dev/null` |
| [Fitter/HighPT/DatacardsWToTauNu.py:375](C:/Users/WWW/Desktop/TauFW/Fitter/HighPT/DatacardsWToTauNu.py:375) | Fixed path suffix | `/src/TauFW/Plotter/data/ff_HighPT/ff_` |
| [Fitter/HighPT/FakeFactorHighPt.py:288](C:/Users/WWW/Desktop/TauFW/Fitter/HighPT/FakeFactorHighPt.py:288) | Fixed path suffix | `/src/TauFW/Plotter/data/ff_HighPT/ff_` |
| [Fitter/HighPT/MetTrigger.py:107](C:/Users/WWW/Desktop/TauFW/Fitter/HighPT/MetTrigger.py:107) | Fixed path suffix | `/src/TauFW/PicoProducer/data/trigger/mettrigger_` |
| [PicoProducer/python/corrections/MetTriggerSF.py:8](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/corrections/MetTriggerSF.py:8) | Fixed path suffix | `/src/TauFW/PicoProducer/data/trigger/` |
| [PicoProducer/python/corrections/WmassCorrection.py:7](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/corrections/WmassCorrection.py:7) | Fixed path suffix | `/src/TauFW/PicoProducer/data/Wstar/` |
| [PicoProducer/python/analysis/SumWeights.py:89](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/analysis/SumWeights.py:89) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/python/datasets/sample.py:42](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/datasets/sample.py:42) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/python/datasets/sample.py:42](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/datasets/sample.py:42) | Remote endpoint / URL | `root://cmsxrootd.fnal.gov/` |
| [PicoProducer/python/datasets/sample.py:42](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/datasets/sample.py:42) | Remote endpoint / URL | `root://xrootd-cms.infn.it/` |
| [PicoProducer/python/datasets/sample.py:92](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/datasets/sample.py:92) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/python/storage/eos.py:26](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/eos.py:26) | Remote endpoint / URL | `root://eosuser.cern.ch/` |
| [PicoProducer/python/storage/eos.py:29](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/eos.py:29) | Remote endpoint / URL | `root://eosuser.cern.ch` |
| [PicoProducer/python/storage/gridka_nrg.py:22](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:22) | Remote endpoint / URL | `root://cmsxrootd-kit.gridka.de/` |
| [PicoProducer/python/storage/gridka_nrg.py:24](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:24) | Remote endpoint / URL | `root://cmsxrootd-kit.gridka.de/` |
| [PicoProducer/python/storage/gridka_nrg.py:26](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:26) | Remote endpoint / URL | `root://cmsxrootd-kit.gridka.de/` |
| [PicoProducer/python/storage/gridka_nrg.py:28](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:28) | Remote endpoint / URL | `root://cmsxrootd-kit.gridka.de/` |
| [PicoProducer/python/storage/gridka_nrg.py:30](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/gridka_nrg.py:30) | Remote endpoint / URL | `root://cmsxrootd-kit.gridka.de/` |
| [PicoProducer/python/storage/t2_desy.py:49](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_desy.py:49) | Remote endpoint / URL | `srm://dcache-se-cms.desy.de:8443/srm/managerv2?SFN=%s` |
| [PicoProducer/python/storage/t2_desy.py:51](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_desy.py:51) | Remote endpoint / URL | `srm://dcache-se-cms.desy.de:8443/srm/managerv2?SFN=%s` |
| [PicoProducer/python/storage/t2_desy.py:57](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_desy.py:57) | Remote endpoint / URL | `srm://dcache-se-cms.desy.de:8443/srm/managerv2?SFN=%s` |
| [PicoProducer/python/storage/t2_desy.py:72](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_desy.py:72) | Remote endpoint / URL | `srm://dcache-se-cms.desy.de:8443/%s/%s` |
| [PicoProducer/python/storage/t2_desy.py:79](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_desy.py:79) | Remote endpoint / URL | `srm://dcache-se-cms.desy.de:8443/%s/%s` |
| [PicoProducer/python/storage/t2_psi.py:23](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_psi.py:23) | Remote endpoint / URL | `gsiftp://storage01.lcg.cscs.ch/` |
| [PicoProducer/python/storage/t2_psi.py:31](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_psi.py:31) | Remote endpoint / URL | `gsiftp://storage01.lcg.cscs.ch/` |
| [PicoProducer/python/storage/t2_psi.py:33](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t2_psi.py:33) | Remote endpoint / URL | `root://storage01.lcg.cscs.ch/` |
| [PicoProducer/python/storage/t3_psi.py:24](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t3_psi.py:24) | Remote endpoint / URL | `gsiftp://t3se01.psi.ch/` |
| [PicoProducer/python/storage/t3_psi.py:26](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t3_psi.py:26) | Remote endpoint / URL | `gsiftp://t3se01.psi.ch/` |
| [PicoProducer/python/storage/t3_psi.py:28](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t3_psi.py:28) | Remote endpoint / URL | `gsiftp://t3se01.psi.ch/` |
| [PicoProducer/python/storage/t3_psi.py:30](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t3_psi.py:30) | Remote endpoint / URL | `root://t3dcachedb03.psi.ch/` |
| [PicoProducer/python/storage/t3_psi.py:31](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/storage/t3_psi.py:31) | Remote endpoint / URL | `root://t3dcachedb03.psi.ch/` |
| [PicoProducer/python/workers/picojob.py:57](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/workers/picojob.py:57) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/python/workers/skimjob.py:45](C:/Users/WWW/Desktop/TauFW/PicoProducer/python/workers/skimjob.py:45) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/CMSDAS2020/samples_mutau_2018_preselected.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/CMSDAS2020/samples_mutau_2018_preselected.py:4) | Remote endpoint / URL | `root://eoscms.cern.ch/` |
| [PicoProducer/samples/PODAS23/samples_2022_postEE.py:6](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/PODAS23/samples_2022_postEE.py:6) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/PODAS23/samples_2022_preEE.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/PODAS23/samples_2022_preEE.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/TauID/samples_UL2018.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/TauID/samples_UL2018.py:4) | Remote endpoint / URL | `root://eosuser.cern.ch/` |
| [PicoProducer/samples/Tau_trig_SF_samples/2024/samples_2024_DY.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/Tau_trig_SF_samples/2024/samples_2024_DY.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/Tau_trig_SF_samples/2024/samples_2024_data.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/Tau_trig_SF_samples/2024/samples_2024_data.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/Tau_trig_SF_samples/2025/samples_2025_DY.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/Tau_trig_SF_samples/2025/samples_2025_DY.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/Tau_trig_SF_samples/2025/samples_2025_data.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/Tau_trig_SF_samples/2025/samples_2025_data.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_2022_postEE.py:7](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2022_postEE.py:7) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_2022_preEE.py:5](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2022_preEE.py:5) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_2023C.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2023C.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_2023D.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2023D.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_2024.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2024.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_2024v15.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2024v15.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_2025.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_2025.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_UL2016_postVFP_nanoV10.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2016_postVFP_nanoV10.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_UL2016_preVFP_nanoV10.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2016_preVFP_nanoV10.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_UL2017_nanoV10.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2017_nanoV10.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/samples_UL2018_nanoV10.py:4](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/samples_UL2018_nanoV10.py:4) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/samples/tutorial/samples_2022_postEE.py:6](C:/Users/WWW/Desktop/TauFW/PicoProducer/samples/tutorial/samples_2022_postEE.py:6) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/utils/convertGENSIM.py:769](C:/Users/WWW/Desktop/TauFW/PicoProducer/utils/convertGENSIM.py:769) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [PicoProducer/utils/getXSec.sh:22](C:/Users/WWW/Desktop/TauFW/PicoProducer/utils/getXSec.sh:22) | Remote endpoint / URL | `root://xrootd-cms.infn.it` |

### Tests

| File:line | Category | Path |
| --- | --- | --- |
| [Tests/BBB/pico_harness.py:31](C:/Users/WWW/Desktop/TauFW/Tests/BBB/pico_harness.py:31) | Absolute filesystem path | `/usr/bin/env` |
| [Tests/BBB/pico_harness.py:45](C:/Users/WWW/Desktop/TauFW/Tests/BBB/pico_harness.py:45) | Absolute filesystem path | `/usr/bin/env` |
| [Tests/Fitter/api/test_tes_id.py:88](C:/Users/WWW/Desktop/TauFW/Tests/Fitter/api/test_tes_id.py:88) | Absolute filesystem path | `/bin/` |
| [Tests/PicoProducer/processors/test.py:95](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/processors/test.py:95) | Absolute filesystem path | `/store/user/aakhmets/taupog/nanoAOD/DYJetsToLLM50_RunIIFall17MiniAODv2_PU2017RECOSIMstep_13TeV_MINIAOD_madgraph-pythia8_v1/67/myNanoProdMc2017_NANO_66.root` |
| [Tests/PicoProducer/processors/test.py:96](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/processors/test.py:96) | Absolute filesystem path | `/store/user/aakhmets/taupog/nanoAOD/DYJetsToLLM50_RunIIFall17MiniAODv2_PU2017RECOSIMstep_13TeV_MINIAOD_madgraph-pythia8_v1/68/myNanoProdMc2017_NANO_67.root` |
| [Tests/PicoProducer/processors/testBookkeeper.py:56](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/processors/testBookkeeper.py:56) | Absolute filesystem path | `/store/mc/RunIISummer20UL18NanoAODv2/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/NANOAODSIM/106X_upgrade2018_realistic_v15_L1v1-v1/50000/C9EAE9C3-7392-6B48-8FD2-A2DCA1C6B2C7.root` |
| [Tests/PicoProducer/processors/testBookkeeper.py:57](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/processors/testBookkeeper.py:57) | Absolute filesystem path | `/store/mc/RunIISummer20UL18NanoAODv2/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/NANOAODSIM/106X_upgrade2018_realistic_v15_L1v1-v1/50000/04BBC240-E6D5-824C-9688-835C8D1D9C12.root` |
| [Tests/PicoProducer/testEventBased.py:120](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/testEventBased.py:120) | Absolute filesystem path | `/scratch/ineuteli/analysis/2016/DY/DYJetsToLL_M-2000to3000_tautau.root` |
| [Tests/PicoProducer/testEventBased.py:121](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/testEventBased.py:121) | Absolute filesystem path | `/scratch/ineuteli/analysis/2016/DY/DYJetsToLL_M-2000to3000_tautau_test.root` |
| [Tests/Plotter/testMacros.py:144](C:/Users/WWW/Desktop/TauFW/Tests/Plotter/testMacros.py:144) | Absolute filesystem path | `/t3home/ineuteli/eos/public/forTAU/TauID_SF_dm_DeepTau2017v2p1VSjet_2016Legacy_ptgt20.root` |
| [Tests/Plotter/testMacros.py:160](C:/Users/WWW/Desktop/TauFW/Tests/Plotter/testMacros.py:160) | Absolute filesystem path | `/scratch/ineuteli/analysis/UL2018/DY/DYJetsToLL_M-50_mutau.root` |
| [Tests/Plotter/testMacros.py:219](C:/Users/WWW/Desktop/TauFW/Tests/Plotter/testMacros.py:219) | Absolute filesystem path | `/t3home/ineuteli/eos/public/forTAU/TauID_SF_dm_DeepTau2017v2p1VSjet_2016Legacy_ptgt20.root` |
| [Tests/Plotter/testMacros.py:233](C:/Users/WWW/Desktop/TauFW/Tests/Plotter/testMacros.py:233) | Absolute filesystem path | `/scratch/ineuteli/analysis/UL2018/DY/DYJetsToLL_M-50_mutau.root` |
| [Tests/Plotter/testMultiThread.py:119](C:/Users/WWW/Desktop/TauFW/Tests/Plotter/testMultiThread.py:119) | Absolute filesystem path | `/eos/user/i/ineuteli/analysis/g-2/UL2018/Data/SingleMuon_Run2018B_mumu.root` |
| [Tests/Plotter/testRDataFrame.py:143](C:/Users/WWW/Desktop/TauFW/Tests/Plotter/testRDataFrame.py:143) | Absolute filesystem path | `/scratch/ineuteli/analysis/UL2018` |
| [Tests/Setup/test_fastsetup.py:126](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_fastsetup.py:126) | Absolute filesystem path | `/tmp/result` |
| [Tests/Setup/test_setup_runner.py:135](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_runner.py:135) | Absolute filesystem path | `/tmp/installation.log` |
| [Tests/Setup/test_setup_runner.py:141](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_runner.py:141) | Absolute filesystem path | `/tmp/installation.log` |
| [Tests/Setup/test_setup_runner.py:176](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_runner.py:176) | Absolute filesystem path | `/tmp/retained` |
| [Tests/Setup/test_setup_runner.py:186](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_runner.py:186) | Absolute filesystem path | `/tmp/retained` |
| [Tests/Setup/test_setup_runner.py:196](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_runner.py:196) | Absolute filesystem path | `/tmp/result` |
| [Tests/Setup/test_setup_runner.py:218](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_runner.py:218) | Absolute filesystem path | `/bin/bash` |
| [Tests/Setup/test_setup_runner.py:239](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_runner.py:239) | Absolute filesystem path | `/bin/bash` |
| [Tests/Setup/test_setup_wrapper.py:28](C:/Users/WWW/Desktop/TauFW/Tests/Setup/test_setup_wrapper.py:28) | Absolute filesystem path | `/usr/bin/env` |
| [Tests/Utilities/test_file_io.py:120](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_file_io.py:120) | Absolute filesystem path | `C:\new\1` |
| [Tests/Utilities/test_file_io.py:122](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_file_io.py:122) | Absolute filesystem path | `C:\new\1` |
| [Tests/Utilities/test_process.py:107](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_process.py:107) | Absolute filesystem path | `/work` |
| [Tests/Utilities/test_process.py:109](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_process.py:109) | Absolute filesystem path | `/work` |
| [Tests/Utilities/test_process.py:122](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_process.py:122) | Absolute filesystem path | `/work` |
| [Tests/Utilities/test_remote_root.py:69](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:69) | Absolute filesystem path | `/store/user/file.root` |
| [Tests/Utilities/test_remote_root.py:71](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:71) | Absolute filesystem path | `/store/other/file.root` |
| [Tests/PicoProducer/analysis/TestModule.py:80](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/analysis/TestModule.py:80) | Remote endpoint / URL | `root://eosuser.cern.ch//eos/cms/store/group/phys_tau/TauFW/nano/UL2018/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/RunIISummer20UL18NanoAODv2-106X_upgrade2018_realistic_v15_L1v1-v1/NANOAODSIM/C9EAE9C3-7392-6B48-8FD2-A2DCA1C6B2C7_skimjec_0.root` |
| [Tests/PicoProducer/analysis/TestModule.py:81](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/analysis/TestModule.py:81) | Remote endpoint / URL | `root://eosuser.cern.ch//eos/cms/store/group/phys_tau/TauFW/nano/UL2018/DYJetsToLL_M-50_TuneCP5_13TeV-madgraphMLM-pythia8/RunIISummer20UL18NanoAODv2-106X_upgrade2018_realistic_v15_L1v1-v1/NANOAODSIM/C9EAE9C3-7392-6B48-8FD2-A2DCA1C6B2C7_skimjec_1.root` |
| [Tests/PicoProducer/processors/test.py:90](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/processors/test.py:90) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [Tests/PicoProducer/processors/testBookkeeper.py:54](C:/Users/WWW/Desktop/TauFW/Tests/PicoProducer/processors/testBookkeeper.py:54) | Remote endpoint / URL | `root://cms-xrd-global.cern.ch/` |
| [Tests/Utilities/test_remote_root.py:19](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:19) | Remote endpoint / URL | `root://storage.example//store/space` |
| [Tests/Utilities/test_remote_root.py:29](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:29) | Remote endpoint / URL | `root://storage.example//store/file.root` |
| [Tests/Utilities/test_remote_root.py:48](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:48) | Remote endpoint / URL | `srm://storage.example/srm/managerv2?SFN=/pnfs/user&token=opaque` |
| [Tests/Utilities/test_remote_root.py:53](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:53) | Remote endpoint / URL | `srm://storage.example/srm/managerv2?SFN=/pnfs/user/file%20name.json.gz&token=opaque` |
| [Tests/Utilities/test_remote_root.py:58](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:58) | Remote endpoint / URL | `gsiftp://storage.example/path/file` |
| [Tests/Utilities/test_remote_root.py:68](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:68) | Remote endpoint / URL | `root://storage.example//store/user` |
| [Tests/Utilities/test_remote_root.py:76](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:76) | Remote endpoint / URL | `root://one.example//store/file.root` |
| [Tests/Utilities/test_remote_root.py:77](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:77) | Remote endpoint / URL | `root://two.example//store/file.root` |
| [Tests/Utilities/test_remote_root.py:88](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:88) | Remote endpoint / URL | `root://one.example:1094/store/file.root` |
| [Tests/Utilities/test_remote_root.py:93](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:93) | Remote endpoint / URL | `gsiftp://two.example/path/file` |
| [Tests/Utilities/test_remote_root.py:93](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:93) | Remote endpoint / URL | `root://one.example//store/file` |
| [Tests/Utilities/test_remote_root.py:95](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:95) | Remote endpoint / URL | `srm://two.example/path/file` |
| [Tests/Utilities/test_remote_root.py:96](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:96) | Remote endpoint / URL | `file:///` |
| [Tests/Utilities/test_remote_root.py:100](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:100) | Remote endpoint / URL | `root://storage.example//store/config.json.gz` |
| [Tests/Utilities/test_remote_root.py:124](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:124) | Remote endpoint / URL | `root://storage.example//store/..\..\outside.json` |
| [Tests/Utilities/test_remote_root.py:139](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:139) | Remote endpoint / URL | `root://storage.example//store/user` |
| [Tests/Utilities/test_remote_root.py:152](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:152) | Remote endpoint / URL | `srm://storage.example/srm?SFN=/pnfs/user&token=opaque` |
| [Tests/Utilities/test_remote_root.py:153](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:153) | Remote endpoint / URL | `srm://storage.example/srm?SFN=/pnfs/user/file&token=opaque` |
| [Tests/Utilities/test_remote_root.py:199](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:199) | Remote endpoint / URL | `root://storage.example//store/input.root` |
| [Tests/Utilities/test_remote_root.py:207](C:/Users/WWW/Desktop/TauFW/Tests/Utilities/test_remote_root.py:207) | Remote endpoint / URL | `gsiftp://storage.example/path/output.root` |

## Full inventory counts

| Category | Occurrences |
| --- | ---: |
| Absolute filesystem path | 381 |
| CMS dataset identifier | 1354 |
| Directory / filename component | 191 |
| Fixed path suffix | 5 |
| Path suffix / logical name | 388 |
| Relative path / filename | 2651 |
| Relative path / template | 821 |
| Remote endpoint / URL | 411 |

## Scan limitations

- Fitter/Zpt/utils.py:20: Python AST unavailable (Missing parentheses in call to 'print'. Did you mean print(...)?); tokens still scanned
- Fitter/Zpt/config/samples.py:69: Python AST unavailable (Missing parentheses in call to 'print'. Did you mean print(...)?); tokens still scanned
- PicoProducer/utils/getDASParents.py:14: Python AST unavailable (Missing parentheses in call to 'print'. Did you mean print(...)?); tokens still scanned
- PicoProducer/utils/convertGENSIM.py:29: Python AST unavailable (Missing parentheses in call to 'print'. Did you mean print(...)?); tokens still scanned
- PicoProducer/utils/checkEvents.py:23: Python AST unavailable (Missing parentheses in call to 'print'. Did you mean print(...)?); tokens still scanned
- Fitter/HighPT/createinputs.py:121: Python AST unavailable (Missing parentheses in call to 'print'. Did you mean print(...)?); tokens still scanned
- Fitter/ETauFR/writedatacard.py:19: Python AST unavailable (Missing parentheses in call to 'print'. Did you mean print(...)?); tokens still scanned
- Tests/PicoProducer/testSample.py:90: Python AST unavailable ('(' was never closed); tokens still scanned
- Tests/PicoProducer/testSample.py: token scan incomplete: ('unexpected EOF in multi-line statement', (123, 0))
