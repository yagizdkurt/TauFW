#!/usr/bin/env python
# =============================================================================
# LEGACY CODE - CORRECTION
# Original location: add_muon_weights.py
# Data-taking year: 2025
# Year basis: 2025 EOS tuples, Run2025 muon payload and branch names.
# Purpose: Adds 2025 muon ID/isolation and trigger scale-factor branches to existing MC pico
#          ROOT files using a Python JSON evaluator.
# Why legacy: One-off repair of a fixed 2025 EOS tuple campaign, with a personal AFS
#             calibration path; no repository caller. Filed directly under 2025 because the
#             muon payloads, target branches and input campaign all identify that data-taking
#             year.
# Status: Reference material; review dependencies and input paths before reuse.
# =============================================================================

"""
Script to add 2025 muon scale factor branches to MC ROOT pico files.

Adds two new branches per event:
  idisoweight_1_2025  = SF_MediumID * SF_TightPFIso  (evaluated at reco muon pt_1, eta_1)
  trigweight_2025     = SF_IsoMu24 trigger (or 1.0 if not in JSON)

Uses a pure Python JSON evaluator to avoid correctionlib version incompatibility
(CMSSW correctionlib 2.5.0 does not support explicit 'input' field in binning nodes).
"""

import os
import sys
import glob
import time
import array
import gzip
import json
import math

from ROOT import TFile, gROOT
gROOT.SetBatch(True)

###############################################################################
# CONFIGURATION
###############################################################################

EOS_BASE_PATH  = "/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/2025"
MC_SAMPLE_DIRS = ["DY", "ST", "TT", "VV", "WJ"]

MUON_SF_FILE = (
    "/afs/cern.ch/user/h/haawedik/CMSSW_14_1_0_pre4/src/TauFW"
    "/PicoProducer/data/lepton/MuonPOG/Run2025/muon_Z.json.gz"
)

SF_ID_KEY   = "NUM_MediumID_DEN_TrackerMuons"
SF_ISO_KEY  = "NUM_TightPFIso_DEN_MediumID"
SF_TRIG_KEY = "NUM_IsoMu24_DEN_CutBasedIdTight_and_PFIsoTight"

TREE_NAME = "tree"

NEW_BRANCH_IDISO  = "idisoweight_1_2025"
NEW_BRANCH_IDISO2 = "idisoweight_2_2025"  # second muon, mumu channel only
NEW_BRANCH_TRIG   = "trigweight_2025"

VERBOSE    = True
DRY_RUN    = False
MAX_FILES  = None   # set to integer to limit (for testing)
MAX_ERRORS = 1000


def _find_bin(edges, value):
    """Return bin index for value in edges array. Handles 'inf' string edge."""
    fvalue = float(value)
    for i in range(len(edges) - 1):
        low  = float(edges[i])
        high = math.inf if edges[i+1] == 'inf' else float(edges[i+1])
        if low <= fvalue < high:
            return i
    # clamp overflow to last bin
    return len(edges) - 2


def _evaluate_node(node, inputs):
    """Recursively evaluate a correctionlib data node."""
    ntype = node['nodetype']

    if ntype == 'binning':
        val = float(inputs[node['input']])
        idx = _find_bin(node['edges'], val)
        return _evaluate_node(node['content'][idx], inputs)

    elif ntype == 'multibinning':
        # multi-dimensional binning: find flat index
        axes = node['inputs']  # list of input names
        edges_list = node['edges']  # list of edge arrays per axis
        flat_idx = 0
        stride = 1
        idxs = []
        for ax, edges in zip(reversed(axes), reversed(edges_list)):
            val = float(inputs[ax])
            bi  = _find_bin(edges, val)
            idxs.insert(0, bi)
        for ax, edges, bi in zip(axes, edges_list, idxs):
            flat_idx = flat_idx * (len(edges) - 1) + bi
        return _evaluate_node(node['content'][flat_idx], inputs)

    elif ntype == 'category':
        key = inputs[node['input']]
        for item in node['content']:
            if str(item['key']) == str(key):
                if 'value' in item:
                    return item['value']
                return _evaluate_node(item['content'], inputs)
        raise KeyError(f"Category key {key!r} not found in {[i['key'] for i in node['content']]}")

    elif ntype == 'formula':
        # simple formula evaluation via Python eval (safe: only math operations)
        expr = node['expression']
        vars_ = {v: float(inputs[v]) for v in node.get('variables', [])}
        params = {f'p{i}': p for i, p in enumerate(node.get('parameters', []))}
        return float(eval(expr, {"__builtins__": {}}, {**vars_, **params, **vars(math)}))

    elif ntype == 'transform':
        new_inputs = dict(inputs)
        new_inputs[node['input']] = _evaluate_node(node['rule'], inputs)
        return _evaluate_node(node['content'], new_inputs)

    else:
        raise ValueError(f"Unknown nodetype: {ntype!r}")


def load_json_corrections(filepath):
    """Load correctionlib JSON (gzipped or plain) into a dict keyed by name."""
    print(f"\n[Loading muon SFs from: {filepath}]")
    if not os.path.exists(filepath):
        print(f"ERROR: file not found: {filepath}")
        return None
    opener = gzip.open if filepath.endswith('.gz') else open
    with opener(filepath, 'rt') as f:
        data = json.load(f)
    corr_dict = {c['name']: c['data'] for c in data['corrections']}
    print(f"  Loaded {len(corr_dict)} corrections")
    return corr_dict


def evaluate_sf(corr_dict, corr_name, eta, pt, syst='nominal'):
    """Evaluate a single scale factor. Returns 1.0 on failure."""
    if corr_name not in corr_dict:
        return 1.0
    inputs = {'eta': eta, 'pt': pt, 'scale_factors': syst}
    try:
        return float(_evaluate_node(corr_dict[corr_name], inputs))
    except Exception as e:
        return 1.0


def get_muon_sfs(corr_dict, pt, eta):
    """Return (idisoweight, trigweight) for a muon at given pt, eta."""
    sf_id  = evaluate_sf(corr_dict, SF_ID_KEY,  eta, pt)
    sf_iso = evaluate_sf(corr_dict, SF_ISO_KEY, eta, pt)
    sf_trig = evaluate_sf(corr_dict, SF_TRIG_KEY, eta, pt)
    return sf_id * sf_iso, sf_trig

###############################################################################
# FILE DISCOVERY
###############################################################################

def get_mc_files():
    if VERBOSE:
        print(f"\n[Searching for MC files in EOS]")
        print(f"  Base path: {EOS_BASE_PATH}")
    all_files = []
    for sample_dir in MC_SAMPLE_DIRS:
        sample_path = os.path.join(EOS_BASE_PATH, sample_dir)
        if not os.path.exists(sample_path):
            print(f"  WARNING: Directory not found: {sample_path}")
            continue
        files = glob.glob(os.path.join(sample_path, "**/*.root"), recursive=True)
        if VERBOSE:
            print(f"  {sample_dir}: found {len(files)} files")
        all_files.extend(files)
    all_files.sort()
    if VERBOSE:
        print(f"\n  Total MC files found: {len(all_files)}")
    return all_files

###############################################################################
# FILE PROCESSING
###############################################################################

def check_branch_exists(tree, branch_name):
    branch = tree.GetBranch(branch_name)
    return branch and branch.GetName() == branch_name


def process_file(filepath, corr_dict):
    fname = os.path.basename(filepath)
    is_mumu = '_mumu' in fname

    if VERBOSE:
        channel = 'mumu' if is_mumu else 'mutau'
        print(f"\n  Processing [{channel}]: {fname}")

    input_file = TFile.Open(filepath, 'READ')
    if not input_file or input_file.IsZombie():
        return False, 0, "Failed to open file"

    tree = input_file.Get(TREE_NAME)
    if not tree:
        input_file.Close()
        return False, 0, f"Tree '{TREE_NAME}' not found"

    num_events = tree.GetEntries()

    # check if already processed
    expected = [NEW_BRANCH_IDISO, NEW_BRANCH_TRIG]
    if is_mumu:
        expected.append(NEW_BRANCH_IDISO2)
    existing = [b for b in expected if check_branch_exists(tree, b)]
    if len(existing) == len(expected):
        input_file.Close()
        return False, num_events, "Already processed (all branches exist)"
    if 0 < len(existing) < len(expected):
        input_file.Close()
        return False, num_events, "Partial processing detected — skipping"

    for req in ['pt_1', 'eta_1']:
        if not check_branch_exists(tree, req):
            input_file.Close()
            return False, 0, f"Branch '{req}' not found"
    if is_mumu:
        for req in ['pt_2', 'eta_2']:
            if not check_branch_exists(tree, req):
                input_file.Close()
                return False, 0, f"Branch '{req}' not found (mumu)"

    if VERBOSE:
        print(f"    Events: {num_events}")

    if DRY_RUN:
        input_file.Close()
        return True, num_events, "Dry-run (no changes made)"

    input_file.Close()

    update_file = TFile.Open(filepath, 'UPDATE')
    if not update_file or update_file.IsZombie():
        return False, 0, "Failed to open in UPDATE mode"

    tree = update_file.Get(TREE_NAME)
    if not tree:
        update_file.Close()
        return False, 0, "Tree not found on re-open"

    idisoweight_arr  = array.array('f', [0.0])
    trigweight_arr   = array.array('f', [0.0])
    idisoweight2_arr = array.array('f', [0.0])

    br_idiso = tree.Branch(NEW_BRANCH_IDISO, idisoweight_arr, f"{NEW_BRANCH_IDISO}/F")
    br_trig  = tree.Branch(NEW_BRANCH_TRIG,  trigweight_arr,  f"{NEW_BRANCH_TRIG}/F")
    br_idiso2 = tree.Branch(NEW_BRANCH_IDISO2, idisoweight2_arr, f"{NEW_BRANCH_IDISO2}/F") if is_mumu else None

    new_branches = [NEW_BRANCH_IDISO, NEW_BRANCH_TRIG] + ([NEW_BRANCH_IDISO2] if is_mumu else [])
    if VERBOSE:
        print(f"    Created branches: {', '.join(new_branches)}")

    for i in range(num_events):
        tree.GetEntry(i)
        pt1  = float(tree.pt_1)
        eta1 = float(tree.eta_1)

        idisoweight, trigweight = get_muon_sfs(corr_dict, pt1, eta1)
        idisoweight_arr[0] = idisoweight
        trigweight_arr[0]  = trigweight
        br_idiso.Fill()
        br_trig.Fill()

        if is_mumu:
            pt2  = float(tree.pt_2)
            eta2 = float(tree.eta_2)
            idisoweight2, _ = get_muon_sfs(corr_dict, pt2, eta2)
            idisoweight2_arr[0] = idisoweight2
            br_idiso2.Fill()

        if VERBOSE and (i + 1) % 100000 == 0:
            print(f"    Processed {i+1}/{num_events} events")

    if VERBOSE:
        print(f"    Filled {num_events} events")

    tree.Write("", 1)  # kOverwrite
    update_file.Close()
    return True, num_events, "Success"

###############################################################################
# MAIN LOOP
###############################################################################

def process_all_files(corr_dict):
    print("\n" + "="*80)
    print("PROCESSING MC ROOT FILES")
    print("="*80)

    files = get_mc_files()
    if not files:
        print("ERROR: No ROOT files found!")
        return None, 0

    if MAX_FILES:
        files = files[:MAX_FILES]
        print(f"Limited to first {MAX_FILES} files")

    stats = {'total_files': len(files), 'processed': 0, 'skipped': 0, 'failed': 0, 'errors': []}
    start_time = time.time()

    for idx, filepath in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] {os.path.basename(filepath)}")
        success, num_events, message = process_file(filepath, corr_dict)

        if success:
            stats['processed'] += 1
            print(f"    OK {message} ({num_events} events)")
        elif "already" in message.lower():
            stats['skipped'] += 1
            print(f"    -- {message}")
        else:
            stats['failed'] += 1
            stats['errors'].append((os.path.basename(filepath), message))
            print(f"    FAIL {message}")

        if stats['failed'] >= MAX_ERRORS:
            print(f"Stopped: reached max errors ({MAX_ERRORS})")
            break

    return stats, time.time() - start_time


def main():
    print("\n" + "="*80)
    print("MUON SF BRANCH ADDER — Run2025")
    print("="*80)
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"EOS Base:  {EOS_BASE_PATH}")
    print(f"Samples:   {', '.join(MC_SAMPLE_DIRS)}")
    print(f"Branches:  {NEW_BRANCH_IDISO}, {NEW_BRANCH_TRIG}")
    if DRY_RUN:
        print("DRY-RUN MODE (no files will be modified)")

    corr_dict = load_json_corrections(MUON_SF_FILE)
    if not corr_dict:
        sys.exit(1)

    # sanity check
    print(f"\n[Sanity check: pt=30, eta=0.5]")
    idiso, trig = get_muon_sfs(corr_dict, 30., 0.5)
    print(f"  idisoweight = {idiso:.4f}")
    print(f"  trigweight  = {trig:.4f}")
    if idiso == 0.0 or trig == 0.0:
        print("ERROR: Got zero SF — check JSON keys!")
        sys.exit(1)

    stats, elapsed = process_all_files(corr_dict)
    if not stats:
        sys.exit(1)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total:     {stats['total_files']}")
    print(f"Processed: {stats['processed']}")
    print(f"Skipped:   {stats['skipped']}")
    print(f"Failed:    {stats['failed']}")
    print(f"Time:      {elapsed:.1f}s")
    if stats['errors']:
        print("Errors:")
        for fname, msg in stats['errors']:
            print(f"  - {fname}: {msg}")
    print("="*80)
    sys.exit(1 if stats['failed'] > 0 else 0)


if __name__ == "__main__":
    main()
