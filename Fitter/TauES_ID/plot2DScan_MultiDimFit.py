#!/usr/bin/env python
"""
Date : Sept 2025
Author : @haawedik
Description :
This script plots 2D parabolas from MultiDimFit output files when you have
scanned over two parameters simultaneously 
"""

import sys
import os
import yaml
import ROOT
import numpy as np
from math import sqrt, pi
from argparse import ArgumentParser
from ROOT import gROOT, gPad, gStyle, TFile, TCanvas, TLegend, TLatex, TF2, TGraph2D, TH2D, TPolyMarker3D, TGraphAsymmErrors, TLine, TEllipse
from ROOT import kBlack, kBlue, kRed, kGreen, kYellow, kOrange, kMagenta, kTeal, kAzure, TMath
import TauFW.Utilities.Drawing.CMSStyle as CMSStyle

# Ensure ROOT runs in batch mode
gROOT.SetBatch(True)
gStyle.SetOptTitle(0)

# CMS style
CMSStyle.setTDRStyle()

def ensureDirectory(dirname):
    """Make directory if it does not exist."""
    if not os.path.exists(dirname):
        os.makedirs(dirname)

def ensureDirectory(dirname):
    """Make directory if it does not exist."""
    if not os.path.exists(dirname):
        os.makedirs(dirname)

def ensureTFile(filename, option='READ'):
    """Open TFile and make sure it exists."""
    if not os.path.isfile(filename):
        print(f"ERROR: File {filename} does not exist!")
        sys.exit(1)
    file = TFile(filename, option)
    if not file or file.IsZombie():
        print(f"ERROR: Could not open file {filename}")
        sys.exit(1)
    return file

def format_region_label(region, setup=None):
    """Format region name to match CMS style (e.g., DM0, DM1_pt1 -> DM1, pt: 20-40)"""
    # If setup is provided, use the title directly from config
    if setup and 'regions' in setup and region in setup['regions']:
        return setup['regions'][region].get('title', region)
    
    # Fallback to parsing the region name
    if '_pt' in region:
        dm_part, pt_part = region.split('_pt', 1)
        # Generic fallback - just show the pt bin number
        return f"{dm_part}, pt bin {pt_part}"
    else:
        return region

def format_region_for_sorting(region):
    """Create sorting key for regions to match your plot order"""
    # Desired order (reverse decay-mode order). Includes the PNet/UParT-only
    # DM2 (h^{+-}2pi0) and the DMrest catch-all bin; harmless for DeepTau (4 bins).
    order_map = {
        'DM11': 0,
        'DM10': 1,
        'DM2': 2,
        'DM1': 3,
        'DM0': 4,
        'DMrest': 5,
    }
    
    if '_pt' in region:
        dm_part, pt_part = region.split('_pt', 1)
        base_order = order_map.get(dm_part, 999)
        # pt bins in reverse order (pt4, pt3, pt2, pt1)
        pt_order = 10 - int(pt_part) if pt_part.isdigit() else 0
        return (base_order, pt_order)
    else:
        return (order_map.get(region, 999), 0)

def interpolate_scan_data(poi1_vals, poi2_vals, nll_vals, nbins=200):
    """Create a smoother 2D histogram by interpolating the scan data"""
    try:
        from scipy.interpolate import griddata
        from scipy.ndimage import gaussian_filter
        from scipy.interpolate import Rbf
    except ImportError:
        raise ImportError("scipy is required for interpolation (griddata / Rbf / gaussian_filter)")
     
    poi1_vals = np.array(poi1_vals)
    poi2_vals = np.array(poi2_vals)
    nll_vals = np.array(nll_vals)
    
    # Create regular grid with higher resolution
    poi1_min, poi1_max = np.min(poi1_vals), np.max(poi1_vals)
    poi2_min, poi2_max = np.min(poi2_vals), np.max(poi2_vals)
    
    # Add smaller padding for better contours
    poi1_range = poi1_max - poi1_min
    poi2_range = poi2_max - poi2_min
    padding = 0.05  # Reduced padding
    poi1_min -= padding * poi1_range
    poi1_max += padding * poi1_range
    poi2_min -= padding * poi2_range
    poi2_max += padding * poi2_range
    
    # Create high-resolution grid
    poi1_grid = np.linspace(poi1_min, poi1_max, nbins)
    poi2_grid = np.linspace(poi2_min, poi2_max, nbins)
    poi1_mesh, poi2_mesh = np.meshgrid(poi1_grid, poi2_grid)
    
    # Interpolate NLL values onto grid
    points = np.column_stack((poi1_vals, poi2_vals))
    
    max_nll = float(np.nanmax(nll_vals))
    # Try cubic interpolation with a finite fill_value to avoid NaNs
    try:
        nll_interpolated = griddata(points, nll_vals, (poi1_mesh, poi2_mesh),
                                    method='cubic', fill_value=max_nll)
        # If cubic left NaNs, fill those with linear
        if np.any(~np.isfinite(nll_interpolated)):
            nll_linear = griddata(points, nll_vals, (poi1_mesh, poi2_mesh),
                                  method='linear', fill_value=max_nll)
            nll_interpolated[~np.isfinite(nll_interpolated)] = nll_linear[~np.isfinite(nll_interpolated)]
    except Exception:
        # As a more robust fallback try radial-basis interpolation (RBF) which extrapolates better
        try:
            rbf = Rbf(poi1_vals, poi2_vals, nll_vals, function='linear')
            nll_interpolated = rbf(poi1_mesh, poi2_mesh)
        except Exception:
            # Last resort: linear griddata with finite fill
            nll_interpolated = griddata(points, nll_vals, (poi1_mesh, poi2_mesh),
                                        method='linear', fill_value=max_nll)

    # Ensure no NaNs remain (safety) and treat outside-hull as high cost
    nll_interpolated = np.where(np.isfinite(nll_interpolated), nll_interpolated, max_nll)
    # Gentle Gaussian smoothing to keep small-scale features (smaller sigma for higher accuracy)
    nll_interpolated = gaussian_filter(nll_interpolated, sigma=0.8)
     
    return poi1_grid, poi2_grid, nll_interpolated

def get_asymm_errors_from_grid(poi1_grid, poi2_grid, nll_grid, best_poi1, best_poi2, level=1.0, max_expand=5.0):
    """Find asymmetric errors from a 2D interpolated grid (connected component projection).
    Returns (p1_dn, p1_up, p2_dn, p2_up) or None."""
    import numpy as _np
    ix_best = int(_np.argmin(_np.abs(poi1_grid - best_poi1)))
    iy_best = int(_np.argmin(_np.abs(poi2_grid - best_poi2)))
    ny, nx = nll_grid.shape
    if ny != len(poi2_grid) or nx != len(poi1_grid):
        return None
    levels_to_try = _np.linspace(level, level * max_expand, num=8)
    for lvl in levels_to_try:
        mask = _np.isfinite(nll_grid) & (nll_grid <= float(lvl))
        if not _np.any(mask):
            continue
        true_idxs = _np.argwhere(mask)  # [iy, ix]
        if mask[iy_best, ix_best]:
            start = (iy_best, ix_best)
        else:
            d2 = (true_idxs[:,0] - iy_best)**2 + (true_idxs[:,1] - ix_best)**2
            nearest = true_idxs[_np.argmin(d2)]
            start = (int(nearest[0]), int(nearest[1]))
        visited = _np.zeros_like(mask, dtype=bool)
        stack = [start]
        comp_iy, comp_ix = [], []
        while stack:
            iy, ix = stack.pop()
            if iy < 0 or iy >= ny or ix < 0 or ix >= nx:
                continue
            if visited[iy, ix] or not mask[iy, ix]:
                continue
            visited[iy, ix] = True
            comp_iy.append(iy); comp_ix.append(ix)
            stack.extend([(iy-1, ix),(iy+1, ix),(iy, ix-1),(iy, ix+1)])
        if len(comp_ix) == 0:
            continue
        comp_x = poi1_grid[_np.array(comp_ix, dtype=int)]
        comp_y = poi2_grid[_np.array(comp_iy, dtype=int)]
        min_x, max_x = float(_np.min(comp_x)), float(_np.max(comp_x))
        min_y, max_y = float(_np.min(comp_y)), float(_np.max(comp_y))
        p1_dn = max(0.0, best_poi1 - min_x); p1_up = max(0.0, max_x - best_poi1)
        p2_dn = max(0.0, best_poi2 - min_y); p2_up = max(0.0, max_y - best_poi2)
        if p1_dn + p1_up + p2_dn + p2_up > 0.0:
            return p1_dn, p1_up, p2_dn, p2_up
    return None

def calculate_correlation_and_uncertainties(poi1_vals, poi2_vals, nll_vals):
    """Calculate correlation and 1σ uncertainties by profiling each POI (2ΔlnL = 1 => ΔlnL = 0.5)."""
    poi1_vals = np.array(poi1_vals)
    poi2_vals = np.array(poi2_vals)
    nll_vals = np.array(nll_vals)

    # Best fit point (minimum deltaNLL)
    min_idx = np.argmin(nll_vals)
    best_poi1 = float(poi1_vals[min_idx])
    best_poi2 = float(poi2_vals[min_idx])
    min_nll = float(nll_vals[min_idx])

    def profile_and_crossings(fixed_vals, other_vals, nlls, best_val, threshold=1):
        """Robust profiling + flexible-crossing finder (quadratic fallback instead of nearest-point)."""
        unique_raw = np.unique(np.sort(fixed_vals))
        if len(unique_raw) > 1:
            spacing = np.median(np.diff(unique_raw))
            tol = max(1e-10, 0.2 * spacing)
        else:
            tol = 1e-8
        unique_x = np.unique(np.round(unique_raw, decimals=12))
        prof_y = np.full_like(unique_x, np.nan, dtype=float)

        # Build profile with tolerant grouping
        for i, x in enumerate(unique_x):
            mask = np.isclose(fixed_vals, x, atol=tol, rtol=0)
            if np.any(mask):
                prof_y[i] = np.min(nlls[mask])

        # Replace totally empty profile entries with a large finite value
        max_nll = float(np.nanmax(nlls))
        prof_y = np.where(np.isfinite(prof_y), prof_y, max_nll)

        # Subtract global minimum to get profile ΔNLL
        prof_d = prof_y - min_nll

        # Find index of closest x to best_val
        best_idx = int(np.argmin(np.abs(unique_x - best_val)))

        # Helper: linear crossing finder on one side
        def find_cross(xarr, yarr, start_idx, direction, thr):
            i = start_idx
            while 0 <= i + direction < len(xarr):
                y1 = yarr[i]; y2 = yarr[i + direction]
                if not (np.isfinite(y1) and np.isfinite(y2)):
                    i += direction; continue
                # check for bracket (including equality)
                if (y1 - thr) * (y2 - thr) <= 0:
                    x1 = xarr[i]; x2 = xarr[i + direction]
                    if y2 == y1:
                        return 0.5 * (x1 + x2)
                    frac = (thr - y1) / (y2 - y1)
                    return x1 + frac * (x2 - x1)
                i += direction
            return None

        # try nominal threshold
        left_x = find_cross(unique_x, prof_d, best_idx, -1, threshold)
        right_x = find_cross(unique_x, prof_d, best_idx, +1, threshold)

        # if missing, try relaxed thresholds (slightly lower/higher)
        if left_x is None or right_x is None:
            for thr in (threshold * 0.95, threshold * 1.05):
                if left_x is None:
                    left_x = find_cross(unique_x, prof_d, best_idx, -1, thr)
                if right_x is None:
                    right_x = find_cross(unique_x, prof_d, best_idx, +1, thr)
                if left_x is not None and right_x is not None:
                    break

        # Quadratic-fit fallback (replace nearest-point approximation)
        def quad_fallback(xarr, yarr, start_idx, direction, thr, max_pts=7):
            # collect up to max_pts points on the requested side including the closest to best
            pts_x, pts_y = [], []
            # start searching from the neighbor toward the side (avoid picking the best point twice)
            i = start_idx if (0 <= start_idx < len(xarr)) else (start_idx - direction)
            count = 0
            while 0 <= i < len(xarr) and count < max_pts:
                pts_x.append(xarr[i]); pts_y.append(yarr[i])
                i += direction
                count += 1
            if len(pts_x) < 3:
                return None  # not enough points for a quadratic fit
            try:
                # fit quadratic: y = a x^2 + b x + c
                coeff = np.polyfit(pts_x, pts_y, 2)
                # solve a x^2 + b x + (c - thr) = 0
                a, b, c = coeff
                c_shift = c - thr
                # guard against degenerate a ~ 0 (linear)
                if abs(a) < 1e-12:
                    # linear fallback using last two points
                    x1, x2 = pts_x[0], pts_x[1] if direction == +1 else pts_x[-2], pts_x[-1]
                    y1, y2 = pts_y[0], pts_y[1] if direction == +1 else pts_y[-2], pts_y[-1]
                    if y2 == y1:
                        return None
                    frac = (thr - y1) / (y2 - y1)
                    return x1 + frac * (x2 - x1)
                disc = b*b - 4*a*c_shift
                if disc < 0:
                    return None
                roots = np.roots([a, b, c_shift])
                # pick root on the correct side of best_val
                candidates = []
                for r in roots:
                    if not np.isfinite(r):
                        continue
                    if direction == -1 and r < best_val:
                        candidates.append(r)
                    if direction == +1 and r > best_val:
                        candidates.append(r)
                if not candidates:
                    return None
                # choose candidate closest to best_val
                return float(min(candidates, key=lambda rr: abs(rr - best_val)))
            except Exception:
                return None

        # apply quadratic fallback where needed
        if left_x is None:
            left_x = quad_fallback(unique_x, prof_d, best_idx - 1, -1, threshold)
        if right_x is None:
            right_x = quad_fallback(unique_x, prof_d, best_idx + 1, +1, threshold)

        # If still None, leave as None -> will produce NaN errors (preferred over nearest-point hack)
        err_down = np.nan if left_x is None else best_val - left_x
        err_up = np.nan if right_x is None else right_x - best_val
        return err_down, err_up, unique_x, prof_d

    # def profile_and_crossings(fixed_vals, other_vals, nlls, best_val, threshold=1):
    #     """Profile: for each unique fixed_val take min nll over otherVals.
    #        Then find left/right crossings where profile - min_nll = threshold.
    #        Returns (err_down, err_up, profile_x, profile_y). If crossing not found, return (np.nan,np.nan,...)."""
    #     unique_x = np.unique(np.sort(fixed_vals))
    #     prof_y = np.full_like(unique_x, np.inf, dtype=float)
    #     # Build profile
    #     for i, x in enumerate(unique_x):
    #         mask = fixed_vals == x
    #         if np.any(mask):
    #             prof_y[i] = np.min(nlls[mask])
    #     # Subtract global minimum to get profile ΔNLL
    #     prof_d = prof_y - min_nll

    #     # Find index of closest x to best_val
    #     best_idx = int(np.argmin(np.abs(unique_x - best_val)))

    #     # Helper to find crossing on one side
    #     def find_cross(xarr, yarr, start_idx, direction):
    #         # direction = -1 (left) or +1 (right)
    #         i = start_idx
    #         while 0 <= i + direction < len(xarr):
    #             y1 = yarr[i]
    #             y2 = yarr[i + direction]
    #             if (y1 <= threshold and y2 > threshold) or (y1 >= threshold and y2 < threshold):
    #                 # linear interpolation
    #                 x1 = xarr[i]
    #                 x2 = xarr[i + direction]
    #                 if y2 == y1:
    #                     return (x1 + x2) / 2.0
    #                 frac = (threshold - y1) / (y2 - y1)
    #                 return x1 + frac * (x2 - x1)
    #             i += direction
    #         return None

    #     left_x = find_cross(unique_x, prof_d, best_idx, -1)
    #     right_x = find_cross(unique_x, prof_d, best_idx, +1)

    #     err_down = np.nan if left_x is None else best_val - left_x
    #     err_up = np.nan if right_x is None else right_x - best_val
    #     return err_down, err_up, unique_x, prof_d

    # Profile POI1 (fix POI1, minimize over POI2)
    poi1_err_down, poi1_err_up, prof_x1, prof_d1 = profile_and_crossings(poi1_vals, poi2_vals, nll_vals, best_poi1)
    # Profile POI2 (fix POI2, minimize over POI1)
    poi2_err_down, poi2_err_up, prof_x2, prof_d2 = profile_and_crossings(poi2_vals, poi1_vals, nll_vals, best_poi2)

    # Create symmetric errors for backward compatibility
    def symmetric(err_down, err_up, poi_vals):
        if np.isnan(err_down) and np.isnan(err_up):
            # fallback: use range/6 as approx 1σ (if profiling failed)
            rng = np.max(poi_vals) - np.min(poi_vals)
            return rng / 6.0 if rng > 0 else 0.0
        # if one side missing, use the available side
        if np.isnan(err_down):
            return float(err_up)
        if np.isnan(err_up):
            return float(err_down)
        return float(0.5 * (err_up + err_down))

    poi1_err = symmetric(poi1_err_down, poi1_err_up, poi1_vals)
    poi2_err = symmetric(poi2_err_down, poi2_err_up, poi2_vals)

    # If asymmetric errors are missing, try to recover them from an interpolated 2D grid
    if (not np.isfinite(poi1_err_down) or not np.isfinite(poi1_err_up) or
        not np.isfinite(poi2_err_down) or not np.isfinite(poi2_err_up)):
        try:
            # moderate grid resolution (speed vs accuracy)
            g_x, g_y, nll_grid = interpolate_scan_data(poi1_vals, poi2_vals, nll_vals, nbins=80)
            grid_errs = get_asymm_errors_from_grid(g_x, g_y, nll_grid, best_poi1, best_poi2, level=1.0, max_expand=4.0)
            if grid_errs is not None:
                g1_dn, g1_up, g2_dn, g2_up = grid_errs
                if not np.isfinite(poi1_err_down) or poi1_err_down <= 0.0:
                    poi1_err_down = g1_dn
                if not np.isfinite(poi1_err_up) or poi1_err_up <= 0.0:
                    poi1_err_up = g1_up
                if not np.isfinite(poi2_err_down) or poi2_err_down <= 0.0:
                    poi2_err_down = g2_dn
                if not np.isfinite(poi2_err_up) or poi2_err_up <= 0.0:
                    poi2_err_up = g2_up
                # recompute symmetric
                poi1_err = symmetric(poi1_err_down, poi1_err_up, poi1_vals)
                poi2_err = symmetric(poi2_err_down, poi2_err_up, poi2_vals)
                print(">>> Recovered asymmetric errors from interpolated grid:", g1_dn, g1_up, g2_dn, g2_up)
        except Exception:
            pass

    # --- Calculate correlation coefficient ---
    try:
        corr_threshold = 4.0  # Use points within Δ(−2lnL) < 4 (approx 95% CL in 1D, 2σ)
        local_mask = (nll_vals - min_nll) < corr_threshold
        if np.sum(local_mask) >= 3:
            # Enough local points: compute sample covariance
            cov = np.cov(poi1_vals[local_mask], poi2_vals[local_mask])
            if cov[0,0] > 0 and cov[1,1] > 0:
                corr = float(cov[0,1] / np.sqrt(cov[0,0] * cov[1,1]))
            else:
                corr = 0.0
        else:
            # Too few local points: use weighted covariance (weights ~ likelihood)
            w = np.exp(-0.5 * (nll_vals - min_nll))
            w_sum = np.sum(w)
            if w_sum > 0:
                w = w / w_sum
                mean1 = float(np.sum(poi1_vals * w))
                mean2 = float(np.sum(poi2_vals * w))
                cov12 = float(np.sum(w * (poi1_vals - mean1) * (poi2_vals - mean2)))
                var1 = float(np.sum(w * (poi1_vals - mean1)**2))
                var2 = float(np.sum(w * (poi2_vals - mean2)**2))
                if var1 > 0 and var2 > 0:
                    corr = float(cov12 / np.sqrt(var1 * var2))
                else:
                    corr = 0.0
            else:
                corr = 0.0
    except Exception:
        corr = 0.0
    # --- End correlation calculation ---

    # Debug prints
    print(f">>> Profiled 1σ (ΔlnL=0.5) results:")
    print(f"    POI1 best = {best_poi1:.6f}, -{poi1_err_down if not np.isnan(poi1_err_down) else float('nan'):.6f}/+{poi1_err_up if not np.isnan(poi1_err_up) else float('nan'):.6f}, sym={poi1_err:.6f}")
    print(f"    POI2 best = {best_poi2:.6f}, -{poi2_err_down if not np.isnan(poi2_err_down) else float('nan'):.6f}/+{poi2_err_up if not np.isnan(poi2_err_up) else float('nan'):.6f}, sym={poi2_err:.6f}")
    print(f"    Correlation (local ΔNLL<4): {corr:.4f}")

    # Return symmetric errors for compatibility plus asymmetric components
    return corr, poi1_err, poi2_err, {
        'poi1_err_down': poi1_err_down,
        'poi1_err_up': poi1_err_up,
        'poi2_err_down': poi2_err_down,
        'poi2_err_up': poi2_err_up,
        'profile_poi1_x': prof_x1, 'profile_poi1_d': prof_d1,
        'profile_poi2_x': prof_x2, 'profile_poi2_d': prof_d2
    }
def extract_2d_scan_data(multidimfit_file, poi1_name, poi2_name):
    """
    Extract 2D scan data from MultiDimFit output file using direct tree loop.
    Finds best fit (min NLL) and 1-sigma intervals (NLL <= 0.5).
    """
    print(f">>> Reading 2D scan data from {multidimfit_file}")
    
    file = ensureTFile(multidimfit_file)
    tree = file.Get('limit')
    if not tree:
        print("ERROR: Could not find 'limit' tree in MultiDimFit file")
        file.Close()
        return None
    
    # Verify branches exist
    branches = [b.GetName() for b in tree.GetListOfBranches()]
    if poi1_name not in branches or poi2_name not in branches or "deltaNLL" not in branches:
        print(f"ERROR: Missing branches. Looking for {poi1_name}, {poi2_name}, deltaNLL")
        print(f"Available: {branches}")
        file.Close()
        return None

    # Arrays for plotting
    poi1_vals = []
    poi2_vals = []
    nll_vals = [] # 2*NLL for plotting compatibility
    
    # Arrays for 1-sigma calculation
    poi1_in_1sigma = []
    poi2_in_1sigma = []
    
    best_val = float("inf")
    best_idx = 0
    best_poi1 = 0.0
    best_poi2 = 0.0
    
    nentries = tree.GetEntries()
    print(f">>> Processing {nentries} entries")
    
    for i in range(nentries):
        tree.GetEntry(i)
        
        val_poi1 = getattr(tree, poi1_name)
        val_poi2 = getattr(tree, poi2_name)
        val_nll = getattr(tree, "deltaNLL")
        
        # Store for plotting (convert NLL to 2*NLL for standard likelihood plots)
        poi1_vals.append(val_poi1)
        poi2_vals.append(val_poi2)
        nll_vals.append(2 * val_nll)
        
        # Logic for 1-sigma interval (deltaNLL <= 0.5)
        if 0 <= val_nll <= 0.5:
            poi1_in_1sigma.append(val_poi1)
            poi2_in_1sigma.append(val_poi2)
            
        # Logic for best fit (minimum non-negative deltaNLL)
        if val_nll < best_val and val_nll >= 0:
            best_val = val_nll
            best_idx = i
            best_poi1 = val_poi1
            best_poi2 = val_poi2
            
    file.Close()
    
    # Calculate 1-sigma ranges
    if poi1_in_1sigma:
        poi1_low = min(poi1_in_1sigma)
        poi1_high = max(poi1_in_1sigma)
    else:
        print(f"WARNING: No points found within 1-sigma region for {poi1_name}")
        poi1_low = best_poi1
        poi1_high = best_poi1
        
    if poi2_in_1sigma:
        poi2_low = min(poi2_in_1sigma)
        poi2_high = max(poi2_in_1sigma)
    else:
        print(f"WARNING: No points found within 1-sigma region for {poi2_name}")
        poi2_low = best_poi2
        poi2_high = best_poi2

    # Debug prints as requested
    print(f"[DEBUG] {poi1_name} 1-sigma range: {poi1_low} - {poi1_high}")
    print(f"[DEBUG] {poi2_name} 1-sigma range: {poi2_low} - {poi2_high}")
    print(f"[DEBUG] Best fit entry index: {best_idx} with deltaNLL = {best_val}")
    print(f"[DEBUG] Best fit {poi1_name}: {best_poi1}")
    print(f"[DEBUG] Best fit {poi2_name}: {best_poi2}")
    
    print(f"[INFO] Extracted {poi1_name}: {best_poi1:.6f}")
    print(f"[INFO] Extracted {poi2_name}: {best_poi2:.6f}")

    # Calculate asymmetric errors
    poi1_err_down = best_poi1 - poi1_low
    poi1_err_up = poi1_high - best_poi1
    poi2_err_down = best_poi2 - poi2_low
    poi2_err_up = poi2_high - best_poi2
    
    # Symmetric error approximation
    poi1_err = (poi1_err_down + poi1_err_up) / 2.0
    poi2_err = (poi2_err_down + poi2_err_up) / 2.0
    
    # Calculate correlation using points near the minimum (approx 2 sigma region)
    import numpy as np
    poi1_arr = np.array(poi1_vals)
    poi2_arr = np.array(poi2_vals)
    nll_arr = np.array(nll_vals) # 2*NLL
    
    # Use points within 2*NLL < 4 (approx 95% CL) for correlation estimate
    mask = nll_arr < 4.0
    correlation = 0.0
    if np.sum(mask) >= 3:
        try:
            cov = np.cov(poi1_arr[mask], poi2_arr[mask])
            if cov[0,0] > 0 and cov[1,1] > 0:
                correlation = float(cov[0,1] / np.sqrt(cov[0,0] * cov[1,1]))
        except Exception:
            correlation = 0.0
            
    return {
        'poi1_name': poi1_name,
        'poi2_name': poi2_name,
        'poi1_vals': np.array(poi1_vals),
        'poi2_vals': np.array(poi2_vals),
        'delta_nll_vals': np.array(nll_vals),
        'best_poi1': best_poi1,
        'best_poi2': best_poi2,
        'poi1_err': poi1_err,
        'poi2_err': poi2_err,
        'poi1_err_down': poi1_err_down,
        'poi1_err_up': poi1_err_up,
        'poi2_err_down': poi2_err_down,
        'poi2_err_up': poi2_err_up,
        'correlation': correlation,
        # Store absolute limits for writing to file if needed
        'poi1_low': poi1_low,
        'poi1_high': poi1_high,
        'poi2_low': poi2_low,
        'poi2_high': poi2_high
    }

def plot_2d_scan(setup, region, year, scan_data, **kwargs):
    """
    Plot 2D parabola from MultiDimFit scan data.
    """
    print(f">>> Plotting 2D scan for {region}")
    
    indir = kwargs.get('indir', f"output_{year}")
    outdir = indir.replace('output', 'plots')
    tag = kwargs.get('tag', "")
    plottag = kwargs.get('plottag', "")
    poi1_name = scan_data['poi1_name']
    poi2_name = scan_data['poi2_name']
    era = f"{year}-13TeV"
    channel = setup["channel"].replace("mu", "m").replace("tau", "t")
    
    ensureDirectory(outdir)
    
    # Canvas name
    canvasname = f"{outdir}/scan_2D_{poi1_name}_{poi2_name}_{channel}_{region}{tag}{plottag}"
    
    # Get data arrays
    poi1_vals = scan_data['poi1_vals']
    poi2_vals = scan_data['poi2_vals']
    delta_nll_vals = scan_data['delta_nll_vals']
    best_poi1 = scan_data['best_poi1']
    best_poi2 = scan_data['best_poi2']
    
    # Determine plot ranges
    poi1_min, poi1_max = np.min(poi1_vals), np.max(poi1_vals)
    poi2_min, poi2_max = np.min(poi2_vals), np.max(poi2_vals)
    
    # Add some margin
    poi1_range = poi1_max - poi1_min
    poi2_range = poi2_max - poi2_min
    margin = 0.1
    
    poi1_min -= margin * poi1_range
    poi1_max += margin * poi1_range
    poi2_min -= margin * poi2_range
    poi2_max += margin * poi2_range
    
    # Create 2D histogram with higher resolution for more accurate contours
    nbins_x = 50 # 20
    nbins_y = 50  #20
    hist_2d = TH2D("hist_2d", "", nbins_x, poi1_min, poi1_max, nbins_y, poi2_min, poi2_max)
    
    # Always try interpolation for smoother results
    use_interpolation = True
    
    try:
        # Try to use scipy interpolation for smoother results
        poi1_grid, poi2_grid, nll_interpolated = interpolate_scan_data(
            poi1_vals, poi2_vals, delta_nll_vals, nbins_x)
        
        # Fill histogram with interpolated data
        for i in range(nbins_x):
            for j in range(nbins_y):
                hist_2d.SetBinContent(i+1, j+1, nll_interpolated[j, i])
        print(">>> Using interpolated scan data for smoother plot")
        
    except (ImportError, Exception) as e:
        print(f">>> Interpolation failed ({e}), using direct binning with heavy smoothing")
        use_interpolation = False
        
        # Fill histogram using the scan data (direct binning)
        for i in range(len(poi1_vals)):
            bin_x = hist_2d.GetXaxis().FindBin(poi1_vals[i])
            bin_y = hist_2d.GetYaxis().FindBin(poi2_vals[i])
            
            # Set bin content to minimum of current content and new value
            # (in case multiple scan points fall in the same bin)
            current_content = hist_2d.GetBinContent(bin_x, bin_y)
            if current_content == 0 or delta_nll_vals[i] < current_content:
                hist_2d.SetBinContent(bin_x, bin_y, delta_nll_vals[i])
        
        # For empty bins, interpolate from nearby filled bins
        # This is a simple nearest-neighbor interpolation
        for i in range(1, nbins_x + 1):
            for j in range(1, nbins_y + 1):
                if hist_2d.GetBinContent(i, j) == 0:
                    x_center = hist_2d.GetXaxis().GetBinCenter(i)
                    y_center = hist_2d.GetYaxis().GetBinCenter(j)
                    
                    # Find nearest scan point
                    distances = np.sqrt((poi1_vals - x_center)**2 + (poi2_vals - y_center)**2)
                    nearest_idx = np.argmin(distances)
                    hist_2d.SetBinContent(i, j, delta_nll_vals[nearest_idx])
        
        # Apply heavy smoothing to get rid of the grid pattern
        for _ in range(5):  # Multiple smoothing iterations
            hist_2d.Smooth(1)
    
    # Set up canvas
    canvas = TCanvas('canvas', 'canvas', 100, 100, 800, 700)
    canvas.SetFillColor(0)
    canvas.SetBorderMode(0)
    canvas.SetFrameFillStyle(0)
    canvas.SetFrameBorderMode(0)
    canvas.SetTopMargin(0.07)
    canvas.SetBottomMargin(0.12)
    canvas.SetLeftMargin(0.12)
    canvas.SetRightMargin(0.15)  # Space for color scale
    canvas.cd()
    
    # Set axis titles
    if 'tes' in poi1_name.lower():
        x_title = "Tau energy scale"
    elif 'tid_sf' in poi1_name.lower():
        x_title = "Tau ID scale factor"
    else:
        x_title = poi1_name
        
    if 'tes' in poi2_name.lower():
        y_title = "Tau energy scale"
    elif 'tid_sf' in poi2_name.lower():
        y_title = "Tau ID scale factor"
    else:
        y_title = poi2_name
    
    hist_2d.GetXaxis().SetTitle(x_title)
    hist_2d.GetYaxis().SetTitle(y_title)
    hist_2d.GetXaxis().SetTitleSize(0.055)
    hist_2d.GetYaxis().SetTitleSize(0.055)
    hist_2d.GetXaxis().SetLabelSize(0.050)
    hist_2d.GetYaxis().SetLabelSize(0.050)
    hist_2d.GetZaxis().SetTitle("-2#Deltaln(L)")
    hist_2d.GetZaxis().SetTitleSize(0.055)
    hist_2d.GetZaxis().SetLabelSize(0.050)
    
    # Set up color palette for better visualization
    # Z-axis range: -1 to 5 in -2ΔlnL. Standard kBird palette, but the lowest
    # ~1/6 of the range (i.e. the negative-deltaNLL band) is overwritten to
    # bright green so grid cells where Migrad disagrees with the grid stand out.
    hist_2d.SetMinimum(-1)
    hist_2d.SetMaximum(5)
    import ROOT as _ROOT
    _ROOT.gStyle.SetPalette(_ROOT.kBird)
    _ROOT.gStyle.SetNumberContours(255)
    _palette = _ROOT.TColor.GetPalette()
    _n_pal = _palette.GetSize()
    _frac_neg = 1.0 / 6.0  # 0 sits at fraction 1/6 of the [-1, 5] range
    _n_neg = int(_n_pal * _frac_neg)
    _green_idx = _ROOT.TColor.GetColor(0, 255, 0)  # pure bright green
    for _i in range(_n_neg):
        _palette[_i] = _green_idx
    _ROOT.gStyle.SetPalette(_n_pal, _palette.GetArray())

    # Draw the 2D histogram with smoother color transitions
    hist_2d.Draw("COLZ")
    
    # Add contour lines for 1σ, 2σ, 3σ confidence levels for 2D
    # For 2D: 1σ = 2.30, 2σ = 6.18, 3σ = 11.83 (for -2ΔlnL)
    contour_levels = [2.30] #, 6.18]  # 68%, 95% confidence levels for 2D
    
    # Create a separate histogram for contours to avoid interference
    hist_contour = hist_2d.Clone("hist_contour")
    hist_contour.SetContour(len(contour_levels))
    for i, level in enumerate(contour_levels):
        hist_contour.SetContourLevel(i, level)
    
    # Draw smooth contour lines
    hist_contour.SetLineColor(kBlack)
    hist_contour.SetLineWidth(3)
    hist_contour.Draw("CONT3 SAME")
    
    # Overlay the actual scan points
    graph_points = ROOT.TGraph(len(poi1_vals), poi1_vals, poi2_vals)
    graph_points.SetMarkerStyle(20)
    graph_points.SetMarkerSize(0.3)
    graph_points.SetMarkerColor(kBlue)
    graph_points.Draw("P SAME")
    
    # Mark the best fit point
    best_fit_marker = ROOT.TMarker(best_poi1, best_poi2, 29)  # Large star
    best_fit_marker.SetMarkerColor(kRed)
    best_fit_marker.SetMarkerSize(2.0)
    best_fit_marker.Draw("SAME")
    
    # Add text with fit results
    latex = TLatex()
    latex.SetTextSize(0.04)
    latex.SetTextAlign(11)
    latex.SetNDC(True)
    
    text_x = 0.15
    text_y = 0.85
    line_height = 0.05
    
    # Region title
    if region in setup.get("regions", {}):
        region_title = setup["regions"][region]["title"]
    else:
        region_title = region
    latex.DrawLatex(text_x, text_y, f"Region: {region_title}")
    
    # Get asymmetric errors (fall back to symmetric if missing)
    poi1_err_down = scan_data.get('poi1_err_down', scan_data.get('poi1_err', 0.0))
    poi1_err_up   = scan_data.get('poi1_err_up',   scan_data.get('poi1_err', 0.0))
    poi2_err_down = scan_data.get('poi2_err_down', scan_data.get('poi2_err', 0.0))
    poi2_err_up   = scan_data.get('poi2_err_up',   scan_data.get('poi2_err', 0.0))

    # Display asymmetric errors in the text box
    latex.DrawLatex(text_x, text_y - line_height,
                   f"{x_title}: {best_poi1:.4f} -{poi1_err_down:.4f}/+{poi1_err_up:.4f}")
    latex.DrawLatex(text_x, text_y - 2*line_height,
                   f"{y_title}: {best_poi2:.4f} -{poi2_err_down:.4f}/+{poi2_err_up:.4f}")
    latex.DrawLatex(text_x, text_y - 3*line_height, 
                    f"Correlation: {scan_data['correlation']:.3f}")
    # latex.DrawLatex(text_x, text_y - 4*line_height, 
    #                 f"Scan points: {len(poi1_vals)}")
    
    # Draw asymmetric error bars around the best-fit point
    try:
        # horizontal (x) error bar at y = best_poi2
        if np.isfinite(poi1_err_down) and np.isfinite(poi1_err_up):
            line_x = TLine(best_poi1 - poi1_err_down, best_poi2, best_poi1 + poi1_err_up, best_poi2)
            line_x.SetLineColor(kRed); line_x.SetLineWidth(2); line_x.Draw("SAME") # Changed width 2 -> 3
            # caps
            # cap_dx = 0.02 * (poi1_max - poi1_min) # Changed size 0.01 -> 0.02
            # cap1 = TLine(best_poi1 - poi1_err_down, best_poi2 - cap_dx, best_poi1 - poi1_err_down, best_poi2 + cap_dx)
            # cap2 = TLine(best_poi1 + poi1_err_up,   best_poi2 - cap_dx, best_poi1 + poi1_err_up,   best_poi2 + cap_dx)
            # cap1.SetLineColor(kRed); cap1.SetLineWidth(3); cap1.Draw("SAME") # Changed width 2 -> 3
            # cap2.SetLineColor(kRed); cap2.SetLineWidth(3); cap2.Draw("SAME") # Changed width 2 -> 3

        # vertical (y) error bar at x = best_poi1
        if np.isfinite(poi2_err_down) and np.isfinite(poi2_err_up):
            line_y = TLine(best_poi1, best_poi2 - poi2_err_down, best_poi1, best_poi2 + poi2_err_up)
            line_y.SetLineColor(kRed); line_y.SetLineWidth(2); line_y.Draw("SAME") # Changed width 2 -> 3
            # caps
            # cap_dy = 0.02 * (poi2_max - poi2_min) # Changed size 0.01 -> 0.02
            # cap3 = TLine(best_poi1 - cap_dy, best_poi2 - poi2_err_down, best_poi1 + cap_dy, best_poi2 - poi2_err_down)
            # cap4 = TLine(best_poi1 - cap_dy, best_poi2 + poi2_err_up,   best_poi1 + cap_dy, best_poi2 + poi2_err_up)
            # cap3.SetLineColor(kRed); cap3.SetLineWidth(3); cap3.Draw("SAME") # Changed width 2 -> 3
            # cap4.SetLineColor(kRed); cap4.SetLineWidth(3); cap4.Draw("SAME") # Changed width 2 -> 3
    except Exception:
        pass
    
    # Add legend for contour lines and points
    legend = TLegend(0.15, 0.50, 0.50, 0.67)
    legend.SetFillStyle(0)
    legend.SetBorderSize(0)
    legend.SetTextSize(0.035)
    legend.AddEntry(best_fit_marker, "Best fit", "p")
    # legend.AddEntry(graph_points, "Scan points", "p")
    legend.AddEntry(hist_contour, "1#sigma CL contour", "l")
    legend.Draw()
    
    # CMS style
    CMSStyle.setCMSLumiStyle(canvas, 0)
    canvas.SetTicks(1, 1)
    canvas.Modified()
    canvas.Update()
    
    # Save the plot
    canvas.SaveAs(canvasname + ".png")
    canvas.SaveAs(canvasname + ".pdf")
    canvas.SaveAs(canvasname + ".root")
    
    print(f">>> Saved 2D scan plot: {canvasname}.png")
    
    canvas.Close()

def plot_measurement_summary(region_labels, measurements, **kwargs):
    """Create a summary plot showing measurements with error bars"""
    title = kwargs.get('title', "Measurements")
    ylabel = kwargs.get('ylabel', "value")
    outname = kwargs.get('outname', "measurements")
    year = kwargs.get('year', "2024")
    
    n_regions = len(region_labels)
    if n_regions == 0:
        print("No measurements to plot")
        return
    
    # Create canvas
    canvas_height = max(600, 60 + 40*n_regions)
    canvas_width = 800
    canvas = ROOT.TCanvas('canvas_summary', 'canvas_summary', 100, 100, canvas_width, canvas_height)
    canvas.SetFillColor(0)
    canvas.SetBorderMode(0)
    canvas.SetFrameFillStyle(0)
    canvas.SetFrameBorderMode(0)
    
    # Set margins
    top_margin = 0.08
    bottom_margin = 0.12
    left_margin = 0.25
    right_margin = 0.05
    
    canvas.SetTopMargin(top_margin)
    canvas.SetBottomMargin(bottom_margin) 
    canvas.SetLeftMargin(left_margin)
    canvas.SetRightMargin(right_margin)
    canvas.SetGrid(1, 0)
    canvas.cd()
    
    # Determine x-axis range
    values = [m[0] for m in measurements]
    errors_down = [m[1] for m in measurements] 
    errors_up = [m[2] for m in measurements]
    
    x_min = min([v - e for v, e in zip(values, errors_down)])
    x_max = max([v + e for v, e in zip(values, errors_up)])
    x_range = x_max - x_min
    x_margin = 0.15 * x_range
    x_min -= x_margin
    x_max += x_margin
    
    # Create frame
    frame = canvas.DrawFrame(x_min, 0.0, x_max, float(n_regions))
    frame.GetYaxis().SetLabelSize(0.0)
    frame.GetXaxis().SetLabelSize(0.042)
    frame.GetXaxis().SetTitleSize(0.050) 
    frame.GetXaxis().SetTitleOffset(1.1)
    frame.GetYaxis().SetNdivisions(n_regions, 0, 0, False)
    frame.GetXaxis().SetTitle(ylabel)
    frame.GetXaxis().SetNdivisions(510)
    
    # Create graph with error bars
    graph = ROOT.TGraphAsymmErrors(n_regions)
    
    for i, (region, measurement) in enumerate(zip(region_labels, measurements)):
        y_pos = n_regions - i - 0.5
        val, err_down, err_up = measurement
        graph.SetPoint(i, val, y_pos)
        graph.SetPointError(i, err_down, err_up, 0.2, 0.2) # Changed vertical cap size 0.1 -> 0.2
    
    # Style the graph
    graph.SetMarkerStyle(20)
    graph.SetMarkerSize(1.0)
    graph.SetMarkerColor(ROOT.kBlack)
    graph.SetLineColor(ROOT.kBlack)
    graph.SetLineWidth(2)
    
    # Draw the graph
    graph.Draw("PE SAME")
    
    # Add vertical line at 1.0 if appropriate
    if min(values) < 1.0 < max(values):
        line = ROOT.TLine(1.0, 0.0, 1.0, float(n_regions))
        line.SetLineStyle(2)
        line.SetLineColor(ROOT.kGray+2)
        line.Draw("SAME")
    
    # Add region labels
    latex = ROOT.TLatex()
    latex.SetTextSize(0.035)
    latex.SetTextFont(42)
    latex.SetTextAlign(32)
    latex.SetNDC(True)
    
    for i, region in enumerate(region_labels):
        y_pos_ndc = 1.0 - top_margin - (i + 0.5) * (1.0 - top_margin - bottom_margin) / n_regions
        latex.DrawLatex(left_margin - 0.02, y_pos_ndc, region)
    
    # Add CMS header
    cms_latex = ROOT.TLatex()
    cms_latex.SetTextSize(0.060)
    cms_latex.SetTextFont(61)
    cms_latex.SetTextAlign(11)
    cms_latex.SetNDC(True)
    cms_latex.DrawLatex(left_margin, 1.0 - top_margin + 0.01, "CMS")
    
    # Add "Internal" label
    internal_latex = ROOT.TLatex()
    internal_latex.SetTextSize(0.045)
    internal_latex.SetTextFont(52)
    internal_latex.SetTextAlign(11)
    internal_latex.SetNDC(True) 
    internal_latex.DrawLatex(left_margin + 0.12, 1.0 - top_margin + 0.01, "Internal")
    
    # Add year and energy
    year_latex = ROOT.TLatex()
    year_latex.SetTextSize(0.045)
    year_latex.SetTextFont(42)
    year_latex.SetTextAlign(31)
    year_latex.SetNDC(True)
    year_latex.DrawLatex(1.0 - right_margin, 1.0 - top_margin + 0.01, f"{year}, {CMSStyle.lumi_dict.get(year, 109):.0f} fb^{{-1}} ({CMSStyle.cme_dict.get(year, 13.6):.1f} TeV)")
    
    # Add title
    if title:
        title_latex = ROOT.TLatex()
        title_latex.SetTextSize(0.045)
        title_latex.SetTextFont(42)
        title_latex.SetTextAlign(11)
        title_latex.SetNDC(True)
        title_latex.DrawLatex(left_margin, 1.0 - top_margin - 0.05, title)
    
    canvas.SetTicks(1, 1)
    canvas.Modified()
    canvas.Update()
    
    # Save
    canvas.SaveAs(outname + ".png")
    canvas.SaveAs(outname + ".pdf") 
    canvas.SaveAs(outname + ".root")
    print(f">>> Saved measurement summary: {outname}.png")
    
    canvas.Close()

def plot_scan_correlations(scan_results_all_regions, **kwargs):
    """Create a correlation plot using correlations from scan results"""
    year = kwargs.get('year', '2024')
    indir = kwargs.get('indir', f"output_{year}")
    outdir = indir.replace('output', 'plots')
    tag = kwargs.get('tag', "")
    plottag = kwargs.get('plottag', "")
    outname = f"{outdir}/scan_correlations_multidimfit{tag}{plottag}"
    
    ensureDirectory(outdir)
    
    # Extract correlations and region names directly from scan results
    correlations = []
    region_labels = []
    
    # Sort regions
    sorted_regions = sorted(scan_results_all_regions.items(), key=lambda x: format_region_for_sorting(x[0]))
    
    for region, scan_data in sorted_regions:
        if scan_data is None:
            continue
        correlation = scan_data.get('correlation', 0.0)
        correlations.append(correlation)
        region_labels.append(format_region_label(region))
    
    n_regions = len(region_labels)
    if n_regions == 0:
        print("No correlation data to plot")
        return
    
    # Create canvas
    canvas_height = max(600, 60 + 40*n_regions)
    canvas_width = 800
    canvas = ROOT.TCanvas('canvas_scan_corr', 'canvas_scan_corr', 100, 100, canvas_width, canvas_height)
    canvas.SetFillColor(0)
    canvas.SetBorderMode(0)
    canvas.SetFrameFillStyle(0)
    canvas.SetFrameBorderMode(0)
    
    # Set margins
    top_margin = 0.08
    bottom_margin = 0.12
    left_margin = 0.25
    right_margin = 0.05
    
    canvas.SetTopMargin(top_margin)
    canvas.SetBottomMargin(bottom_margin) 
    canvas.SetLeftMargin(left_margin)
    canvas.SetRightMargin(right_margin)
    canvas.SetGrid(1, 0)
    canvas.cd()
    
    # Determine x-axis range for correlations (-1 to +1)
    x_min = -1.2
    x_max = 1.2
    
    # Create frame
    frame = canvas.DrawFrame(x_min, 0.0, x_max, float(n_regions))
    frame.GetYaxis().SetLabelSize(0.0)
    frame.GetXaxis().SetLabelSize(0.042)
    frame.GetXaxis().SetTitleSize(0.050) 
    frame.GetXaxis().SetTitleOffset(1.1)
    frame.GetYaxis().SetNdivisions(n_regions, 0, 0, False)
    frame.GetXaxis().SetTitle("TES-TauID Correlation from 2D Scans")
    frame.GetXaxis().SetNdivisions(510)
    
    # Create individual markers for each correlation
    markers = []
    
    for i, (region, correlation) in enumerate(zip(region_labels, correlations)):
        y_pos = n_regions - i - 0.5
        
        # Simple color scheme: blue for all correlations
        color = ROOT.kBlue + 2
        
        # Create marker
        marker = ROOT.TMarker(correlation, y_pos, 20)
        marker.SetMarkerSize(1.2)
        marker.SetMarkerColor(color)
        markers.append(marker)
        marker.Draw("SAME")
    
    # Add vertical line at 0.0 (no correlation)
    line_zero = ROOT.TLine(0.0, 0.0, 0.0, float(n_regions))
    line_zero.SetLineStyle(2)
    line_zero.SetLineColor(ROOT.kGray+2)
    line_zero.SetLineWidth(2)
    line_zero.Draw("SAME")
    
    # Add region labels
    latex = ROOT.TLatex()
    latex.SetTextSize(0.035)
    latex.SetTextFont(42)
    latex.SetTextAlign(32)
    latex.SetNDC(True)
    
    for i, region in enumerate(region_labels):
        y_pos_ndc = 1.0 - top_margin - (i + 0.5) * (1.0 - top_margin - bottom_margin) / n_regions
        latex.DrawLatex(left_margin - 0.02, y_pos_ndc, region)
    
    # Add correlation values next to points
    corr_latex = ROOT.TLatex()
    corr_latex.SetTextSize(0.030)
    corr_latex.SetTextFont(42)
    corr_latex.SetTextAlign(11)
    
    for i, correlation in enumerate(correlations):
        y_pos = n_regions - i - 0.5
        x_pos = correlation + 0.05 if correlation >= 0 else correlation - 0.05
        corr_latex.DrawLatex(x_pos, y_pos, f"{correlation:.3f}")
    
    # Add CMS header
    cms_latex = ROOT.TLatex()
    cms_latex.SetTextSize(0.060)
    cms_latex.SetTextFont(61)
    cms_latex.SetTextAlign(11)
    cms_latex.SetNDC(True)
    cms_latex.DrawLatex(left_margin, 1.0 - top_margin + 0.01, "CMS")
    
    # Add "Internal" label
    internal_latex = ROOT.TLatex()
    internal_latex.SetTextSize(0.045)
    internal_latex.SetTextFont(52)
    internal_latex.SetTextAlign(11)
    internal_latex.SetNDC(True) 
    internal_latex.DrawLatex(left_margin + 0.12, 1.0 - top_margin + 0.01, "Internal")
    
    # Add year and energy
    year_latex = ROOT.TLatex()
    year_latex.SetTextSize(0.045)
    year_latex.SetTextFont(42)
    year_latex.SetTextAlign(31)
    year_latex.SetNDC(True)
    year_latex.DrawLatex(1.0 - right_margin, 1.0 - top_margin + 0.01, f"{year}, {CMSStyle.lumi_dict.get(year, 109):.0f} fb^{{-1}} ({CMSStyle.cme_dict.get(year, 13.6):.1f} TeV)")
    
    # Add title
    title_latex = ROOT.TLatex()
    title_latex.SetTextSize(0.045)
    title_latex.SetTextFont(42)
    title_latex.SetTextAlign(11)
    title_latex.SetNDC(True)
    title_latex.DrawLatex(left_margin, 1.0 - top_margin - 0.05, "TES-TauID Correlations from MultiDimFit Scans")
    
    canvas.SetTicks(1, 1)
    canvas.Modified()
    canvas.Update()
    
    # Save
    canvas.SaveAs(outname + ".png")
    canvas.SaveAs(outname + ".pdf") 
    canvas.SaveAs(outname + ".root")
    print(f">>> Saved scan correlation plot: {outname}.png")
    
    canvas.Close()


def write_2d_fit_results(poi1_name, poi2_name, poi1_val, poi1_err_down, poi1_err_up, 
                         poi2_val, poi2_err_down, poi2_err_up, correlation, region, **kwargs):
    """Write 2D fit results to text file"""
    year = kwargs.get('year', '2024')
    tag = kwargs.get('tag', '')
    channel = kwargs.get('channel', 'mt')
    outdir = kwargs.get('outdir', 'plots')
    
    ensureDirectory(outdir)
    
    outfname = f"{outdir}/measurement_2D_{poi1_name}_{poi2_name}_{channel}_{region}{tag}.txt"
    
    print(f">>> Writing 2D fit results to {outfname}")
    
    # Calculate absolute limits
    poi1_low = poi1_val - poi1_err_down
    poi1_high = poi1_val + poi1_err_up
    poi2_low = poi2_val - poi2_err_down
    poi2_high = poi2_val + poi2_err_up
    
    with open(outfname, 'w') as file:
        file.write("# 2D Fit Results from MultiDimFit\n")
        file.write(f"# Region: {region}\n")
        file.write(f"# Year: {year}\n")
        file.write(f"# Channel: {channel}\n")
        file.write("# Format: parameter value error_down error_up\n")
        file.write(f"{poi1_name} {poi1_val:.6f} {poi1_err_down:.6f} {poi1_err_up:.6f}\n")
        file.write(f"{poi2_name} {poi2_val:.6f} {poi2_err_down:.6f} {poi2_err_up:.6f}\n")
        file.write(f"correlation {correlation:.6f}\n")
        # Add absolute limits as requested
        file.write(f"# Absolute 1-sigma limits:\n")
        file.write(f"{poi1_name}_1sigma_low: {poi1_low:.6f}\n")
        file.write(f"{poi1_name}_1sigma_high: {poi1_high:.6f}\n")
        file.write(f"{poi2_name}_1sigma_low: {poi2_low:.6f}\n")
        file.write(f"{poi2_name}_1sigma_high: {poi2_high:.6f}\n")
    
    return outfname

def main(args):
    """Main function - handle multiple regions and create summary plots"""
    
    print("Using configuration file: %s" % args.config)
    with open(args.config, 'r') as file:
        setup = yaml.safe_load(file)
    
    channel = setup["channel"].replace("mu", "m").replace("tau", "t")
    tag = setup.get("tag", "")
    era = args.year
    extratag = "_DeepTau"
    
    # Input directory
    if args.indir:
        if not args.indir.rstrip('/').endswith(str(era)):
            indir = os.path.join(args.indir, str(era))
        else:
            indir = args.indir
    else:
        indir = f"output_{era}"
    
    # Process regions
    scan_results_all_regions = {}
    
    if args.poi1 and args.poi2:
        # Single region mode
        poi1_name = args.poi1  # e.g., "tes_DM0" (corrTES) or "tes_DM0_pt1" (uncorr)
        poi2_name = args.poi2  # e.g., "tid_SF_DM0_pt1"

        # Region: prefer explicit -r (correct for corrTES where tes_<DM> has no pT),
        # else derive from poi1.
        if args.region:
            region = args.region
        elif '_' in poi1_name:
            region = poi1_name.split('_', 1)[1]
        else:
            region = "DM0"

        regions_to_process = [region]
    else:
        # Multiple regions mode - get from config
        try:
            regions_to_process = setup["observables"]["m_vis"]["scanRegions"]
            print(f">>> Processing {len(regions_to_process)} regions from config: {regions_to_process}")
        except KeyError:
            print("ERROR: No regions found in config file. Please specify --poi1 and --poi2 for single region mode.")
            sys.exit(1)
    
    # Process each region
    for region in regions_to_process:
        print(f"\n>>> Processing region: {region}")
        
        # Construct POI names if not provided
        if not args.poi1 or not args.poi2:
            poi1_name = f"tes_{region}"
            poi2_name = f"tid_SF_{region}"
        else:
            poi1_name = args.poi1
            poi2_name = args.poi2
        
        # Construct MultiDimFit filename
        multidimfit_filename = f"{indir}/higgsCombine.{channel}_m_vis-{region}{tag}{extratag}-{era}-13TeV.MultiDimFit.mH90.root"
        
        if not os.path.exists(multidimfit_filename):
            # Try alternative naming
            multidimfit_filename = f"{indir}/higgsCombine.mt_m_vis-{region}{tag}{extratag}-{era}-13TeV.MultiDimFit.mH90.root"
            if not os.path.exists(multidimfit_filename):
                print(f"WARNING: MultiDimFit file not found for {region}")
                scan_results_all_regions[region] = None
                continue
        
        print(f">>> Using: {multidimfit_filename}")
        
        # Extract scan data
        scan_data = extract_2d_scan_data(multidimfit_filename, poi1_name, poi2_name)
        if scan_data is None:
            print(f"ERROR: Could not extract scan data for {region}")
            scan_results_all_regions[region] = None
            continue
            
        scan_results_all_regions[region] = scan_data
        
        # Create individual 2D plot
        plot_2d_scan(setup, region, era, scan_data, 
                     indir=indir, tag=tag, plottag=args.plottag)
        
        # Write individual text results for this region (use asymmetric errors if available)
        outdir = indir.replace('output', 'plots')
        poi1_val = scan_data['best_poi1']
        poi2_val = scan_data['best_poi2']
        correlation = scan_data.get('correlation', 0.0)

        # Use asymmetric errors if present in scan_data, fall back to symmetric stored values
        poi1_err_down = scan_data.get('poi1_err_down', scan_data.get('poi1_err', 0.0))
        poi1_err_up   = scan_data.get('poi1_err_up',   scan_data.get('poi1_err', 0.0))
        poi2_err_down = scan_data.get('poi2_err_down', scan_data.get('poi2_err', 0.0))
        poi2_err_up   = scan_data.get('poi2_err_up',   scan_data.get('poi2_err', 0.0))

        # Write individual region results with asymmetric errors
        write_2d_fit_results(
            poi1_name, poi2_name,
            poi1_val, poi1_err_down, poi1_err_up,
            poi2_val, poi2_err_down, poi2_err_up,
            correlation, region,
            year=era, tag=tag, channel=channel, outdir=outdir
        )
    
    # Create summary plots and text files if we have multiple regions


if __name__ == '__main__':
    description = '''Plot 2D parabolas from MultiDimFit scan output.'''
    parser = ArgumentParser(prog="plot2DScan_MultiDimFit", 
                          description=description, epilog="Success!")
    
    parser.add_argument('-y', '--year', dest='year', 
                       choices=['2024', '2016', '2017', '2018', 'UL2016_preVFP', 
                               'UL2016_postVFP', 'UL2017', 'UL2018', 'UL2018_v10',
                               '2022_postEE', '2022_preEE', '2023C', '2023D', '2025', '2026', '2526'],
                       type=str, default='2024', action='store', 
                       help="select year")
    
    parser.add_argument('-c', '--config', dest='config', type=str, 
                       default='TauES_ID/config/config_coarse_TT.yml', 
                       action='store', 
                       help="set config file containing sample & fit setup")
    
    parser.add_argument('--poi1', dest='poi1', type=str, required=False,
                       help="first parameter of interest (e.g., tes_DM0). If not provided, will process all regions from config.")
    
    parser.add_argument('--poi2', dest='poi2', type=str, required=False,
                       help="second parameter of interest (e.g., tid_SF_DM0). If not provided, will process all regions from config.")
    
    parser.add_argument('-r', '--region', dest='region', type=str,
                       help="region name (if not extractable from POI names)")
    
    parser.add_argument('-i', '--indir', dest='indir', type=str, 
                       help='input directory')
    
    parser.add_argument('-t', '--plottag', dest='plottag', type=str, 
                       default="", help='extra tag for plot filename')
    
    parser.add_argument('-v', '--verbose', dest='verbose', 
                       default=False, action='store_true', help="set verbose")
    
    args = parser.parse_args()
    main(args)










