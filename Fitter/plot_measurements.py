#!/usr/bin/env python
# Script to plot correlations and measurements from 2D measurement files
# Creates 3 plots: correlations, TES values, and TauID values

import ROOT
ROOT.gROOT.SetBatch(True)  # Run in batch mode (no GUI)
import os
import glob
import argparse
import re
from ROOT import TCanvas, TGraph, TGraphAsymmErrors, TLatex, TLegend, TLine, kBlue, kRed, kGreen, kMagenta, kBlack, kOrange, kGray

TREE_TAG = ""  # tagger suffix for the output/postfit trees (e.g. "_pnet"); set from --tagger, "" = DeepTau

import TauFW.Utilities.Drawing.CMSStyle as CMSStyle

LABEL = {}  # --lumi/--cme of the command line (CL §27); empty: CMSStyle's tables


def lumi_label(year):
    """Lumi + CoM label for the measurement plots: --lumi/--cme if given, else CMSStyle's tables
    (e.g. year='2526' -> '135 fb^{-1} (13.6 TeV)', '2526' lumi=135.48). An era without a luminosity gets only the
    energy (it was a fixed '109 fb^{-1}', CL §27)."""
    lumi = LABEL.get('lumi', CMSStyle.lumi_dict.get(year))
    cme = LABEL.get('cme', CMSStyle.cme_dict.get(year, 13.6))
    return "%s(%.1f TeV)" % ("%.0f fb^{-1} " % (lumi) if lumi else "", cme)

def load_measurements_corr(ele_wp, jet_wp, year):
    """corrTES loader: one param/fitdiag file per DM contains 4 POIs (1 TES + 3 TauID);
       expand each into 3 measurement records (one per pT bin) sharing the TES value."""
    PT_RANGES = {'pt1': '20-40 GeV', 'pt2': '40-60 GeV', 'pt3': '60-200 GeV'}
    measurements = []

    # ---- MultiDimFit: per-DM param files ----
    pattern = f"output_pt_less_region_corrTES{TREE_TAG}/againstjet_{jet_wp}/againstelectron_{ele_wp}/{year}/FitparameterValues__mutau_DeepTau_{year}-13TeV_DM*.txt"
    files = glob.glob(pattern)
    print(f"[corr] Found {len(files)} per-DM MultiDimFit param files")
    for filename in files:
        if os.path.getsize(filename) == 0:
            continue
        dm_match = re.search(r'_(DM\d+)\.txt$', filename)
        if not dm_match:
            continue
        dm = dm_match.group(1)
        # Parse: tes_DM<X> + tid_SF_DM<X>_pt{1,2,3} (+ _1sigma_low/_high)
        tes = {'val': None, 'low': None, 'high': None}
        tid = {p: {'val': None, 'low': None, 'high': None} for p in ('pt1','pt2','pt3')}
        with open(filename) as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                key, sval = line.split(':', 1)
                key = key.strip()
                try:
                    val = float(sval.strip())
                except ValueError:
                    continue
                # TES
                if key == f'tes_{dm}': tes['val'] = val
                elif key == f'tes_{dm}_1sigma_low': tes['low'] = val
                elif key == f'tes_{dm}_1sigma_high': tes['high'] = val
                # TauID per pT
                for pt in ('pt1','pt2','pt3'):
                    if key == f'tid_SF_{dm}_{pt}': tid[pt]['val'] = val
                    elif key == f'tid_SF_{dm}_{pt}_1sigma_low': tid[pt]['low'] = val
                    elif key == f'tid_SF_{dm}_{pt}_1sigma_high': tid[pt]['high'] = val
        tes_err_d = (abs(tes['val'] - tes['low'])  if tes['val'] is not None and tes['low']  is not None else None)
        tes_err_u = (abs(tes['high'] - tes['val']) if tes['val'] is not None and tes['high'] is not None else None)
        for pt in ('pt1','pt2','pt3'):
            t = tid[pt]
            if t['val'] is None or tes['val'] is None:
                continue
            tid_err_d = abs(t['val'] - t['low'])  if t['low']  is not None else None
            tid_err_u = abs(t['high'] - t['val']) if t['high'] is not None else None
            measurements.append({
                'type': 'MultiDimFit', 'region': f"{dm} {PT_RANGES[pt]}",
                'dm': dm, 'pt_bin': pt, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                'tes_val': tes['val'], 'tes_err_down': tes_err_d, 'tes_err_up': tes_err_u,
                'tid_val': t['val'],   'tid_err_down': tid_err_d, 'tid_err_up': tid_err_u,
                'correlation': 0.0,
            })

    # ---- FitDiagnostics: per-DM files in FitDiagnosticsValues/ ----
    fd_pattern = f"./FitDiagnosticsValues/VSjet{jet_wp}_VSele{ele_wp}/DM*_fitdiagnostics_TES_TauID_values.txt"
    fd_files = glob.glob(fd_pattern)
    print(f"[corr] Found {len(fd_files)} per-DM FitDiagnostics files")
    for filename in fd_files:
        if os.path.getsize(filename) == 0:
            continue
        m = re.match(r'(DM\d+)_fitdiagnostics', os.path.basename(filename))
        if not m: continue
        dm = m.group(1)
        tes_val = tes_err = None
        tid_per_pt = {}
        with open(filename) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 3: continue
                k = parts[0]
                try:
                    v = float(parts[1]); e = float(parts[2])
                except ValueError:
                    continue
                if k == f'tes_{dm}':
                    tes_val, tes_err = v, e
                else:
                    pm = re.match(rf'tid_SF_{dm}_(pt\d+)$', k)
                    if pm:
                        tid_per_pt[pm.group(1)] = (v, e)
        for pt, (tv, te) in tid_per_pt.items():
            if tes_val is None: continue
            measurements.append({
                'type': 'FitDiagnostics', 'region': f"{dm} {PT_RANGES.get(pt, pt)}",
                'dm': dm, 'pt_bin': pt, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                'tes_val': tes_val, 'tes_err_down': tes_err, 'tes_err_up': tes_err,
                'tid_val': tv,      'tid_err_down': te,      'tid_err_up': te,
                'correlation': 0.0,
            })
    print(f"[corr] Loaded {len(measurements)} measurements total")
    return measurements


def _fullcorr_sf_eff_and_err(fitdiag_path, dm):
    """Read tid_SF_<dm>, tid_syst_<dm>_pt{1,2,3} (val + err + correlation) from a
       FitDiagnostics file's fit_s RooFitResult and return:
           sf_eff[pt] = tid_SF · (1 + 0.10·θ̂)
           sig_eff[pt]² = (1+0.10·θ̂)²·σ_tid² + (0.10·tid)²·σ_θ² + 2·(...)·ρ·σ_tid·σ_θ
       Returns ({pt: sf_eff}, {pt: sig_eff}, tid_val, tid_err) or (None,None,None,None) if unreadable.
       The covariance term is essential — POI and per-pT nuisances are highly anti-correlated
       (the data measures the *product*, not the individual factors)."""
    import ROOT
    from math import sqrt
    if not os.path.exists(fitdiag_path):
        return None, None, None, None
    f = ROOT.TFile.Open(fitdiag_path)
    fr = f.Get('fit_s') if f else None
    if not fr:
        if f: f.Close()
        return None, None, None, None
    pars = fr.floatParsFinal()
    tid_v = pars.find(f'tid_SF_{dm}')
    if not tid_v:
        f.Close()
        return None, None, None, None
    tid_val = tid_v.getVal()
    tid_err = tid_v.getError()
    sf_eff, sig_eff = {}, {}
    for pt in (1, 2, 3):
        syst_name = f'tid_syst_{dm}_pt{pt}'
        th = pars.find(syst_name)
        if not th:
            continue
        th_val = th.getVal()
        th_err = th.getError()
        rho = fr.correlation(f'tid_SF_{dm}', syst_name)
        a = 1.0 + 0.10 * th_val
        b = 0.10 * tid_val
        var = a*a*tid_err*tid_err + b*b*th_err*th_err + 2.0*a*b*rho*tid_err*th_err
        sf_eff[f'pt{pt}']  = tid_val * a
        sig_eff[f'pt{pt}'] = sqrt(max(0.0, var))
    f.Close()
    return sf_eff, sig_eff, tid_val, tid_err


def load_measurements_fullcorr(ele_wp, jet_wp, year):
    """fullcorr loader: per-DM param file gives tes_<DM>, tid_SF_<DM> (POIs) +
       3 nuisance pulls tid_syst_<DM>_pt{1,2,3}. Each DM expands into 3 measurement
       records (one per pT) with effective TauID = common · (1 + 0.10 · θ̂).
       Uncertainty uses the full POI-nuisance covariance from FitDiagnostics
       (the POI and per-pT nuisances are strongly anti-correlated)."""
    PT_RANGES = {'pt1': '20-40 GeV', 'pt2': '40-60 GeV', 'pt3': '60-200 GeV'}
    measurements = []

    pattern = f"output_pt_less_region_fullcorr{TREE_TAG}/againstjet_{jet_wp}/againstelectron_{ele_wp}/{year}/FitparameterValues__mutau_DeepTau_{year}-13TeV_DM*.txt"
    files = glob.glob(pattern)
    print(f"[fullcorr] Found {len(files)} per-DM MultiDimFit param files")
    for filename in files:
        if os.path.getsize(filename) == 0:
            continue
        dm_match = re.search(r'_(DM\d+)\.txt$', filename)
        if not dm_match:
            continue
        dm = dm_match.group(1)
        tes = {'val': None, 'low': None, 'high': None}
        tid = {'val': None, 'low': None, 'high': None}
        pulls = {}  # ptN -> θ̂
        with open(filename) as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                key, sval = line.split(':', 1)
                key = key.strip()
                try:
                    val = float(sval.strip())
                except ValueError:
                    continue
                if key == f'tes_{dm}': tes['val'] = val
                elif key == f'tes_{dm}_1sigma_low': tes['low'] = val
                elif key == f'tes_{dm}_1sigma_high': tes['high'] = val
                elif key == f'tid_SF_{dm}': tid['val'] = val
                elif key == f'tid_SF_{dm}_1sigma_low': tid['low'] = val
                elif key == f'tid_SF_{dm}_1sigma_high': tid['high'] = val
                else:
                    pm = re.match(rf'tid_syst_{dm}_(pt\d+)$', key)
                    if pm:
                        pulls[pm.group(1)] = val

        if tes['val'] is None or tid['val'] is None:
            continue
        tes_err_d = abs(tes['val'] - tes['low'])  if tes['low']  is not None else None
        tes_err_u = abs(tes['high'] - tes['val']) if tes['high'] is not None else None
        # SF_eff errors with full covariance from FitDiagnostics if available
        fitdiag_path = (f"postfit_pt_less_region_fullcorr{TREE_TAG}/againstjet_{jet_wp}/"
                        f"againstelectron_{ele_wp}/{year}/"
                        f"fitDiagnostics.mt_m_vis-{dm}_mutau_DeepTau-{year}-13TeV.root")
        sf_eff_map, sig_eff_map, _, _ = _fullcorr_sf_eff_and_err(fitdiag_path, dm)
        for pt in ('pt1','pt2','pt3'):
            theta = pulls.get(pt, 0.0)
            sf_eff = tid['val'] * (1.0 + 0.10 * theta)
            if sf_eff_map and pt in sf_eff_map:
                sf_eff   = sf_eff_map[pt]
                eff_err  = sig_eff_map[pt]
                eff_err_d = eff_err_u = eff_err
            else:
                # Fallback: ignore correlation (overestimates the error)
                tid_err_d = abs(tid['val'] - tid['low'])  if tid['low']  is not None else 0.0
                tid_err_u = abs(tid['high'] - tid['val']) if tid['high'] is not None else 0.0
                sys_term = 0.10 * tid['val']
                eff_err_d = (tid_err_d**2 + sys_term**2)**0.5
                eff_err_u = (tid_err_u**2 + sys_term**2)**0.5
            measurements.append({
                'type': 'MultiDimFit', 'region': f"{dm} {PT_RANGES[pt]}",
                'dm': dm, 'pt_bin': pt, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                'tes_val': tes['val'], 'tes_err_down': tes_err_d, 'tes_err_up': tes_err_u,
                'tid_val': sf_eff,     'tid_err_down': eff_err_d, 'tid_err_up': eff_err_u,
                'tid_common': tid['val'], 'tid_pull': theta,
                'correlation': 0.0,
            })

    # FitDiagnostics: read pulls from fit_s and compute effective TauID
    fd_pattern = f"./FitDiagnosticsValues/VSjet{jet_wp}_VSele{ele_wp}/DM*_fitdiagnostics_TES_TauID_values.txt"
    fd_files = glob.glob(fd_pattern)
    print(f"[fullcorr] Found {len(fd_files)} per-DM FitDiagnostics files")
    for filename in fd_files:
        if os.path.getsize(filename) == 0:
            continue
        m = re.match(r'(DM\d+)_fitdiagnostics', os.path.basename(filename))
        if not m: continue
        dm = m.group(1)
        tes_val = tes_err = None
        tid_val = tid_err = None
        with open(filename) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 3: continue
                k = parts[0]
                try:
                    v = float(parts[1]); e = float(parts[2])
                except ValueError:
                    continue
                if k == f'tes_{dm}':       tes_val, tes_err = v, e
                elif k == f'tid_SF_{dm}':  tid_val, tid_err = v, e
        if tes_val is None or tid_val is None:
            continue
        # Per-pT effective SFs from the FitDiagnostics covariance
        fitdiag_path = (f"postfit_pt_less_region_fullcorr{TREE_TAG}/againstjet_{jet_wp}/"
                        f"againstelectron_{ele_wp}/{year}/"
                        f"fitDiagnostics.mt_m_vis-{dm}_mutau_DeepTau-{year}-13TeV.root")
        sf_eff_map, sig_eff_map, _, _ = _fullcorr_sf_eff_and_err(fitdiag_path, dm)
        for pt in ('pt1','pt2','pt3'):
            if sf_eff_map and pt in sf_eff_map:
                sf, err = sf_eff_map[pt], sig_eff_map[pt]
            else:
                sys_term = 0.10 * tid_val
                sf  = tid_val
                err = (tid_err**2 + sys_term**2)**0.5
            measurements.append({
                'type': 'FitDiagnostics', 'region': f"{dm} {PT_RANGES[pt]}",
                'dm': dm, 'pt_bin': pt, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                'tes_val': tes_val, 'tes_err_down': tes_err, 'tes_err_up': tes_err,
                'tid_val': sf,      'tid_err_down': err,    'tid_err_up': err,
                'tid_common': tid_val, 'tid_pull': 0.0,
                'correlation': 0.0,
            })
    print(f"[fullcorr] Loaded {len(measurements)} measurements total")
    return measurements


def load_measurements(ele_wp="tight", jet_wp="medium", year="2024", variant="uncorr"):
    """Load measurements from 2D measurement files and FitDiagnostics"""
    if variant == "corr":
        return load_measurements_corr(ele_wp, jet_wp, year)
    if variant == "fullcorr":
        return load_measurements_fullcorr(ele_wp, jet_wp, year)

    measurements = []

    # --- 1. Load MultiDimFit (2D Scan) files ---
    pattern_multidim = f"output_pt_less_region{TREE_TAG}/againstjet_{jet_wp}/againstelectron_{ele_wp}/{year}/FitparameterValues__mutau_DeepTau_{year}-13TeV_*.txt"
    files_multidim = glob.glob(pattern_multidim)
    print(f"Found {len(files_multidim)} MultiDimFit files")
    
    for filename in files_multidim:
        if os.path.getsize(filename) == 0: continue
        try:
            basename = os.path.basename(filename)
            tes_dm_match = re.search(r'(DM\d+)(?:_(pt\d+))?', basename)
            jet_wp_match = re.search(r'againstjet_(\w+)', filename)
            ele_wp_match = re.search(r'againstelectron_(\w+)', filename)
            
            if not (tes_dm_match and jet_wp_match and ele_wp_match): continue
                
            dm = tes_dm_match.group(1)
            pt_bin = tes_dm_match.group(2) if tes_dm_match.group(2) else "inclusive"
            jet_wp = jet_wp_match.group(1)
            ele_wp = ele_wp_match.group(1)
            
            if pt_bin == "inclusive": region_name = f"{dm} inclusive"
            else:
                pt_ranges = {'pt1': '20-40 GeV', 'pt2': '40-60 GeV', 'pt3': '60-200 GeV'}
                pt_label = pt_ranges.get(pt_bin, pt_bin)
                region_name = f"{dm} {pt_label}"
            
            with open(filename, 'r') as f: lines = f.readlines()
            
            tes_val = None; tes_err_up = None; tes_err_down = None
            tid_val = None; tid_err_up = None; tid_err_down = None
            correlation = 0.0
            tes_low = None; tes_high = None; tid_low = None; tid_high = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('#') or line == '': continue
                
                if ':' in line: # New format
                    parts = line.split(':')
                    if len(parts) >= 2:
                        key = parts[0].strip()
                        try:
                            val = float(parts[1].strip())
                            if key.startswith('tes_'):
                                if '1sigma_low' in key: tes_low = val
                                elif '1sigma_high' in key: tes_high = val
                                else: tes_val = val
                            elif key.startswith('tid_SF_'):
                                if '1sigma_low' in key: tid_low = val
                                elif '1sigma_high' in key: tid_high = val
                                else: tid_val = val
                        except ValueError: pass
                else: # Old format
                    parts = line.split()
                    if len(parts) >= 4:
                        param_name = parts[0]
                        try:
                            value = float(parts[1])
                            error_down = float(parts[2])
                            error_up = float(parts[3])
                            if param_name.startswith('tes_'):
                                tes_val = value; tes_err_down = error_down; tes_err_up = error_up
                            elif param_name.startswith('tid_SF_'):
                                tid_val = value; tid_err_down = error_down; tid_err_up = error_up
                        except ValueError: pass

            if tes_val is not None and tes_low is not None and tes_high is not None:
                tes_err_down = abs(tes_val - tes_low)
                tes_err_up = abs(tes_high - tes_val)
            if tid_val is not None and tid_low is not None and tid_high is not None:
                tid_err_down = abs(tid_val - tid_low)
                tid_err_up = abs(tid_high - tid_val)
            
            if all(x is not None for x in [tes_val, tid_val]):
                measurements.append({
                    'type': 'MultiDimFit',
                    'region': region_name,
                    'dm': dm, 'pt_bin': pt_bin, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                    'tes_val': tes_val, 'tes_err_down': tes_err_down, 'tes_err_up': tes_err_up,
                    'tid_val': tid_val, 'tid_err_down': tid_err_down, 'tid_err_up': tid_err_up,
                    'correlation': correlation
                })
        except Exception as e:
            print(f"Error processing MultiDimFit {filename}: {e}")

    # --- 2. Load FitDiagnostics files ---
    pattern_fitdiag = f"./FitDiagnosticsValues/VSjet{jet_wp}_VSele{ele_wp}/*fitdiagnostics_TES_TauID_values.txt" #postfit_pt_less_region/againstjet_*/againstelectron_*/2024/
    files_fitdiag = glob.glob(pattern_fitdiag)
    print(f"Found {len(files_fitdiag)} FitDiagnostics files")

    for filename in files_fitdiag:
        if os.path.getsize(filename) == 0: continue
        try:
            basename = os.path.basename(filename)
            
            # Relaxed regex: Only require DM, optional pt. WPs are optional.
            tes_dm_match = re.search(r'(DM\d+)(?:_(pt\d+))?', basename)
            
            if not tes_dm_match: 
                print(f"Skipping {basename}: Could not extract DM")
                continue

            dm = tes_dm_match.group(1)
            pt_bin = tes_dm_match.group(2) if tes_dm_match.group(2) else "inclusive"
            
            # Try to extract WPs if present in path, otherwise default
            jet_wp_match = re.search(r'againstjet_(\w+)', filename)
            ele_wp_match = re.search(r'againstelectron_(\w+)', filename)
            
            jet_wp = jet_wp_match.group(1) if jet_wp_match else "Unknown"
            ele_wp = ele_wp_match.group(1) if ele_wp_match else "Unknown"

            if pt_bin == "inclusive": region_name = f"{dm} inclusive"
            else:
                pt_ranges = {'pt1': '20-40 GeV', 'pt2': '40-60 GeV', 'pt3': '60-200 GeV'}
                pt_label = pt_ranges.get(pt_bin, pt_bin)
                region_name = f"{dm} {pt_label}"

            with open(filename, 'r') as f: lines = f.readlines()
            
            tes_val = None; tes_err = None
            tid_val = None; tid_err = None

            for line in lines:
                parts = line.strip().split()
                if len(parts) < 3: continue
                key = parts[0]
                try:
                    val = float(parts[1])
                    err = float(parts[2]) # Symmetric error
                    if key.startswith('tes_'):
                        tes_val = val; tes_err = err
                        print(f"  [FitDiag] Found TES: {tes_val} +/- {tes_err}")
                    elif key.startswith('tid_SF_'):
                        tid_val = val; tid_err = err
                        print(f"  [FitDiag] Found TauID: {tid_val} +/- {tid_err}")
                except ValueError: pass
            
            if tes_val is not None and tid_val is not None:
                measurements.append({
                    'type': 'FitDiagnostics',
                    'region': region_name,
                    'dm': dm, 'pt_bin': pt_bin, 'jet_wp': jet_wp, 'ele_wp': ele_wp,
                    'tes_val': tes_val, 'tes_err_down': tes_err, 'tes_err_up': tes_err,
                    'tid_val': tid_val, 'tid_err_down': tid_err, 'tid_err_up': tid_err,
                    'correlation': 0.0
                })
                print(f"  [FitDiag] {region_name}: TES={tes_val:.4f} +/-{tes_err:.4f}, TauID={tid_val:.4f} +/-{tid_err:.4f}")

        except Exception as e:
            print(f"Error processing FitDiagnostics {filename}: {e}")
    
    print(f"\nLoaded {len(measurements)} total measurements")
    return measurements

def create_correlation_plot(measurements, jet_wp, ele_wp, year):
    """Create correlation plot (Only for MultiDimFit)"""
    print("\nCreating correlation plot...")
    
    # Filter only MultiDimFit for correlation plot
    md_measurements = [m for m in measurements if m['type'] == 'MultiDimFit']
    
    c1 = TCanvas("c_corr", "TES-TauID Correlations", 800, 600)
    c1.SetMargin(0.45, 0.05, 0.15, 0.08)
    c1.SetGrid()
    
    n_points = len(md_measurements)
    gr = TGraphAsymmErrors(n_points)
    
    y_labels = []
    for i, meas in enumerate(md_measurements):
        gr.SetPoint(i, meas['correlation'], i)
        gr.SetPointError(i, 0.02, 0.02, 0, 0)
        
        if meas['pt_bin'] == 'inclusive': label = meas['dm']
        else:
            pt_ranges = {'pt1': '20-40 GeV', 'pt2': '40-60 GeV', 'pt3': '60-200 GeV'}
            pt_range = pt_ranges.get(meas['pt_bin'], meas['pt_bin'])
            label = f"{meas['dm']} {pt_range}"
        y_labels.append(label)
    
    gr.SetMarkerStyle(20); gr.SetMarkerSize(1.0); gr.SetMarkerColor(kBlack); gr.SetLineColor(kBlack)
    gr.SetTitle(""); gr.GetXaxis().SetTitle("Correlation Coefficient")
    gr.GetXaxis().SetTitleSize(0.045); gr.GetXaxis().SetLabelSize(0.04)
    gr.GetXaxis().SetRangeUser(-1.0, 1.0); gr.GetYaxis().SetRangeUser(-0.5, len(md_measurements) - 0.5)
    gr.GetYaxis().SetLabelSize(0); gr.GetYaxis().SetTickLength(0)
    
    gr.Draw("AP")
    
    for i, label in enumerate(y_labels):
        text = TLatex()
        text.SetTextSize(0.03); text.SetTextAlign(32)
        text.DrawLatex(-0.95, i, label)
    
    for i, meas in enumerate(md_measurements):
        corr_text = TLatex()
        corr_text.SetTextSize(0.025); corr_text.SetTextAlign(12)
        x_pos = meas['correlation'] + 0.05
        if x_pos > 0.9: x_pos = meas['correlation'] - 0.05; corr_text.SetTextAlign(32)
        corr_text.DrawLatex(x_pos, i, f"{meas['correlation']:.6f}")
    
    line_zero = ROOT.TLine(0, -0.5, 0, len(md_measurements) - 0.5)
    line_zero.SetLineStyle(2); line_zero.SetLineColor(ROOT.kGray+1); line_zero.Draw()
    
    # Add CMS label
    cms_label = TLatex(); cms_label.SetNDC(); cms_label.SetTextFont(61); cms_label.SetTextSize(0.05); cms_label.DrawLatex(0.46, 0.92, "CMS")
    cms_internal = TLatex(); cms_internal.SetNDC(); cms_internal.SetTextFont(52); cms_internal.SetTextSize(0.04); cms_internal.DrawLatex(0.55, 0.92, "Internal")
    lumi_text = TLatex(); lumi_text.SetNDC(); lumi_text.SetTextFont(42); lumi_text.SetTextSize(0.035); lumi_text.DrawLatex(0.68, 0.92, lumi_label(year))
    
    c1.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/correlation_plot.png")
    c1.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/correlation_plot.pdf")
    c1.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/correlation_plot.root")
    return c1

def create_tes_plot(measurements, jet_wp, ele_wp, year):
    """Create TES measurements plot"""
    print("\nCreating TES plot...")
    
    c2 = TCanvas("c_tes", "TES Measurements", 800, 600)
    c2.SetMargin(0.35, 0.05, 0.15, 0.08)
    c2.SetGrid()
    
    # Get unique regions and sort them
    unique_regions = sorted(list(set(m['region'] for m in measurements)), key=lambda x: (x.split()[0], x))
    n_points = len(unique_regions)
    
    gr_multi = TGraphAsymmErrors(n_points)
    gr_fitdiag = TGraphAsymmErrors(n_points)
    
    y_labels = []
    tes_values = []
    tes_errors = []
    
    for i, region in enumerate(unique_regions):
        # Label
        parts = region.split()
        if 'inclusive' in region: label = parts[0]
        else: label = region
        y_labels.append(label)
        
        # MultiDimFit
        meas_multi = next((m for m in measurements if m['region'] == region and m['type'] == 'MultiDimFit'), None)
        if meas_multi:
            gr_multi.SetPoint(i, meas_multi['tes_val'], i - 0.15) # Offset down
            gr_multi.SetPointError(i, meas_multi['tes_err_down'], meas_multi['tes_err_up'], 0, 0)
            tes_values.append(meas_multi['tes_val'])
            tes_errors.append(max(meas_multi['tes_err_up'], meas_multi['tes_err_down']))
        else:
            gr_multi.SetPoint(i, -999, i - 0.15) # Hidden
            
        # FitDiagnostics
        meas_fit = next((m for m in measurements if m['region'] == region and m['type'] == 'FitDiagnostics'), None)
        if meas_fit:
            gr_fitdiag.SetPoint(i, meas_fit['tes_val'], i + 0.15) # Offset up
            gr_fitdiag.SetPointError(i, meas_fit['tes_err_down'], meas_fit['tes_err_up'], 0, 0)
            tes_values.append(meas_fit['tes_val'])
            tes_errors.append(max(meas_fit['tes_err_up'], meas_fit['tes_err_down']))
        else:
            gr_fitdiag.SetPoint(i, -999, i + 0.15) # Hidden

    # Styling
    gr_multi.SetMarkerStyle(20); gr_multi.SetMarkerSize(1.0); gr_multi.SetMarkerColor(kBlack); gr_multi.SetLineColor(kBlack)
    gr_fitdiag.SetMarkerStyle(21); gr_fitdiag.SetMarkerSize(1.0); gr_fitdiag.SetMarkerColor(kRed); gr_fitdiag.SetLineColor(kRed)
    
    gr_multi.SetTitle(""); gr_multi.GetXaxis().SetTitle("TES Scale Factor")
    gr_multi.GetXaxis().SetTitleSize(0.045); gr_multi.GetXaxis().SetLabelSize(0.04)
    
    # Range
    if tes_values:
        x_min = min(v - e for v, e in zip(tes_values, tes_errors)) * 0.98
        x_max = max(v + e for v, e in zip(tes_values, tes_errors)) * 1.02
        gr_multi.GetXaxis().SetRangeUser(x_min, x_max)
    
    gr_multi.GetYaxis().SetRangeUser(-0.5, n_points - 0.5 + 0.25 * n_points)
    gr_multi.GetYaxis().SetLabelSize(0); gr_multi.GetYaxis().SetTickLength(0)

    gr_multi.Draw("AP")
    gr_fitdiag.Draw("P SAME")

    # Labels
    for i, label in enumerate(y_labels):
        text = TLatex()
        text.SetTextSize(0.035); text.SetTextAlign(32)
        text.DrawLatex(gr_multi.GetXaxis().GetXmin() + 0.05*(gr_multi.GetXaxis().GetXmax()-gr_multi.GetXaxis().GetXmin()), i, label)

    # Legend
    leg = TLegend(0.65, 0.75, 0.9, 0.88)
    leg.SetBorderSize(0)
    leg.AddEntry(gr_multi, "2D Scan", "lp")
    leg.AddEntry(gr_fitdiag, "FitDiagnostics", "lp")
    leg.Draw()
    
    line_unity = ROOT.TLine(1.0, -0.5, 1.0, n_points - 0.5 + 0.25 * n_points)
    line_unity.SetLineStyle(2); line_unity.SetLineColor(ROOT.kGray+1); line_unity.Draw()

    # Add CMS label
    cms_label = TLatex(); cms_label.SetNDC(); cms_label.SetTextFont(61); cms_label.SetTextSize(0.05); cms_label.DrawLatex(0.26, 0.92, "CMS")
    cms_internal = TLatex(); cms_internal.SetNDC(); cms_internal.SetTextFont(52); cms_internal.SetTextSize(0.04); cms_internal.DrawLatex(0.35, 0.92, "Internal")
    lumi_text = TLatex(); lumi_text.SetNDC(); lumi_text.SetTextFont(42); lumi_text.SetTextSize(0.035); lumi_text.DrawLatex(0.65, 0.92, lumi_label(year))

    c2.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/tes_measurements.png")
    c2.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/tes_measurements.pdf")
    c2.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/tes_measurements.root")
    return c2

def create_tauID_plot(measurements, jet_wp, ele_wp, year):
    """Create TauID measurements plot"""
    print("\nCreating TauID plot...")
    
    c3 = TCanvas("c_tid", "TauID Measurements", 800, 600)
    c3.SetMargin(0.35, 0.05, 0.15, 0.08)
    c3.SetGrid()
    
    unique_regions = sorted(list(set(m['region'] for m in measurements)), key=lambda x: (x.split()[0], x))
    n_points = len(unique_regions)
    
    gr_multi = TGraphAsymmErrors(n_points)
    gr_fitdiag = TGraphAsymmErrors(n_points)
    
    y_labels = []
    tid_values = []
    tid_errors = []
    
    for i, region in enumerate(unique_regions):
        parts = region.split()
        if 'inclusive' in region: label = parts[0]
        else: label = region
        y_labels.append(label)
        
        meas_multi = next((m for m in measurements if m['region'] == region and m['type'] == 'MultiDimFit'), None)
        if meas_multi and meas_multi.get('tid_val') is not None:
            edn = meas_multi.get('tid_err_down') or 0.0  # None (Hesse no-crossing) -> 0
            eup = meas_multi.get('tid_err_up')   or 0.0
            gr_multi.SetPoint(i, meas_multi['tid_val'], i - 0.15)
            gr_multi.SetPointError(i, edn, eup, 0, 0)
            tid_values.append(meas_multi['tid_val'])
            tid_errors.append(max(eup, edn))
        else:
            gr_multi.SetPoint(i, -999, i - 0.15)

        meas_fit = next((m for m in measurements if m['region'] == region and m['type'] == 'FitDiagnostics'), None)
        if meas_fit and meas_fit.get('tid_val') is not None:
            edn = meas_fit.get('tid_err_down') or 0.0
            eup = meas_fit.get('tid_err_up')   or 0.0
            gr_fitdiag.SetPoint(i, meas_fit['tid_val'], i + 0.15)
            gr_fitdiag.SetPointError(i, edn, eup, 0, 0)
            tid_values.append(meas_fit['tid_val'])
            tid_errors.append(max(eup, edn))
        else:
            gr_fitdiag.SetPoint(i, -999, i + 0.15)
    
    gr_multi.SetMarkerStyle(20); gr_multi.SetMarkerSize(1.0); gr_multi.SetMarkerColor(kBlack); gr_multi.SetLineColor(kBlack)
    gr_fitdiag.SetMarkerStyle(21); gr_fitdiag.SetMarkerSize(1.0); gr_fitdiag.SetMarkerColor(kRed); gr_fitdiag.SetLineColor(kRed)
    
    gr_multi.SetTitle(""); gr_multi.GetXaxis().SetTitle("TauID Scale Factor")
    gr_multi.GetXaxis().SetTitleSize(0.045); gr_multi.GetXaxis().SetLabelSize(0.04)
    
    if tid_values:
        x_min = min(v - e for v, e in zip(tid_values, tid_errors)) * 0.95
        x_max = max(v + e for v, e in zip(tid_values, tid_errors)) * 1.05
        gr_multi.GetXaxis().SetRangeUser(x_min, x_max)
    
    gr_multi.GetYaxis().SetRangeUser(-0.5, n_points - 0.5 + 0.25 * n_points)
    gr_multi.GetYaxis().SetLabelSize(0); gr_multi.GetYaxis().SetTickLength(0)

    gr_multi.Draw("AP")
    gr_fitdiag.Draw("P SAME")

    for i, label in enumerate(y_labels):
        text = TLatex()
        text.SetTextSize(0.035); text.SetTextAlign(32)
        text.DrawLatex(gr_multi.GetXaxis().GetXmin() + 0.08*(gr_multi.GetXaxis().GetXmax()-gr_multi.GetXaxis().GetXmin()), i, label)
    
    leg = TLegend(0.65, 0.75, 0.9, 0.88)
    leg.SetBorderSize(0)
    leg.AddEntry(gr_multi, "2D Scan", "lp")
    leg.AddEntry(gr_fitdiag, "FitDiagnostics", "lp")
    leg.Draw()
    
    line_unity = ROOT.TLine(1.0, -0.5, 1.0, n_points - 0.5 + 0.25 * n_points)
    line_unity.SetLineStyle(2); line_unity.SetLineColor(ROOT.kGray+1); line_unity.Draw()

    # Add CMS label
    cms_label = TLatex(); cms_label.SetNDC(); cms_label.SetTextFont(61); cms_label.SetTextSize(0.05); cms_label.DrawLatex(0.26, 0.92, "CMS")
    cms_internal = TLatex(); cms_internal.SetNDC(); cms_internal.SetTextFont(52); cms_internal.SetTextSize(0.04); cms_internal.DrawLatex(0.35, 0.92, "Internal")
    lumi_text = TLatex(); lumi_text.SetNDC(); lumi_text.SetTextFont(42); lumi_text.SetTextSize(0.035); lumi_text.DrawLatex(0.65, 0.92, lumi_label(year))

    c3.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/tauID_measurements.png")
    c3.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/tauID_measurements.pdf")
    c3.SaveAs(f"Measurements/VSjet{jet_wp}_VSele{ele_wp}/tauID_measurements.root")
    return c3

def main():
    """Main function"""
    print("Loading measurements from 2D measurement files...")
    parser = argparse.ArgumentParser(description="Combine prefit, postfit, and optional scan plots.")
    parser.add_argument('--jet_wp', type=str, default="Medium", help="Jet working point (not used in this script)")
    parser.add_argument('--ele_wp', type=str, default="Tight", help="Electron working point (not used in this script)")
    parser.add_argument('--year', type=str, default="2024", help="Year for plotting (not used in this script)")
    parser.add_argument('--variant', choices=['uncorr','corr','fullcorr'], default='uncorr',
                        help="uncorr: per-region; corr: per-DM TES; fullcorr: per-DM TES+TauID with per-pT pulls")
    parser.add_argument('--tagger', type=str, default='',
                        help="tree tagger suffix (e.g. pnet, upart); '' = DeepTau default")
    parser.add_argument('--lumi', dest='lumi', type=float, default=None, help="integrated luminosity [/fb] of the CMS label (default: CMSStyle.lumi_dict of the era; the TauFW Framework gives the one of the shapes' normalisation, CL §27)")
    parser.add_argument('--cme', dest='cme', type=float, default=None, help="centre-of-mass energy [TeV] of the CMS label (default: CMSStyle.cme_dict of the era)")

    args = parser.parse_args()
    LABEL.update({key: value for key, value in (('lumi', args.lumi), ('cme', args.cme)) if value is not None})
    global TREE_TAG
    if args.tagger:
        TREE_TAG = "_" + args.tagger
    # Load measurements
    os.makedirs(f"Measurements/VSjet{args.jet_wp}_VSele{args.ele_wp}/", exist_ok=True)
    measurements = load_measurements(ele_wp=args.ele_wp, jet_wp=args.jet_wp,
                                     year=args.year, variant=args.variant)
    
    if not measurements:
        print("No measurements found!")
        return
    
    # Sort measurements by decay mode for consistent plotting
    measurements.sort(key=lambda x: (x['dm'], x['jet_wp'], x['ele_wp']))
    
    print(f"\nCreating plots for {len(measurements)} measurements...")
    
    # Create the three plots
    c1 = create_correlation_plot(measurements, jet_wp=args.jet_wp, ele_wp=args.ele_wp, year=args.year)
    c2 = create_tes_plot(measurements, jet_wp=args.jet_wp, ele_wp=args.ele_wp, year=args.year)
    c3 = create_tauID_plot(measurements, jet_wp=args.jet_wp, ele_wp=args.ele_wp, year=args.year)
    
    print("\nAll plots created successfully!")
    print("Files saved:")
    print("  - correlation_plot.png/pdf")
    print("  - tes_measurements.png/pdf") 
    print("  - tauID_measurements.png/pdf")
    
    print("\\nPlots completed successfully!")

if __name__ == "__main__":
    main()