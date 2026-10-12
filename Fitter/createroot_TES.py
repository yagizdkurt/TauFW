#! /usr/bin/env python
# Author: P.Mastrapasqua, O. Poncet (May 2023)
# Usage: python3 createroot_TES.py -c TauES_ID/config/config_coarse_TT.yml -j Medium -e VVLoose -f root -y 2024
'''This script makes pt-dependants TES json/root files from config file.'''
import ROOT
import os, sys, yaml, glob
from array import array
from argparse import ArgumentParser
from collections import OrderedDict
from ROOT import gROOT, gPad, gStyle, TFile, TCanvas, TLegend, TLatex, TF1, TMultiGraph, TGraph, TGraph2D, TPolyMarker3D, TGraphAsymmErrors, TLine, TH2F, TPaveText, kBlack, kBlue, kRed, kGreen, kYellow, kOrange, kMagenta, kTeal, kAzure, TMath, TH1F, kWhite
# from fit_tools import FitSF
#from TauFW.Plotter.sample.utils import CMSStyle
try:
    import correctionlib.schemav2 as cs
except ImportError:
    cs = None
# import rich

TREE_TAG = ""  # tagger suffix for the output tree (e.g. "_pnet"); set from --tagger, "" = DeepTau


def load_pt_values(setup,**kwargs):
    pt_avg_list = []
    pt_error_list = []
    bins_order = setup["plottingOrder"]
    for region in setup['regions']:
        # print("region = %s" %(ptregion))
        title = setup['regions'][region]["title"]
        if 'pt' not in title: continue
        str_pt_lo = title.split("pt:")[-1].split('-')[0].strip()
        str_pt_hi = title.split("pt:")[-1].split('-')[1].strip()
        pt_hi = float(str_pt_hi)
        pt_lo = float(str_pt_lo)
        pt_avg = (pt_hi + pt_lo) / 2.0
        pt_error = pt_avg - pt_lo
        pt_avg_list.append(pt_avg)
        pt_error_list.append(pt_error)
        # print("pt average = %f and pt error = %s" %(pt_avg, pt_error))
    #pt_avg_list = sorted(list(set(pt_avg_list)), key=lambda k: k[0])
    #print(pt_avg_list)
    return pt_avg_list, pt_error_list

def load_edges(setup,**kwargs):
    edg  = []
    bins_order = setup["plottingOrder"]
    for region in setup['regions']:
        # print("region = %s" %(ptregion))
        title = setup["regions"][region]["title"]
        if 'pt' not in title: continue
        str_pt_lo = title.split("pt:")[-1].split('-')[0].strip()
        str_pt_hi = title.split("pt:")[-1].split('-')[1].strip()
        #print("ibin")
        #print(str_pt_lo)
        #print(str_pt_hi)
        pt_hi = float(str_pt_hi)
        pt_lo = float(str_pt_lo)
        edg.append(pt_lo)
    print(edg)
    edg.append(pt_hi)
    #edg = sorted(list(set(edg)))
    print(edg)
    return edg


def _load_fullcorr_tid(input_root, year, jet_wp, ele_wp):
    """For fullcorr TauID: per-DM SF_eff(DM, pt) = common · (1 + 0.10·θ̂_pt).
       Uncertainty uses the full POI-nuisance covariance from FitDiagnostics
       (the two are strongly anti-correlated; the data measures the *product*).
       Returns (regions, values, errhi, errlo) with regions = '<DM>_pt<N>'."""
    import re as _re
    from math import sqrt
    try:
        import ROOT as _ROOT
    except ImportError:
        _ROOT = None

    pattern = f"{input_root}/againstjet_{jet_wp}/againstelectron_{ele_wp}/{year}/FitparameterValues_*_DeepTau_{year}-13TeV_DM*.txt"
    files = glob.glob(pattern)
    print(f"[fullcorr-tid] Found {len(files)} param files")
    # Postfit FitDiag tree (covariance source)
    fitdiag_dir = input_root.replace('output_pt_less_region', 'postfit_pt_less_region')
    fitdiag_dir = os.path.join(fitdiag_dir, f"againstjet_{jet_wp}",
                               f"againstelectron_{ele_wp}", year)

    regions, vals, errhi, errlo = [], [], [], []
    for fn in files:
        if os.path.getsize(fn) == 0:
            continue
        m = _re.search(r'_(DM\d+)\.txt$', fn)
        if not m:
            continue
        dm = m.group(1)
        common = {'val': None, 'low': None, 'high': None}
        pulls = {}
        with open(fn) as f:
            for line in f:
                line = line.strip()
                if not line or ':' not in line:
                    continue
                k, v = line.split(':', 1)
                k = k.strip()
                try:
                    v = float(v.strip())
                except ValueError:
                    continue
                if k == f'tid_SF_{dm}':                common['val']  = v
                elif k == f'tid_SF_{dm}_1sigma_low':   common['low']  = v
                elif k == f'tid_SF_{dm}_1sigma_high':  common['high'] = v
                else:
                    pm = _re.match(rf'tid_syst_{dm}_(pt\d+)$', k)
                    if pm:
                        pulls[pm.group(1)] = v
        if common['val'] is None:
            continue

        # Try FitDiagnostics for full covariance error propagation
        sf_eff_map, sig_eff_map = {}, {}
        fitdiag_path = os.path.join(fitdiag_dir,
            f"fitDiagnostics.mt_m_vis-{dm}_mutau_DeepTau-{year}-13TeV.root")
        if _ROOT is not None and os.path.exists(fitdiag_path):
            f_fd = _ROOT.TFile.Open(fitdiag_path)
            fr = f_fd.Get('fit_s') if f_fd else None
            if fr:
                pars = fr.floatParsFinal()
                tid_v = pars.find(f'tid_SF_{dm}')
                if tid_v:
                    tid_val = tid_v.getVal()
                    tid_err = tid_v.getError()
                    for pt in (1,2,3):
                        th = pars.find(f'tid_syst_{dm}_pt{pt}')
                        if not th: continue
                        th_val = th.getVal(); th_err = th.getError()
                        rho = fr.correlation(f'tid_SF_{dm}', f'tid_syst_{dm}_pt{pt}')
                        a = 1.0 + 0.10*th_val
                        b = 0.10*tid_val
                        var = a*a*tid_err*tid_err + b*b*th_err*th_err + 2.0*a*b*rho*tid_err*th_err
                        sf_eff_map[f'pt{pt}']  = tid_val * a
                        sig_eff_map[f'pt{pt}'] = sqrt(max(0.0, var))
            if f_fd: f_fd.Close()

        # Fallback uncertainty (ignores correlation — used only if FitDiag missing)
        tid_err_d_fb = abs(common['val'] - common['low'])  if common['low']  is not None else 0.0
        tid_err_u_fb = abs(common['high'] - common['val']) if common['high'] is not None else 0.0
        sys_term_fb = 0.10 * common['val']

        for pt in ('pt1','pt2','pt3'):
            theta = pulls.get(pt, 0.0)
            if pt in sf_eff_map:
                sf = sf_eff_map[pt]
                err = sig_eff_map[pt]
                eff_err_d = eff_err_u = err
                source = "FitDiag-cov"
            else:
                sf = common['val'] * (1.0 + 0.10 * theta)
                eff_err_d = (tid_err_d_fb**2 + sys_term_fb**2)**0.5
                eff_err_u = (tid_err_u_fb**2 + sys_term_fb**2)**0.5
                source = "fallback"
            regions.append(f"{dm}_{pt}")
            vals.append(sf)
            errhi.append(eff_err_u)
            errlo.append(eff_err_d)
            print(f"[fullcorr-tid] {dm}_{pt}: SF_eff={sf:.4f} +/-{eff_err_u:.4f} ({source}, θ̂={theta:+.2f}σ)")
    return regions, vals, errhi, errlo


# Load the SF measurements from the new 2D measurement files
def load_sf_measurements(setup, year, **kwargs):
    tag     = kwargs.get('tag',         ""              )
    jet_wp  = kwargs.get('jet_wp',      "Tight"         )
    ele_wp  = kwargs.get('ele_wp',      "Tight"         )
    sf      = kwargs.get('sf',          "tes"         )
    variant = kwargs.get('variant',     "uncorr"        )

    region = []
    tes_values = []
    tid_values = []
    tes_errhi = []
    tes_errlo = []
    tid_errhi = []
    tid_errlo = []

    print(f"[DEBUG] Looking for {sf} measurements in year {year} (variant={variant})")

    # Variant-aware input root (+ tagger suffix for PNet/UParT trees)
    if variant == "corr":
        input_root = "output_pt_less_region_corrTES" + TREE_TAG
    elif variant == "fullcorr":
        input_root = "output_pt_less_region_fullcorr" + TREE_TAG
    else:
        input_root = "output_pt_less_region" + TREE_TAG

    # fullcorr + TauID: synthesize per-pT effective SFs from common POI + per-pT pulls
    if variant == "fullcorr" and sf == "tid_SF":
        return _load_fullcorr_tid(input_root, year, jet_wp, ele_wp)

    # Use glob to find all measurement files
    pattern = f"{input_root}/againstjet_{jet_wp}/againstelectron_{ele_wp}/{year}/FitparameterValues_*_DeepTau_{year}-13TeV_*.txt"
    #f"plots_pt_less_region/againstjet_{jet_wp}/againstelectron_{ele_wp}/{year}/measurement_2D_tes_*_tid_SF_*_mt_*_mutau.txt"
    all_files = glob.glob(pattern)
    print(f"[DEBUG] Found {len(all_files)} measurement files")
    
    for inputfilename in all_files:
        print(f"[DEBUG] Processing: {inputfilename}")
        
        try:
            with open(inputfilename, 'r') as file:
                # Store data for the requested SF type found in this file
                # Structure: { region_name: {'val': v, 'low': l, 'high': h} }
                file_data = {}
                
                for line in file:
                    if line.startswith('#') or line.strip() == '':
                        continue
                    
                    # Check for new format "key: value"
                    if ':' in line:
                        parts = line.strip().split(':')
                        if len(parts) != 2: continue
                        
                        key = parts[0].strip()
                        try:
                            value = float(parts[1].strip())
                        except ValueError:
                            continue

                        # Check if this key matches the requested SF type (tes or tid_SF)
                        if key.startswith(sf + '_'):
                            # Parse key to extract region and type (val, low, high)
                            # Format examples: 
                            # tes_DM0_pt1
                            # tes_DM0_pt1_1sigma_low
                            # tes_DM0_pt1_1sigma_high
                            
                            remainder = key[len(sf)+1:] # remove "tes_" or "tid_SF_"
                            
                            if remainder.endswith('_1sigma_low'):
                                reg = remainder[:-11] # len('_1sigma_low') = 11
                                kind = 'low'
                            elif remainder.endswith('_1sigma_high'):
                                reg = remainder[:-12] # len('_1sigma_high') = 12
                                kind = 'high'
                            else:
                                reg = remainder
                                kind = 'val'
                            
                            if reg not in file_data:
                                file_data[reg] = {}
                            file_data[reg][kind] = value
                
                # Process the data collected from the file
                for reg, data in file_data.items():
                    if 'val' in data:
                        val = data['val']
                        low = data.get('low', val) # Default to val (0 error) if missing
                        high = data.get('high', val)
                        
                        # Calculate errors
                        # The file has absolute values for 1sigma bounds
                        err_down = abs(val - low)
                        err_up = abs(high - val)
                        
                        region.append(reg)
                        if sf == 'tes':
                            tes_values.append(val)
                            tes_errhi.append(err_up)
                            tes_errlo.append(err_down)
                        else:
                            tid_values.append(val)
                            tid_errhi.append(err_up)
                            tid_errlo.append(err_down)
                            
                        print(f"[DEBUG] Successfully loaded {reg}: {sf}={val}, +{err_up}/-{err_down}")
                    
        except FileNotFoundError:
            print(f"[DEBUG] File not found: {inputfilename}")
            continue
    
    print(f"[DEBUG] Total regions loaded: {len(region)}")
    print(f"[DEBUG] Regions: {region}")
    
    # Return the appropriate values based on the requested SF type
    if sf == 'tes':
        return region, tes_values, tes_errhi, tes_errlo
    else:  # tid_SF
        return region, tid_values, tid_errhi, tid_errlo


def plot_dm_graph(setup, form, ele_wp, jet_wp, **kwargs):
    tag = kwargs.get('tag', "")
    variant = kwargs.get('variant', "uncorr")
    jet_wps = [jet_wp]  # Use only the specified jet working point
    sfs = ['tes', 'tid_SF']
    pt_avg_list, pt_error_list = load_pt_values(setup)
    pt_edges = load_edges(setup)
    
    # Ensure output directory exists
    ensureDirectory("tau_sf")
    
    # Tagger-aware labels (DeepTau by default; PNet/UParT via config 'tagger' block)
    _tagger    = setup.get('tagger') or {}
    id_label   = _tagger.get('id_label', 'DeepTau2018v2p5VSjet')          # e.g. ParticleNetVSjet
    tagger_tag = id_label.replace('VSjet', '').rstrip('_') or 'DeepTau2018v2p5'  # filename component

    # Loop over DMs
    print(">>> DM exclusive ")
    # DM order from config (unique DMs in scanRegions order); fallback to legacy 4-bin DeepTau
    try:
        dm_order = []
        for _r in setup["observables"]["m_vis"]["scanRegions"]:
            _d = _r.split('_')[0]
            if _d not in dm_order:
                dm_order.append(_d)
    except Exception:
        dm_order = []
    if not dm_order:
        dm_order = ["DM0", "DM1", "DM10", "DM11"]

    # Define pt edges for each pt bin (adjust these based on your actual pt ranges)
    pt_bin_edges = { # should be configurable in the yml file, but for now hardcoded based on typical pt binning
        "pt1": [20.0, 40.0],   # Adjust these ranges as needed
        "pt2": [40.0, 60.0],   # Adjust these ranges as needed  
        "pt3": [60.0, 200.0],  # Adjust these ranges as needed
    }

    # Create a dictionary to store sf data
    sf_dict = {}
    
    # Loop over SFs and years
    for sf in sfs:
        sf_dict[sf] = {}
        for year in [args.year]:
            sf_dict[sf][year] = {}
            
            for dm in dm_order:
                print(f">>>>>>>>>>>> {dm}:")
                
                # Loop over jet_wps (only one in this case)
                for current_jet_wp in jet_wps:
                    print(f'jet_wp: {current_jet_wp}')
                    # Load measurements
                    region, tes, tes_errhi, tes_errlo = load_sf_measurements(
                        setup, year, tag=tag, jet_wp=current_jet_wp, ele_wp=ele_wp, sf=sf,
                        variant=variant
                    )
                    
                    # Filter elements with current DM (exact match to avoid DM1 matching DM10, DM11)
                    dm_list = [elem for elem in region if elem == dm or elem.startswith(dm + '_')]
                    print(f"Elements with {dm}: {dm_list}")
                    
                    # Get values for current DM
                    print(">>>>>> INPUT FOR JSON")
                    if dm_list:
                        # Sort dm_list to ensure consistent ordering (pt1, pt2, pt3, then inclusive)
                        def sort_key(item):
                            if '_pt1' in item:
                                return (item.replace('_pt1', ''), 1)
                            elif '_pt2' in item:
                                return (item.replace('_pt2', ''), 2)
                            elif '_pt3' in item:
                                return (item.replace('_pt3', ''), 3)
                            else:
                                return (item, 0)  # Inclusive DM comes first
                        
                        sorted_dm_list = sorted(dm_list, key=sort_key)
                        
                        # Get sorted values
                        dm_tes = [tes[region.index(elem)] for elem in sorted_dm_list]
                        dm_tes_errhi = [tes_errhi[region.index(elem)] for elem in sorted_dm_list]
                        dm_tes_errlo = [tes_errlo[region.index(elem)] for elem in sorted_dm_list]
                        
                        print(f"tes for : {dm_tes}")
                        
                        # Build pt_edges for this DM based on the pt bins found
                        dm_pt_edges = []
                        has_pt_bins = any('_pt' in elem for elem in sorted_dm_list)
                        
                        if has_pt_bins:
                            # We have pt binned measurements
                            for elem in sorted_dm_list:
                                if '_pt1' in elem:
                                    if pt_bin_edges["pt1"][0] not in dm_pt_edges:
                                        dm_pt_edges.append(pt_bin_edges["pt1"][0])
                                elif '_pt2' in elem:
                                    if pt_bin_edges["pt2"][0] not in dm_pt_edges:
                                        dm_pt_edges.append(pt_bin_edges["pt2"][0])
                                elif '_pt3' in elem:
                                    if pt_bin_edges["pt3"][0] not in dm_pt_edges:
                                        dm_pt_edges.append(pt_bin_edges["pt3"][0])
                            
                            # Add the final edge
                            if any('_pt3' in elem for elem in sorted_dm_list):
                                dm_pt_edges.append(pt_bin_edges["pt3"][1])
                            elif any('_pt2' in elem for elem in sorted_dm_list):
                                dm_pt_edges.append(pt_bin_edges["pt2"][1])
                            elif any('_pt1' in elem for elem in sorted_dm_list):
                                dm_pt_edges.append(pt_bin_edges["pt1"][1])
                        else:
                            # Only inclusive measurement, use full pt range
                            dm_pt_edges = [20.0, 200.0]
                        
                        # Sort edges to ensure they're in ascending order
                        dm_pt_edges = sorted(list(set(dm_pt_edges)))
                        print(f"pt_edges for : {dm_pt_edges}")

                        print(f"tes_errhi :  {dm_tes_errhi}")
                        print(f"tes_errlo :  {dm_tes_errlo}")

                        dm_tes_up = [val + err for val, err in zip(dm_tes, dm_tes_errhi)]
                        print(f"tes_up for : {dm_tes_up}")
                        dm_tes_down = [val - err for val, err in zip(dm_tes, dm_tes_errlo)]
                        print(f"tes_down for : {dm_tes_down}")

                        # Store in dictionary with correct key
                        key = f'{dm}_{current_jet_wp}'
                        sf_dict[sf][year][key] = {
                            "edges": dm_pt_edges, 
                            "content": dm_tes, 
                            "up": dm_tes_up, 
                            "down": dm_tes_down
                        }
                    else:
                        # No data for this DM
                        key = f'{dm}_{current_jet_wp}'
                        sf_dict[sf][year][key] = {
                            "edges": [], 
                            "content": [], 
                            "up": [], 
                            "down": []
                        }
    print("SF dictionary")
    print(sf_dict)

    # Create ROOT files
    colors = [kBlack, kBlue, kRed, kMagenta, kYellow, kOrange, kGreen, kTeal, kAzure]
    for sf in sfs:
        if form == 'root':
            # Loop on DMs
            for idx, current_jet_wp in enumerate(jet_wps):
                if sf == 'tes':
                    name = 'TauES'
                else:
                    name = 'TauID'
                    
                sfile = TFile(f"tau_sf/{name}_SF_dm_{tagger_tag}_{args.year}{({'corr': '_corrTES', 'fullcorr': '_fullcorr'}.get(variant, ''))}_VSjet{current_jet_wp}_VSele{ele_wp}.root", 'recreate')

                for year in [args.year]:
                    for dm in dm_order:
                        # Build the function strings
                        funcstr = '(x<=20)*0'
                        funcstr_up = '(x<=20)*0'  
                        funcstr_down = '(x<=20)*0'

                        # Build key
                        key = f'{dm}_{current_jet_wp}'
                        
                        print(f"[DEBUG] Looking for key: {key}")
                        print(f"[DEBUG] Available keys: {list(sf_dict[sf][year].keys())}")
                        
                        # Check if we have data
                        if key not in sf_dict[sf][year] or len(sf_dict[sf][year][key]["content"]) == 0:
                            print(f"[DEBUG] No data for {key}, creating default function returning 1.0")
                            funcstr = '1.0'
                            funcstr_up = '1.0'
                            funcstr_down = '1.0'
                        else:
                            print(f"[DEBUG] Found data for {key}: {len(sf_dict[sf][year][key]['content'])} bins")
                            edges = sf_dict[sf][year][key]["edges"]
                            content = sf_dict[sf][year][key]["content"]
                            up_content = sf_dict[sf][year][key]["up"]
                            down_content = sf_dict[sf][year][key]["down"]
                            
                            # Ensure we have the right number of edges (should be len(content) + 1)
                            print(f"[DEBUG] Edges: {edges}, Content: {content}")
                            
                            # Build the piecewise function for each bin
                            for ip in range(len(content)):
                                if ip < len(edges) - 1:  # Make sure we don't go out of bounds
                                    pt_low = edges[ip]
                                    pt_high = edges[ip + 1]
                                    print(f'ip: {ip}, pt_low: {pt_low}, pt_high: {pt_high}')
                                    funcstr += f'+ (x > {pt_low} && x <= {pt_high})*{content[ip]}'
                                    funcstr_up += f'+ (x > {pt_low} && x <= {pt_high})*{up_content[ip]}'
                                    funcstr_down += f'+ (x > {pt_low} && x <= {pt_high})*{down_content[ip]}'
                                else:
                                    # Last bin - extend to high pT
                                    pt_low = edges[ip] if ip < len(edges) else edges[-1]
                                    print(f'ip: {ip} (last bin), pt_low: {pt_low}')
                                    funcstr += f'+ (x > {pt_low})*{content[ip]}'
                                    funcstr_up += f'+ (x > {pt_low})*{up_content[ip]}'
                                    funcstr_down += f'+ (x > {pt_low})*{down_content[ip]}'


                        print(key)
                        print(funcstr, '\t', dm, '\t', year)
                        
                        # Create functions
                        func_SF = TF1(dm + year, funcstr, 0, 200)
                        func_SF.Write()
                        func_SF_up = TF1(dm + year + '_up', funcstr_up, 0, 200)
                        func_SF_up.Write()
                        func_SF_down = TF1(dm + year + '_down', funcstr_down, 0, 200)
                        func_SF_down.Write()
                
                sfile.Write()
                sfile.Close()

    # Create JSON files
    if form == 'json':
        if cs is None:
            print("Warning: correctionlib not available. JSON files will not be created.")
            return
            
        try:
            import json
            
            for sf in sfs:
                for idx, current_jet_wp in enumerate(jet_wps):
                    if sf == 'tes':
                        name = 'TauES'
                    else:
                        name = 'TauID'
                    
                    # Create correction with systematic variation as input parameter
                    dm_systematic_categories = []
                    
                    for dm in dm_order:
                        dm_num = -1 if dm == 'DMrest' else int(dm.replace('DM', ''))  # DM0->0, DM11->11, DMrest->-1
                        key = f'{dm}_{current_jet_wp}'
                        
                        if key in sf_dict[sf][args.year] and len(sf_dict[sf][args.year][key]["content"]) > 0:
                            # Use actual data for all variations
                            edges = sf_dict[sf][args.year][key]["edges"]
                            nom_content = sf_dict[sf][args.year][key]["content"]
                            up_content = sf_dict[sf][args.year][key]["up"]
                            down_content = sf_dict[sf][args.year][key]["down"]
                            
                            # Ensure content length is len(edges) - 1 for correctionlib
                            for content_name, content in [("nom", nom_content), ("up", up_content), ("down", down_content)]:
                                if len(content) != len(edges) - 1:
                                    print(f"Warning: Adjusting content length for {dm} {content_name}: {len(content)} -> {len(edges)-1}")
                                    if len(content) > len(edges) - 1:
                                        content[:] = content[:len(edges)-1]  # Truncate in place
                                    else:
                                        content.extend([1.0] * (len(edges) - 1 - len(content)))  # Pad with 1.0
                        else:
                            # Use default values for all variations
                            edges = [20.0, 200.0]
                            nom_content = up_content = down_content = [1.0]
                        
                        # Create systematic variation categories for this DM
                        dm_systematic_categories.append(cs.CategoryItem(
                            key=dm_num,
                            value=cs.Category(
                                nodetype="category",
                                input="syst",
                                content=[
                                    cs.CategoryItem(key="nom", value=cs.Binning(
                                        nodetype="binning",
                                        input="pT",
                                        edges=edges,
                                        content=nom_content,
                                        flow="clamp"
                                    )),
                                    cs.CategoryItem(key="up", value=cs.Binning(
                                        nodetype="binning",
                                        input="pT",
                                        edges=edges,
                                        content=up_content,
                                        flow="clamp"
                                    )),
                                    cs.CategoryItem(key="down", value=cs.Binning(
                                        nodetype="binning",
                                        input="pT",
                                        edges=edges,
                                        content=down_content,
                                        flow="clamp"
                                    ))
                                ]
                            )
                        ))
                    
                    # Create single correction with systematic variation and working points as inputs
                    corr = cs.Correction(
                        name=f"{name}SF",
                        version=1,
                        description=f"{name} SF, pT binned divided by DM with systematic variations and working point inputs ({id_label})",
                        inputs=[
                            cs.Variable(name="genmatch", type="int", description="Tau genmatch, sf only on real taus (genmatch 5)"),
                            cs.Variable(name="DM", type="int", description="Tau decay mode (e.g. 0,1,2,10,11; -1 = rest for PNet/UParT)"),
                            cs.Variable(name="pT", type="real", description="Tau transverse momentum"),
                            cs.Variable(name="syst", type="string", description="Systematic variation ('nom', 'up', 'down')"),
                            cs.Variable(name="wp_VSmu", type="string", description="DeepTau2018v2p5 working point vs muon ('VLoose', 'Loose', 'Medium', 'Tight', 'VTight', 'VVTight')"),
                            cs.Variable(name="wp_VSe", type="string", description="DeepTau2018v2p5 working point vs electron ('VVLoose', 'VLoose', 'Loose', 'Medium', 'Tight', 'VTight', 'VVTight')"),
                            cs.Variable(name="wp_VSjet", type="string", description=f"{id_label} working point vs jet"),
                        ],
                        output={'name': "sf", 'type': "real", 'description': f"{name} scale factor"},
                        data=cs.Category(
                            nodetype="category",
                            input="wp_VSmu",
                            content=[
                                cs.CategoryItem(key="Tight", value=cs.Category(
                                    nodetype="category", 
                                    input="wp_VSe",
                                    content=[
                                        cs.CategoryItem(key=ele_wp, value=cs.Category(
                                            nodetype="category",
                                            input="wp_VSjet", 
                                            content=[
                                                cs.CategoryItem(key=current_jet_wp, value=cs.Category(
                                                    nodetype="category",
                                                    input="genmatch",
                                                    content=[
                                                        cs.CategoryItem(key=1, value=1.0),
                                                        cs.CategoryItem(key=2, value=1.0),
                                                        cs.CategoryItem(key=3, value=1.0),
                                                        cs.CategoryItem(key=4, value=1.0),
                                                        cs.CategoryItem(key=5, value=cs.Category(
                                                            nodetype="category",
                                                            input="DM",
                                                            content=dm_systematic_categories
                                                        )),
                                                        cs.CategoryItem(key=6, value=1.0),
                                                        cs.CategoryItem(key=0, value=1.0)
                                                    ]
                                                ))
                                            ]
                                        ))
                                    ]
                                ))
                            ]
                        )
                    )
                    
                    cset = cs.CorrectionSet(
                        schema_version=2,
                        description=f"{name} SFs with systematic variations",
                        corrections=[corr]
                    )
                    
                    json_filename = f"tau_sf/{name}_SF_dm_{tagger_tag}_{args.year}{({'corr': '_corrTES', 'fullcorr': '_fullcorr'}.get(variant, ''))}_VSjet{current_jet_wp}_VSele{ele_wp}.json"
                    with open(json_filename, "w") as fout:
                        print(f">>> Writing JSON: {json_filename}")
                        fout.write(cset.json())
        
        except ImportError as e:
            print(f"Warning: Failed to import correctionlib: {e}")
            print("JSON files will not be created")
            
    # Old commented code for reference
    #   ###############################################################
    #   ## create JSON file with SFs (following correctionlib rules)
#       corr = cs.Correction(
#          name="TauIdSF",
#          version=1,
#          description="Tau Id SF, pT binned divided by DM",
#          inputs= [
#                  cs.Variable(name="genmatch", type="int", description="Tau genmatch, sf only on real taus (genmatch 5) "),
#                  cs.Variable(name="DM", type="int", description="Tau decay mode (0,1,10,11)"),
#                  cs.Variable(name="pT", type="real", description="Tau transverse momentum"),
#                  ], 
#          output={'name': "sf", 'type': "real", 'description': "Tau Id scale factor"},
#          data=cs.Category(
#               nodetype="category",
#               input="genmatch",
#               content=[
#                       cs.CategoryItem(key=1,value=1.0),
#                       cs.CategoryItem(key=2,value=1.0),
#                       cs.CategoryItem(key=3,value=1.0),
#                       cs.CategoryItem(key=4,value=1.0),
#                       cs.CategoryItem(key=5,
#                                       value=cs.Category(
#                                             nodetype="category",
#                                             input="DM",
#                                             content=[
#                                                     cs.CategoryItem(key=0,
#                                                     value=cs.Binning(
#                                                           nodetype="binning",
#                                                           input="pT",
#                                                           edges=sf_dict["0"]["edges"],
#                                                           content=sf_dict["0"]["content"] ,
#                                                           flow="clamp"
#                                                           )), 
#                                                     cs.CategoryItem(key=1,
#                                                     value=cs.Binning(
#                                                           nodetype="binning",
#                                                           input="pT",
#                                                           edges=sf_dict["1"]["edges"],
#                                                           content=sf_dict["1"]["content"] ,
#                                                           flow="clamp"
#                                                           )),
#                                                     cs.CategoryItem(key=10,
#                                                     value=cs.Binning(
#                                                           nodetype="binning",
#                                                           input="pT",
#                                                           edges=sf_dict["10"]["edges"],
#                                                           content=sf_dict["10"]["content"] ,
#                                                           flow="clamp"
#                                                           )),
#                                                     cs.CategoryItem(key=11,
#                                                     value=cs.Binning(
#                                                           nodetype="binning",
#                                                           input="pT",
#                                                           edges=sf_dict["11"]["edges"],
#                                                           content=sf_dict["11"]["content"] ,
#                                                           flow="clamp"
#                                                           )),
#                                                     ]
#                                                     )),
#                       cs.CategoryItem(key=6,value=1.0),
#                       cs.CategoryItem(key=0,value=1.0)
#                       ]
#                       )
#              )

    #   print("Evaluate a point: ")
    #   print(corr.to_evaluator().evaluate(5,11,300.))
    #   rich.print(corr)
    #   cset = cs.CorrectionSet(
    #          schema_version=2,
    #          description="Tau SFs",
    #          corrections=[
    #                       corr
    #                      ],
    #          )
    #   with open("tes_DeepTau2018v2p5VSjet_%s.json"%year, "w") as fout:
    #        print(">>>Writing JSON!")
    #        fout.write(cset.json())


def ensureDirectory(dirname):
  """Make directory if it does not exist."""
  if not os.path.exists(dirname):
      os.makedirs(dirname)
      print(">>> made directory %s"%dirname)


def main(args):
    print("Using configuration file: %s"%args.config)
    with open(args.config, 'r') as file:
        setup = yaml.safe_load(file)

    tag           = setup["tag"] if "tag" in setup else ""
    form          = args.form
    ele_wp        = args.ele_wp
    jet_wp        = args.jet_wp
    year          = args.year
    #CMSStyle.setCMSEra(year)

    plot_dm_graph(setup, form, ele_wp, jet_wp, tag=tag, variant=args.variant)
    




if __name__ == '__main__':

  description = '''This script makes plot of pt-dependants id SF measurments from txt file and config file.'''
  parser = ArgumentParser(prog="plot_it_SF",description=description,epilog="Success!")
  parser.add_argument('-c', '--config', dest='config', type=str, default='TauES_ID/config/Default_FitSetupTES_mutau_DM_mt65pt_lessptregion.yml', action='store', help="set config file")
  parser.add_argument('-f', '--form', dest='form', choices=['json', 'root'], type=str, default='root', action='store', help="select format")
  parser.add_argument('-e', '--electron_wp', dest='ele_wp', type=str, default='VVLoose', help="electron wp")
  parser.add_argument('-j', '--jet_wp', dest='jet_wp', type=str, default='Tight', help="jet working point")
  parser.add_argument('-y', '--year', dest='year', type=str, default='2025', help="year of the measurement")
  parser.add_argument('--variant', dest='variant', choices=['uncorr','corr','fullcorr'], default='uncorr',
                      help="uncorr: per-region; corr: per-DM TES; fullcorr: per-DM TES & common TauID with per-pT effective SFs")
  parser.add_argument('--tagger', dest='tagger', type=str, default='',
                      help="output-tree tagger suffix (e.g. pnet, upart); '' = DeepTau default")
  args = parser.parse_args()
  if args.tagger:
    TREE_TAG = "_" + args.tagger
  main(args)
  print(">>>\n>>> done\n")
