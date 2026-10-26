#!/usr/bin/env python
# =============================================================================
# LEGACY CODE - CORRECTION
# Original location: add_pileup_weights.py
# Data-taking year: 2025 and 2026
# Year basis: 2024 MC tuples of the 2025 campaign (pico2024/TES_variations/2025) reweighted to
#             2025, 2026 and combined data profiles.
# Purpose: Adds missing 2025, 2026 and combined 2025+2026 pileup-weight branches to existing
#          MC ROOT files in place.
# Why legacy: April 2026 repair of the same fixed 2025 EOS tuple campaign; hardcoded
#             calibration paths and no repository caller. This is campaign postprocessing
#             rather than a production API.
# Status: Reference material; review dependencies and input paths before reuse.
# =============================================================================

"""
Script to add pileup weight branches to MC ROOT files in EOS.
Date: April 2026

Description:
    Loops over all MC ROOT files in EOS directories (DY, ST, TT, VV, WJ),
    loads MC and data pileup histograms, then adds pileup weight branches
    for several data targets:
      - 2025: nominal + xsec variations (puweight_2025_<xsec>_v2)
      - 2026: nominal                   (puweight_2026_69p2)
      - combined 2025+2026: nominal     (puweight_2025_2026_69p2)
    The MC denominator (MC_PileUp_2025.root) is shared across all targets, since
    the same MC files are reweighted; only the data profile (numerator) changes.

    For each event, computes weight = data_bin_content / mc_bin_content
    using the npu_true variable. Handles empty bins by setting weight = 1.0.

    Branch-adding is idempotent per branch: only missing branches are added, so
    re-running tops up whatever is absent and preserves existing branches.

    Files are modified in-place on EOS.
"""

import os
import sys
import glob
import time
import array
from collections import OrderedDict

# ROOT imports
from ROOT import TFile, TH1D, gROOT, gDirectory

# Suppress ROOT info messages
gROOT.SetBatch(True)

###############################################################################
# CONFIGURATION
###############################################################################

# Input paths
EOS_BASE_PATH = "/eos/cms/store/group/phys_tau/TauFW/pico2024/TES_variations/2025"
MC_SAMPLE_DIRS = ["DY", "ST", "TT", "VV", "WJ"]
PILEUP_DATA_DIR = "/afs/cern.ch/user/h/haawedik/CMSSW_14_1_0_pre4/src/TauFW/PicoProducer/data/pileup"

# MC and data pileup histogram files
MC_PILEUP_FILE = os.path.join(PILEUP_DATA_DIR, "MC_PileUp_2025.root")
DATA_PILEUP_FILES = OrderedDict([
    # 2025 (nominal + xsec variations) — already written to the EOS files by earlier runs
    ('2025_80p0',      os.path.join(PILEUP_DATA_DIR, "Data_PileUp_2025_80p0.root")),
    ('2025_72p3832',   os.path.join(PILEUP_DATA_DIR, "Data_PileUp_2025_72p3832.root")),
    ('2025_69p2',      os.path.join(PILEUP_DATA_DIR, "Data_PileUp_2025_69p2.root")),
    ('2025_66p0168',   os.path.join(PILEUP_DATA_DIR, "Data_PileUp_2025_66p0168.root")),
    # 2026 nominal and combined 2025+2026 nominal (same MC denominator, only data profile differs)
    ('2026_69p2',      os.path.join(PILEUP_DATA_DIR, "Data_PileUp_2026_69p2.root")),
    ('2025_2026_69p2', os.path.join(PILEUP_DATA_DIR, "Data_PileUp_2025_2026_69p2.root")),
])

# Histogram names inside ROOT files
MC_HIST_NAME = "pileup"
DATA_HIST_NAME = "pileup"

# TTree settings
TREE_NAME = "tree"
NPU_BRANCH_NAME = "npu_true"
WEIGHT_BRANCH_PREFIX = "puweight_2025_"
WEIGHT_DTYPE = 'f'  # ROOT float type for branches

# Output weight branch names
WEIGHT_BRANCHES = OrderedDict([
    ('2025_80p0',      'puweight_2025_80p0_v2'),
    ('2025_72p3832',   'puweight_2025_72p3832_v2'),
    ('2025_69p2',      'puweight_2025_69p2_v2'),
    ('2025_66p0168',   'puweight_2025_66p0168_v2'),
    ('2026_69p2',      'puweight_2026_69p2'),          # NEW: reweight MC to 2026 data (nominal)
    ('2025_2026_69p2', 'puweight_2025_2026_69p2'),    # NEW: reweight MC to combined 2025+2026 data (nominal)
])

# Options
VERBOSE = True
DRY_RUN = False 
MAX_FILES = None  # Set to integer to limit number of files processed (for testing)
MAX_ERRORS = 1000   # Stop after this many file errors

###############################################################################
# UTILITY FUNCTIONS
###############################################################################

def safe_open_file(filepath, mode='READ'):
    """
    Safely open a ROOT file and return TFile object.
    
    Args:
        filepath (str): Path to ROOT file
        mode (str): 'READ' or 'RECREATE'
    
    Returns:
        TFile object or None on failure
    """
    try:
        if not os.path.exists(filepath):
            print(f"  ERROR: File not found: {filepath}")
            return None
        
        tfile = TFile.Open(filepath, mode)
        if not tfile or tfile.IsZombie():
            print(f"  ERROR: Failed to open file or file is corrupted: {filepath}")
            return None
        
        return tfile
    except Exception as e:
        print(f"  ERROR: Exception opening file {filepath}: {e}")
        return None


def load_histogram(filepath, histname):
    """
    Load a histogram from a ROOT file.
    
    Args:
        filepath (str): Path to ROOT file
        histname (str): Name of histogram
    
    Returns:
        TH1D object or None on failure
    """
    tfile = safe_open_file(filepath, 'READ')
    if not tfile:
        return None
    
    hist = tfile.Get(histname)
    if not hist:
        print(f"  ERROR: Histogram '{histname}' not found in {filepath}")
        tfile.Close()
        return None
    
    # Clone histogram to memory (prevents ROOT file ownership issues)
    hist_clone = hist.Clone(histname)
    hist_clone.SetDirectory(0)
    tfile.Close()
    
    return hist_clone


def normalize_histogram(hist, name=""):
    """
    Normalize histogram to sum to 1.0 (probability distribution).
    
    Args:
        hist (TH1D): Histogram to normalize
        name (str): Optional name for logging
    """
    integral = hist.Integral()
    if integral > 0:
        hist.Scale(1.0 / integral)
        if VERBOSE:
            print(f"    Normalized {name} histogram (integral was {integral:.6f})")
    else:
        print(f"    WARNING: {name} histogram has zero integral!")


def load_all_pileup_histograms():
    """
    Load all MC and data pileup histograms.
    
    Returns:
        dict: {
            'mc_hist': MC histogram,
            'data_hists': {'80p0': hist, '72p3832': hist, ...}
        }
        or None on failure
    """
    if VERBOSE:
        print("\n[Loading pileup histograms]")
    
    # Load MC histogram
    if VERBOSE:
        print(f"  Loading MC histogram from: {MC_PILEUP_FILE}")
    
    mc_hist = load_histogram(MC_PILEUP_FILE, MC_HIST_NAME)
    if not mc_hist:
        print("ERROR: Failed to load MC pileup histogram!")
        return None
    
    normalize_histogram(mc_hist, "MC")
    
    # Load data histograms
    data_hists = OrderedDict()
    for scenario, filepath in DATA_PILEUP_FILES.items():
        if VERBOSE:
            print(f"  Loading data histogram ({scenario}) from: {filepath}")
        
        hist = load_histogram(filepath, DATA_HIST_NAME)
        if not hist:
            print(f"ERROR: Failed to load data pileup histogram for {scenario}!")
            return None
        
        normalize_histogram(hist, f"Data ({scenario})")
        data_hists[scenario] = hist
    
    if VERBOSE:
        print(f"\nSuccessfully loaded all {len(data_hists) + 1} histograms")
    
    return {
        'mc_hist': mc_hist,
        'data_hists': data_hists,
    }


def get_pileup_weight(npu_true, data_hist, mc_hist):
    """
    Calculate pileup weight for a given npu_true value.
    
    Weight = data_bin_content / mc_bin_content
    
    Args:
        npu_true (float): Number of true pileup interactions
        data_hist (TH1D): Data pileup histogram (normalized)
        mc_hist (TH1D): MC pileup histogram (normalized)
    
    Returns:
        float: Weight (default 1.0 if MC bin is empty or weight > 5.0)
    """
    # Find bin for given npu_true value
    bin_idx = mc_hist.GetXaxis().FindBin(npu_true)
    
    # Get bin contents
    data_content = data_hist.GetBinContent(bin_idx)
    mc_content = mc_hist.GetBinContent(bin_idx)
    
    # Calculate weight with safety checks
    if mc_content > 0:
        weight = data_content / mc_content
        # Clamp only pathological outliers (preserve legitimate high weights in data-peak bins)
        if weight > 100.0:
            weight = 100.0
        return weight
    else:
        # Empty MC bin: return unity weight (no reweighting)
        return 1.0


def get_mc_files():
    """
    Discover all ROOT files in MC sample directories on EOS.
    
    Returns:
        list: Sorted list of file paths
    """
    if VERBOSE:
        print(f"\n[Searching for MC files in EOS]")
        print(f"  Base path: {EOS_BASE_PATH}")
    
    all_files = []
    
    for sample_dir in MC_SAMPLE_DIRS:
        sample_path = os.path.join(EOS_BASE_PATH, sample_dir)
        
        if not os.path.exists(sample_path):
            print(f"  WARNING: Directory not found: {sample_path}")
            continue
        
        # Find all .root files recursively
        pattern = os.path.join(sample_path, "**/*.root")
        files = glob.glob(pattern, recursive=True)
        
        if VERBOSE:
            print(f"  {sample_dir}: found {len(files)} files")
        
        all_files.extend(files)
    
    all_files.sort()
    
    if VERBOSE:
        print(f"\n  Total MC files found: {len(all_files)}")
    
    return all_files


def check_branch_exists(tree, branch_name):
    """
    Check if a branch exists in a TTree.
    
    Args:
        tree (TTree): ROOT tree
        branch_name (str): Branch name to check
    
    Returns:
        bool: True if branch exists
    """
    branch = tree.GetBranch(branch_name)
    return branch and branch.GetName() == branch_name  # PyROOT returns null pointer, not None


def process_file(filepath, histograms):
    """
    Process a single MC ROOT file: add pileup weight branches.
    
    Args:
        filepath (str): Path to ROOT file
        histograms (dict): {'mc_hist': ..., 'data_hists': {...}}
    
    Returns:
        tuple: (success: bool, num_events: int, message: str)
    """
    if VERBOSE:
        print(f"\n  Processing: {os.path.basename(filepath)}")
    
    # Open input file
    input_file = safe_open_file(filepath, 'READ')
    if not input_file:
        return False, 0, "Failed to open file"
    
    # Get tree
    tree = input_file.Get(TREE_NAME)
    if not tree:
        input_file.Close()
        return False, 0, f"Tree '{TREE_NAME}' not found"
    
    num_events = tree.GetEntries()
    
    # Check if npu_true branch exists
    if not check_branch_exists(tree, NPU_BRANCH_NAME):
        input_file.Close()
        return False, 0, f"Branch '{NPU_BRANCH_NAME}' not found"
    
    # Per-branch idempotency: add only the weight branches that are missing, so branches
    # written by earlier runs (e.g. the 2025 set) are preserved and re-runs are safe.
    branches_to_add = OrderedDict((key, name) for key, name in WEIGHT_BRANCHES.items()
                                  if not check_branch_exists(tree, name))
    if not branches_to_add:
        input_file.Close()
        return False, num_events, "Already processed (all weight branches exist)"

    if VERBOSE:
        print(f"    Events: {num_events}")

    if DRY_RUN:
        print(f"    DRY-RUN: Would add {len(branches_to_add)} weight branches: {', '.join(branches_to_add.values())}")
        input_file.Close()
        return True, num_events, "Dry-run (no changes made)"

    input_file.Close()

    # Open in UPDATE mode — adds branches in-place, preserves cutflow and other objects
    update_file = TFile.Open(filepath, 'UPDATE')
    if not update_file or update_file.IsZombie():
        return False, 0, "Failed to open file in UPDATE mode"

    tree = update_file.Get(TREE_NAME)
    if not tree:
        update_file.Close()
        return False, 0, f"Tree '{TREE_NAME}' not found on re-open"

    # Create only the missing branches on the existing tree
    weight_arrays = {}
    new_branches = []
    for scenario, branch_name in branches_to_add.items():
        weight_arrays[scenario] = array.array('f', [0.0])
        br = tree.Branch(branch_name, weight_arrays[scenario], f"{branch_name}/{WEIGHT_DTYPE}")
        new_branches.append(br)

    if VERBOSE:
        print(f"    Created {len(branches_to_add)} weight branches: {', '.join(branches_to_add.values())}")

    mc_hist = histograms['mc_hist']
    data_hists = histograms['data_hists']

    # Loop and fill only the new branches
    num_processed = 0
    for i in range(num_events):
        tree.GetEntry(i)
        npu_true = tree.npu_true

        for scenario in branches_to_add:
            weight = get_pileup_weight(npu_true, data_hists[scenario], mc_hist)
            weight_arrays[scenario][0] = weight

        for br in new_branches:
            br.Fill()

        num_processed += 1

        if VERBOSE and (i + 1) % 100000 == 0:
            print(f"    Processed {i + 1}/{num_events} events")

    if VERBOSE:
        print(f"    Filled {num_processed} events with weights")

    tree.Write("", 1)  # kOverwrite — replaces tree key in-place
    update_file.Close()

    if VERBOSE:
        print(f"    Successfully updated: {filepath}")
    return True, num_processed, "Success"


def process_all_files(histograms):
    """
    Process all MC ROOT files.
    
    Args:
        histograms (dict): Loaded pileup histograms
    
    Returns:
        dict: Summary statistics
    """
    print("\n" + "="*80)
    print("PROCESSING MC ROOT FILES")
    print("="*80)
    
    files = get_mc_files()
    
    if not files:
        print("ERROR: No ROOT files found!")
        return None
    
    if MAX_FILES:
        files = files[:MAX_FILES]
        print(f"\nLimited to first {MAX_FILES} files for testing")
    
    # Initialize statistics
    stats = {
        'total_files': len(files),
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'total_events': 0,
        'errors': [],
    }
    
    start_time = time.time()
    
    # Process each file
    for idx, filepath in enumerate(files, 1):
        print(f"\n[{idx}/{len(files)}] {os.path.basename(filepath)}")
        
        success, num_events, message = process_file(filepath, histograms)
        
        stats['total_events'] += num_events
        
        if success:
            stats['processed'] += 1
            print(f"    ✓ {message} ({num_events} events)")
        else:
            if "already exist" in message:
                stats['skipped'] += 1
                print(f"    ⊘ {message}")
            else:
                stats['failed'] += 1
                stats['errors'].append((os.path.basename(filepath), message))
                print(f"    ✗ {message}")
        
        # Stop if too many errors
        if stats['failed'] >= MAX_ERRORS:
            print(f"\nStopped: reached max errors ({MAX_ERRORS})")
            break
    
    elapsed = time.time() - start_time
    
    return stats, elapsed


def print_summary(stats, elapsed):
    """Print processing summary."""
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    print(f"\nTotal files:      {stats['total_files']}")
    print(f"Processed:        {stats['processed']}")
    print(f"Skipped:          {stats['skipped']}")
    print(f"Failed:           {stats['failed']}")
    print(f"Total events:     {stats['total_events']}")
    print(f"Time elapsed:     {elapsed:.1f} seconds")
    
    if stats['errors']:
        print(f"\nErrors:")
        for filename, error_msg in stats['errors']:
            print(f"  - {filename}: {error_msg}")
    
    print("\n" + "="*80)


###############################################################################
# MAIN
###############################################################################

def main():
    """Main execution function."""
    
    print("\n" + "="*80)
    print("PILEUP WEIGHT SCRIPT FOR MC ROOT TREES")
    print("="*80)
    print(f"\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"EOS Base:  {EOS_BASE_PATH}")
    print(f"Samples:   {', '.join(MC_SAMPLE_DIRS)}")
    print(f"Scenarios: {', '.join(WEIGHT_BRANCHES.keys())}")
    if DRY_RUN:
        print("\n⚠️  DRY-RUN MODE (no files will be modified)")
    print()
    
    # Load pileup histograms
    histograms = load_all_pileup_histograms()
    if not histograms:
        print("\nERROR: Failed to load pileup histograms. Exiting.")
        sys.exit(1)
    
    # Process all files
    result = process_all_files(histograms)
    if not result:
        print("\nERROR: File processing failed. Exiting.")
        sys.exit(1)
    
    stats, elapsed = result
    
    # Print summary
    print_summary(stats, elapsed)
    
    # Return exit code
    if stats['failed'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
