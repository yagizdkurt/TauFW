# Contract: TES shapes (the input histograms of the TES / tau ID fit)

Written by `createinputsTES.py` (`Histogrammer/shapes/TauES/`, in `Fitter/TauES/` until step 2 of the isolation
work, CL §22), read by the fit (`Fitter/TauES_ID/harvestDatacards_TES_idSF_MCStat.py`, `harvestDatacards_zmm.py`). The two
sides never import each other; this page and the channel config (below) are all they share. In a TauFW recipe the
Framework carries the files from the `shapes` stage to the `fit` stage: the artifact `{kind: shapes, path, era,
channel, config, jet_wp, ele_wp, observable}` names a file (`TauFW.Histogrammer.api.TESShapes`, `_shape_files`;
the Fitter API's until CL §22 H3).

Unlike `control-histograms.md` this format has no version field and no metadata in the file: it is the format the fit
has read since 2021, written down as it is (CL §22, H0). Changing anything below means changing both sides together.

## File

One ROOT file per observable and channel config:

```
<dir>/ztt_<ch>_tes_<obs><DM>.inputs-<era>-13TeV<tag>.root
```

| Part | Value |
|---|---|
| `<dir>` | `<outbase>/againstjet_<J>/againstelectron_<E>/` (`-O`, default `input_pt_less_region`; `-j`, `-e`) |
| `<ch>` | the config's `channel` with `tau` -> `t`, `mu` -> `m`: `mutau` -> `mt`, `mumu` -> `mm` |
| `<obs>` | `observables.<o>.extra.filename`, else the observable's name |
| `<DM>` | `-d` (empty in every run script and in the API) |
| `<era>` | `-y`, e.g. `2025` |
| `<tag>` | the config's `tag`, e.g. `_mutau`, `_mumu` |

Example: `input_pt_less_region/againstjet_Medium/againstelectron_VVLoose/ztt_mt_tes_m_vis.inputs-2025-13TeV_mutau.root`.

Defined today in four places that must agree: the writer (`createinputsTES.py:238`), the two readers (both
`"%s/%s_%s_tes_%s.inputs-%s%s.root"` with `era='<year>-13TeV'`), the Histogrammer API (`tes_shapes.py`
`_shape_files`, the artifacts) and the fit preflight glob `*.inputs-<era>-*.root` (Fitter API `preflight_fit`).

## Inside

| Object | Name | Read by the fit |
|---|---|---|
| directory per region | the region's name (`DM0_pt1`, `baseline`) | yes: `$BIN` |
| nominal histogram | `<process>`, the config's `processes` (`ZTT ZL ZJ W VV ST TTT TTL TTJ QCD data_obs` for mutau, `ZL ZTT ZJ W VV ST TT QCD data_obs` for mumu); negative bins set to 0 | yes: `$BIN/$PROCESS` |
| TES point | `<process>_TES<value>` with three decimals and a dot: `ZTT_TES0.950` | yes: `$BIN/$PROCESS_TES$MASS`, masses `"%.3f"` of `TESvariations.values` |
| shape systematic | `<process>_<name with $BIN replaced by the region><Up/Down>`, e.g. `ZL_shape_mTauFake_DM0_pt1Up` | yes: `$BIN/$PROCESS_$SYSTEMATIC`, with `check_integral` |
| `stack*`, `plot_<process>_<syst>` (TCanvas), `style` (TStyle) | written by the control plots (`plotinputs`) | no |

Next to it, also not read by the fit: `rebinning/<the same file name>` (rebinned histograms and
`data_obs_nonztt_subtratced`) and the PNG control plots under `<dir>/plots/`.

The histograms of one file are written by several runs of `createinputs` into the same file (nominal, each TES point,
each shape systematic). It is opened with `UPDATE` (Histogrammer BUGS L20: a rerun into the same directory keeps
histograms of an earlier config).

## The channel config (read by both sides)

One YAML file per channel: the templates `Configs/Fitter/tes_id/config_coarse_{TT,PNet,UParT}.yml` and
`FitSetup_mumu.yml` (ids `fitter.tes_id_*`; `Fitter/TauES_ID/config/`, `Fitter/TauES/config/` until changelog §22
H2). In each template the top-level keys are grouped under banners by reader, as in the table below; a ROOT-free
test checks that every template has the keys both readers take without a default (`Tests/Framework/test_configs.py`,
`read_tes_id`). H = `createinputsTES.py`, F = the fit side
(harvest, `makecombinedfitTES_SF*.py`, `plotParabola_POI_region.py`, `plotPostFitScan_POI.py`, `runpostfit.py`,
`createroot_TES.py`, `make_tid_2025.py`, the Fitter API).

| Key | H | F |
|---|---|---|
| `channel` | yes | yes |
| `tag` | yes (file name) | yes (file name, card names, labels) |
| `baselineCuts` | yes (selection, working-point substitution) | yes, as text (measurement record of `plotParabola`) |
| `regions` (names), `.definition`, `.title`, `.binning` | yes | names, titles; definitions as text |
| `observables.<o>` (names, `binning`, `variable`, `extra`, `title`) | yes | names, `title`, `extra.filename` |
| `observables.<o>.fitRegions` | yes (which regions are filled) | yes (which cards) |
| `observables.<o>.scanRegions` | no | yes |
| `plottingOrder` | no (only the YAML anchor of the region list) | yes |
| `TESvariations.values` | yes (which shifted files and histograms) | yes (mass points, POI range) |
| `TESvariations.processes` | yes | no |
| `samples.*` (`filename`, `join`, `split`, `rename`, `data`, `removeSFs`, `addSFs`), `scaleFactors` | yes | no |
| `processes` | yes (the processes of the nominal) | yes (signals, backgrounds) |
| `systematics` with `effect: shape` | yes (all fields) | `name`, `processes`, `effect` |
| `systematics` with `effect: lnN` | no (skipped) | yes (`scaleFactor`) |
| `tesRegions`, `tid_SFRegions` | no | yes |
| `tagger` | yes (VSjet cut) | yes (labels, file names) |
| `fitSpecs` | no | no (read by nobody, kept) |

## Variation tuples (input of the writer)

A TES point or a shape systematic with `sampleAppend` reads `<sample>_<channel><tag>.root` next to the nominal tuple,
e.g. `..._mutau_TES0p950.root` (`("_TES%.3f"%v).replace(".","p")`), `..._mutau_LTF1p030.root`; the sum of weights is
read again from that file's cutflow. A missing file is only a warning when the sample set is made and fails later
(TODO §0: a preflight check after step 2).

## Checked by

- BBB `histogrammer.tes_inputs` (CL §22): the script end to end on fixture tuples, the shape file, the rebinned file
  and the names of the control plots; locked with the code before step 2 moved it. Not covered there: the working-point
  substitution (no `idDeepTau*` branches in the fixture) and the content of the LTF shapes (`ZL`, `TTL` are empty in
  the fixture's selection; TODO §7).
- BBB `fitter.shapes`, `fitter.rebin`: the writer (`createinputs`) and `rebinning` on their own.
- Real data (CL §22, H4, 2026-10-19): `Tests/tools/compare_shapefiles.py` compares two output directories (file
  names, every key, histograms in full, with a tolerance); the 2025 shapes of the code before and after step 2 were
  the same within the run-to-run noise of the fill, the LTF shapes included.
