#! /usr/bin/env python
"""
Postfit step for the CORRELATED-TES variant.

Sibling of makecombinedfitTES_SF_postfit.py. Iterates per DM (not per region):
 - reads the per-DM param file written by makecombinedfitTES_SF_corrTES.py
   (best-fits, 1σ ranges, nuisance seeds for tes_DM<X> + tid_SF_DM<X>_pt{1,2,3})
 - runs FitDiagnostics on the per-DM combined workspace with all 4 POIs floating
 - optionally runs combineTool Impacts per POI
 - runs PostFitShapesFromWorkspace once per DM to extract postfit shapes
   for all 3 pT bins simultaneously
"""
import os
import sys
import yaml
from argparse import ArgumentParser


def collect_dms(setup):
    """Return ordered unique DM list pulled from scanRegions (e.g. DM0_pt1 -> DM0)."""
    dms = []
    for r in setup["observables"]["m_vis"]["scanRegions"]:
        d = r.split('_')[0]
        if d not in dms:
            dms.append(d)
    return dms


def load_param_file(path):
    """Return (params, errors) where errors[poi] = {'low':..,'high':..}."""
    params, errors = {}, {}
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, value = line.split(':', 1)
            key = key.strip()
            try:
                value = float(value.strip())
            except ValueError:
                continue
            if key.startswith('trackedParam_'):
                key = key[len('trackedParam_'):]
            if key.endswith('_1sigma_low'):
                errors.setdefault(key[:-len('_1sigma_low')], {})['low'] = value
            elif key.endswith('_1sigma_high'):
                errors.setdefault(key[:-len('_1sigma_high')], {})['high'] = value
            else:
                params[key] = value
    return params, errors


def run_combined_fit(setup, setup_mumu, option, args, **kwargs):
    tes_range    = kwargs.get('tes_range', f"{min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])}")
    tid_SF_range = kwargs.get('tid_SF_range', "0.50,1.2")
    extratag     = kwargs.get('extratag', "_DeepTau")
    save_opts    = kwargs.get('save_opts', " --saveShapes")
    era          = kwargs.get('era', "")
    jet_wp       = kwargs.get('jet_wp', args.jet_wp)
    ele_wp       = kwargs.get('ele_wp', args.ele_wp)
    config_mumu  = kwargs.get('config_mumu', "")

    fit_outdir = os.path.join(args.indir, str(era))
    postfit_outdir = fit_outdir.replace("output", "postfit")
    os.makedirs(fit_outdir, exist_ok=True)
    os.makedirs(postfit_outdir, exist_ok=True)
    print(f"[corrTES-postfit] fit_outdir:     {fit_outdir}")
    print(f"[corrTES-postfit] postfit_outdir: {postfit_outdir}")

    if option != '3':
        print(f"[corrTES-postfit] option={option} not supported (only '3'); aborting")
        return

    dms = collect_dms(setup)
    print(f"[corrTES-postfit] DMs to process: {dms}")

    # Build CSV branches we want to keep as workspace POIs vs nuisances later
    for dm in dms:
        pt_regions = [r for r in setup["observables"]["m_vis"]["scanRegions"]
                      if r.split('_')[0] == dm]
        if not pt_regions:
            continue
        print(f"\n[corrTES-postfit] === DM={dm} | pT regions={pt_regions} ===")

        tes_poi  = f"tes_{dm}"
        tid_pois = [f"tid_SF_{r}" for r in pt_regions]
        all_pois = [tes_poi] + tid_pois
        all_pois_csv = ",".join(all_pois)

        # Per-DM combined workspace (already built during fit step)
        ws_name  = f"combinecards_{dm}{setup['tag']}"
        workspace_file = os.path.join(fit_outdir, f"{ws_name}.root")
        if not os.path.isfile(workspace_file):
            # Fallback: rebuild the workspace if the fit step didn't preserve it
            print(f"[corrTES-postfit] WARNING: {workspace_file} missing — re-running text2workspace")
            ws_txt = os.path.join(fit_outdir, f"{ws_name}.txt")
            if not os.path.isfile(ws_txt):
                print(f"[corrTES-postfit] ERROR: no datacard {ws_txt}; skipping {dm}")
                continue
            os.system(f"text2workspace.py {ws_txt} -o {workspace_file}")

        # Load param file written by the fit step
        param_file = os.path.join(fit_outdir,
                                  f"FitparameterValues_{setup['tag']}_DeepTau_{era}-13TeV_{dm}.txt")
        if not os.path.isfile(param_file):
            print(f"[corrTES-postfit] ERROR: param file {param_file} missing; skipping {dm}")
            continue
        params, errors = load_param_file(param_file)
        print(f"[corrTES-postfit] loaded {len(params)} params, "
              f"{sum(1 for e in errors.values() if 'low' in e and 'high' in e)} POI 1σ ranges")

        # Strip combine internal diagnostic branches; not real workspace parameters.
        bad_keys = {"iChannel", "nll", "nll0"}
        param_opts = ",".join(f"{k}={v}" for k, v in params.items() if k not in bad_keys)

        # Per-POI ranges: pad the ±1σ window so robustHesse can scan PAST ±1σ to find the
        # ΔNLL crossing. Boxing a POI to exactly its ±1σ makes robustHesse hit the wall
        # -> "Closed range without finding crossing". Clamp to the wide default so a POI
        # can never leave the scan window.
        range_parts = []
        for poi in all_pois:
            e = errors.get(poi, {})
            dflt = tes_range if poi.startswith('tes_') else tid_SF_range
            dlo, dhi = (float(x) for x in dflt.split(','))
            if 'low' in e and 'high' in e and poi in params:
                c    = float(params[poi])                       # best-fit centre
                half = max(e['high'] - c, c - e['low'], 1e-4)   # 1σ half-width
                lo   = max(c - 5*half, dlo)                      # ≥5σ headroom, clamped
                hi   = min(c + 5*half, dhi)                      #   to the physical range
                range_parts.append(f"{poi}={lo},{hi}")
            else:
                range_parts.append(f"{poi}={dflt}")
        range_opts = ":".join(range_parts)

        BINLABELoutput = f"mt_m_vis-{dm}{setup['tag']}{extratag}-{era}-13TeV"
        POI_OPTS_F = f"--saveNLL --setParameters r=1,{param_opts} --freezeParameters r"
        FitDiagnostics_opts = (
            f" -m 90 -d {workspace_file} {POI_OPTS_F} "
            f"--setParameterRanges {range_opts} "
            f"-n .{BINLABELoutput} "
            f"--robustFit=1 --setRobustFitAlgo=Minuit2 --setRobustFitStrategy=1 "
            f"--setRobustFitTolerance=0.001 --cminDefaultMinimizerStrategy=0 "
            f"--X-rtd MINIMIZER_analytic --robustHesse=1 "
            f"--redefineSignalPOIs {all_pois_csv} "
            f"--cminFallbackAlgo Minuit2,Migrad,0:0.0001 --cminPreScan "
            f"{save_opts} --trackParameters {all_pois_csv}"
        )
        print(f"[corrTES-postfit] combine -M FitDiagnostics {FitDiagnostics_opts}")
        os.system(f"combine -M FitDiagnostics {FitDiagnostics_opts}")

        # Extract postfit POI values from fit_s
        try:
            import ROOT
            fdf = ROOT.TFile.Open(f"fitDiagnostics.{BINLABELoutput}.root")
            fr  = fdf.Get("fit_s") if fdf else None
            if fr:
                outdir = f"FitDiagnosticsValues/VSjet{jet_wp}_VSele{ele_wp}/"
                os.makedirs(outdir, exist_ok=True)
                with open(f"{outdir}/{dm}_fitdiagnostics_TES_TauID_values.txt", "w") as out:
                    for poi in all_pois:
                        v = fr.floatParsFinal().find(poi)
                        if v:
                            out.write(f"{poi} {v.getVal()} {v.getError()}\n")
                print(f"[corrTES-postfit] wrote {outdir}/{dm}_fitdiagnostics_TES_TauID_values.txt")
            if fdf: fdf.Close()
        except Exception as e:
            print(f"[corrTES-postfit] ERROR reading fitDiagnostics.{BINLABELoutput}.root: {e}")

        # Impacts (optional, slow)
        if getattr(args, 'impacts', False):
            os.system(f"mkdir -p impacts/VSjet{jet_wp}_VSele{ele_wp}/")
            common = (f"-d {workspace_file} -m 90 --redefineSignalPOIs {all_pois_csv} "
                      f"--setParameterRange {range_opts} --setParameters r=1,{param_opts} "
                      f"--freezeParameters r -v 0")
            os.system(f"combineTool.py -M Impacts {common} --doInitialFit --robustFit 1 "
                      f"--cminFallbackAlgo Minuit2,0:1")
            os.system(f"combineTool.py -M Impacts {common} --doFits --robustFit 1 "
                      f"--parallel {args.impacts_parallel}")
            os.system(f"combineTool.py -M Impacts {common} -o impacts_{dm}.json")
            for poi in all_pois:
                os.system(f"plotImpacts.py -i impacts_{dm}.json "
                          f"-o impacts/VSjet{jet_wp}_VSele{ele_wp}/impacts_{dm}_{poi} --POI {poi}")

        # PostFitShapesFromWorkspace once per DM (covers all 3 pT-bin channels)
        outf_postfit = os.path.join(postfit_outdir,
                                    f"PostFitShape_{era}_{setup['tag']}_{dm}.root")
        outf_fit = f"fitDiagnostics.{BINLABELoutput}.root"
        print(f"[corrTES-postfit] PostFitShapesFromWorkspace --output {outf_postfit} "
              f"--workspace {workspace_file} -f {outf_fit}:fit_s --postfit")
        os.system(f"PostFitShapesFromWorkspace --output {outf_postfit} "
                  f"--workspace {workspace_file} -f {outf_fit}:fit_s --postfit")
        # Park the fitDiagnostics file in postfit dir for tidiness
        os.system(f"mv {outf_fit} {postfit_outdir}/ 2>/dev/null")
        print(f"[corrTES-postfit] PostFit shape: {outf_postfit}")


def main(args):
    era = args.era
    print(f"Using config: {args.config}")
    with open(args.config, 'r') as f:
        setup = yaml.safe_load(f)
    setup_mumu = 0
    if args.config_mumu != 'None':
        with open(args.config_mumu, 'r') as f:
            setup_mumu = yaml.safe_load(f)

    run_combined_fit(setup, setup_mumu, args.option, args,
                     era=era, config=args.config, config_mumu=args.config_mumu,
                     jet_wp=args.jet_wp, ele_wp=args.ele_wp)


if __name__ == '__main__':
    parser = ArgumentParser(prog="makeTESfit_corrTES_postfit",
                            description="postfit step for the correlated-TES fit")
    parser.add_argument('-y', '--era', dest='era',
                        choices=['2016','2017','2018','UL2016_preVFP','UL2016_postVFP',
                                 'UL2017','UL2018','UL2018_v10','2022_postEE','2022_preEE',
                                 '2024','2025','2026','2526'],
                        default='2025')
    parser.add_argument('-c', '--config', dest='config', type=str,
                        default='../Configs/Fitter/tes_id/config_coarse_TT.yml')
    parser.add_argument('-o', '--option', dest='option', choices=['3'], default='3',
                        help="only '3' (per-DM joint fit) supported")
    parser.add_argument('-cmm', '--config_mumu', dest='config_mumu', type=str, default='None')
    parser.add_argument('--indir', dest='indir', type=str, required=True,
                        help="output_pt_less_region_corrTES/againstjet_X/againstelectron_Y/")
    parser.add_argument('--mumu_input_file', dest='mumu_input_file', type=str, required=False)
    parser.add_argument('--jet_wp', dest='jet_wp', type=str, required=True)
    parser.add_argument('--ele_wp', dest='ele_wp', type=str, required=True)
    parser.add_argument('--impacts', dest='impacts', action='store_true', default=False,
                        help="also run combineTool Impacts per DM (slow)")
    parser.add_argument('--impacts-parallel', dest='impacts_parallel', type=int, default=8)
    args = parser.parse_args()
    main(args)
    print(">>>\n>>> corrTES postfit done\n")
