#!/usr/bin/env python
"""
Date : Sept 202
Author : @haawedik based on plotParabola_POI_region.py by @oponcet
Description :
This script plots 2D parabolas from FitDiagnostics output files.
It extracts the correlation matrix and covariance information to create
2D likelihood contours for two parameters of interest (e.g., TES and tid_SF).
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
from TauFW.Plotter.sample.utils import CMSStyle

# Ensure ROOT runs in batch mode
gROOT.SetBatch(True)
gStyle.SetOptTitle(0)

# CMS style
CMSStyle.setTDRStyle()

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

def calculate_correlation_and_uncertainties(poi1_vals, poi2_vals, nll_vals):
    """Calculate correlation and proper uncertainties from scan data"""
    poi1_vals = np.array(poi1_vals)
    poi2_vals = np.array(poi2_vals)
    nll_vals = np.array(nll_vals)
    
    print(f">>> Debug correlation calculation:")
    print(f"    Total scan points: {len(poi1_vals)}")
    print(f"    POI1 range: [{np.min(poi1_vals):.4f}, {np.max(poi1_vals):.4f}]")
    print(f"    POI2 range: [{np.min(poi2_vals):.4f}, {np.max(poi2_vals):.4f}]")
    print(f"    NLL range: [{np.min(nll_vals):.4f}, {np.max(nll_vals):.4f}]")
    
    # Calculate raw correlation with all points first
    if len(np.unique(poi1_vals)) > 1 and len(np.unique(poi2_vals)) > 1:
        raw_correlation = np.corrcoef(poi1_vals, poi2_vals)[0, 1]
        print(f"    Raw correlation (all points): {raw_correlation:.4f}")
    else:
        raw_correlation = 0.0
        print("    Cannot calculate correlation: insufficient variation in parameters")
    
    # Find minimum NLL point
    min_idx = np.argmin(nll_vals)
    best_poi1 = poi1_vals[min_idx]
    best_poi2 = poi2_vals[min_idx]
    
    # Try different NLL thresholds for filtering
    for threshold in [20.0, 10.0, 5.0, 3.0]:
        mask = nll_vals < threshold
        filtered_poi1 = poi1_vals[mask]
        filtered_poi2 = poi2_vals[mask]
        
        print(f"    Points with deltaNLL < {threshold}: {np.sum(mask)}")
        
        if len(filtered_poi1) >= 10:
            if len(np.unique(filtered_poi1)) > 1 and len(np.unique(filtered_poi2)) > 1:
                correlation = np.corrcoef(filtered_poi1, filtered_poi2)[0, 1]
                print(f"    Filtered correlation (deltaNLL < {threshold}): {correlation:.4f}")
                break
    else:
        # Use raw correlation if filtering doesn't work
        correlation = raw_correlation
        print(f"    Using raw correlation: {correlation:.4f}")
    
    # Calculate uncertainties using likelihood weighting
    weights = np.exp(-nll_vals)
    weights = weights / np.sum(weights)
    
    poi1_mean = np.sum(weights * poi1_vals)
    poi2_mean = np.sum(weights * poi2_vals)
    
    poi1_err = np.sqrt(np.sum(weights * (poi1_vals - poi1_mean)**2))
    poi2_err = np.sqrt(np.sum(weights * (poi2_vals - poi2_mean)**2))
    
    print(f"    Final correlation: {correlation:.4f}")
    print(f"    Uncertainties: {poi1_err:.4f}, {poi2_err:.4f}")
    
    return correlation, poi1_err, poi2_err

def interpolate_scan_data(poi1_vals, poi2_vals, nll_vals, nbins=100):
    """Create a smoother 2D histogram by interpolating the scan data"""
    try:
        from scipy.interpolate import griddata
        from scipy.ndimage import gaussian_filter
    except ImportError:
        raise ImportError("scipy is required for interpolation")
    
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
    
    # First try cubic interpolation
    try:
        nll_interpolated = griddata(points, nll_vals, (poi1_mesh, poi2_mesh), 
                                   method='cubic', fill_value=np.nan)
        # Fill NaN values with linear interpolation
        mask = np.isnan(nll_interpolated)
        if np.any(mask):
            nll_linear = griddata(points, nll_vals, (poi1_mesh, poi2_mesh), 
                                method='linear', fill_value=np.max(nll_vals))
            nll_interpolated[mask] = nll_linear[mask]
    except:
        # Fallback to linear interpolation
        nll_interpolated = griddata(points, nll_vals, (poi1_mesh, poi2_mesh), 
                                   method='linear', fill_value=np.max(nll_vals))
    
    # Apply Gaussian smoothing for even smoother contours
    nll_interpolated = gaussian_filter(nll_interpolated, sigma=1.0)
    
    return poi1_grid, poi2_grid, nll_interpolated

def get_fit_results(multidimfit_file, poi1_name, poi2_name):
    """
    Extract fit results from MultiDimFit output file.
    Returns best fit values, uncertainties, and correlation coefficient.
    """
    print(f">>> Reading fit results from {multidimfit_file}")
    
    file = ensureTFile(multidimfit_file)
    
    # Get the limit tree (MultiDimFit output)
    tree = file.Get("limit")
    if not tree:
        print("ERROR: Could not find limit tree in MultiDimFit file")
        file.Close()
        return None
    
    print(f">>> Found {tree.GetEntries()} entries in limit tree")
    
    # Arrays to collect scan points
    poi1_vals = []
    poi2_vals = []
    nll_vals = []
    
    # Read all scan points
    for i in range(tree.GetEntries()):
        tree.GetEntry(i)
        
        # Check if the required branches exist
        if not (hasattr(tree, poi1_name) and hasattr(tree, poi2_name) and hasattr(tree, 'deltaNLL')):
            if i == 0:  # Only print error once
                print(f"ERROR: Could not find parameters {poi1_name}, {poi2_name}, or deltaNLL in tree")
                print("Available branches:")
                for branch in tree.GetListOfBranches():
                    print(f"  {branch.GetName()}")
                file.Close()
                return None
        
        poi1_val = getattr(tree, poi1_name)
        poi2_val = getattr(tree, poi2_name)
        delta_nll = getattr(tree, 'deltaNLL')
        
        poi1_vals.append(poi1_val)
        poi2_vals.append(poi2_val)
        nll_vals.append(delta_nll)
    
    # Find the best fit point (minimum deltaNLL)
    min_idx = nll_vals.index(min(nll_vals))
    best_poi1 = poi1_vals[min_idx]
    best_poi2 = poi2_vals[min_idx]
    min_nll = nll_vals[min_idx]
    
    print(f">>> Best fit point: {poi1_name} = {best_poi1}, {poi2_name} = {best_poi2}")
    print(f">>> Minimum deltaNLL = {min_nll}")
    
    # Calculate proper correlation and uncertainties from scan data
    correlation, poi1_err, poi2_err = calculate_correlation_and_uncertainties(
        poi1_vals, poi2_vals, nll_vals)
    
    print(f">>> Scan statistics:")
    print(f"    Total scan points: {len(poi1_vals)}")
    print(f"    {poi1_name} range: [{min(poi1_vals):.4f}, {max(poi1_vals):.4f}]")
    print(f"    {poi2_name} range: [{min(poi2_vals):.4f}, {max(poi2_vals):.4f}]")
    print(f"    NLL range: [{min(nll_vals):.4f}, {max(nll_vals):.4f}]")
    print(f">>> Calculated correlation: {correlation:.4f}")
    print(f">>> {poi1_name} = {best_poi1:.4f} ± {poi1_err:.4f}")
    print(f">>> {poi2_name} = {best_poi2:.4f} ± {poi2_err:.4f}")
    
    file.Close()
    
    return {
        'poi1_name': poi1_name,
        'poi2_name': poi2_name,
        'poi1_val': best_poi1,
        'poi2_val': best_poi2,
        'poi1_err': poi1_err,
        'poi2_err': poi2_err,
        'correlation': correlation,
        'scan_data': {
            'poi1_vals': poi1_vals,
            'poi2_vals': poi2_vals,
            'nll_vals': nll_vals
        }
    }

def create_2d_nll_function(fit_results):
    """
    Create a 2D NLL function based on fit results.
    This assumes a bivariate Gaussian likelihood.
    """
    poi1_val = fit_results['poi1_val']
    poi2_val = fit_results['poi2_val']
    poi1_err = fit_results['poi1_err']
    poi2_err = fit_results['poi2_err']
    rho = fit_results['correlation']
    
    # Define the 2D NLL function
    # NLL = 0.5 * [(x-mu1)^2/sigma1^2 + (y-mu2)^2/sigma2^2 - 2*rho*(x-mu1)*(y-mu2)/(sigma1*sigma2)] / (1-rho^2)
    def nll_2d(x, par):
        x1 = x[0]  # first parameter (e.g., TES)
        x2 = x[1]  # second parameter (e.g., tid_SF)
        
        dx1 = (x1 - poi1_val) / poi1_err
        dx2 = (x2 - poi2_val) / poi2_err
        
        if abs(rho) < 0.999:  # avoid division by zero
            discriminant = 1.0 - rho * rho
            nll = 0.5 * (dx1*dx1 + dx2*dx2 - 2*rho*dx1*dx2) / discriminant
        else:
            nll = 0.5 * (dx1*dx1 + dx2*dx2)
        
        return nll
    
    return nll_2d

def plot_2d_parabola(setup, region, year, fit_results, **kwargs):
    """
    Plot 2D parabola (likelihood contours) for two parameters using actual scan data.
    """
    print(f">>> Plotting 2D parabola for {region}")
    
    indir = kwargs.get('indir', f"output_{year}")
    outdir = indir.replace('output', 'plots')
    tag = kwargs.get('tag', "")
    plottag = kwargs.get('plottag', "")
    poi1_name = fit_results['poi1_name']
    poi2_name = fit_results['poi2_name']
    era = f"{year}-13TeV"
    channel = setup["channel"].replace("mu", "m").replace("tau", "t")
    
    ensureDirectory(outdir)
    
    # Canvas name
    canvasname = f"{outdir}/parabola_2D_{poi1_name}_{poi2_name}_{channel}_{region}{tag}{plottag}"
    
    # Extract scan data
    scan_data = fit_results['scan_data']
    poi1_vals = np.array(scan_data['poi1_vals'])
    poi2_vals = np.array(scan_data['poi2_vals'])
    nll_vals = np.array(scan_data['nll_vals'])
    
    # Set up ranges for plotting based on actual scan data
    poi1_min, poi1_max = np.min(poi1_vals), np.max(poi1_vals)
    poi2_min, poi2_max = np.min(poi2_vals), np.max(poi2_vals)
    
    # Add some padding to the ranges
    poi1_range = poi1_max - poi1_min
    poi2_range = poi2_max - poi2_min
    padding = 0.1  # 10% padding
    x1_min = poi1_min - padding * poi1_range
    x1_max = poi1_max + padding * poi1_range
    x2_min = poi2_min - padding * poi2_range
    x2_max = poi2_max + padding * poi2_range
    
    # Create 2D histogram for contour plotting using actual scan data
    nbins = 100  # Higher resolution for smoother contours
    hist_2d = TH2D("hist_2d", "", nbins, x1_min, x1_max, nbins, x2_min, x2_max)
    
    # Always try interpolation for smoother results
    use_interpolation = True
    
    try:
        # Try to use scipy interpolation for smoother results
        poi1_grid, poi2_grid, nll_interpolated = interpolate_scan_data(
            poi1_vals, poi2_vals, nll_vals, nbins)
        
        # Fill histogram with interpolated data
        for i in range(nbins):
            for j in range(nbins):
                hist_2d.SetBinContent(i+1, j+1, 2 * nll_interpolated[j, i])  # Factor of 2 for -2ΔlnL
        print(">>> Using interpolated scan data for smoother plot")
        
    except (ImportError, Exception) as e:
        print(f">>> Interpolation failed ({e}), using direct binning with heavy smoothing")
        use_interpolation = False
        
        # Fill histogram with actual scan data (direct binning)
        for i, (p1, p2, nll) in enumerate(zip(poi1_vals, poi2_vals, nll_vals)):
            bin_x = hist_2d.GetXaxis().FindBin(p1)
            bin_y = hist_2d.GetYaxis().FindBin(p2)
            # Use the minimum NLL value if multiple points fall in the same bin
            current_val = hist_2d.GetBinContent(bin_x, bin_y)
            if current_val == 0 or 2 * nll < current_val:
                hist_2d.SetBinContent(bin_x, bin_y, 2 * nll)  # Factor of 2 for -2ΔlnL
        
        # Apply heavy smoothing to get rid of the grid pattern
        for _ in range(5):  # Multiple smoothing iterations
            hist_2d.Smooth(1)
    
    # Get fit parameters for plotting
    poi1_val = fit_results['poi1_val']
    poi2_val = fit_results['poi2_val']
    poi1_err = fit_results['poi1_err']
    poi2_err = fit_results['poi2_err']
    
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
    hist_2d.SetMinimum(0)
    max_val = hist_2d.GetMaximum()
    if max_val > 20:
        hist_2d.SetMaximum(20)  # Cap the maximum for better color scale
    
    # Draw the 2D histogram with smoother color transitions
    hist_2d.Draw("COLZ")
    
    # Add contour lines for 1σ, 2σ, 3σ confidence levels for 2D
    # For 2D: 1σ = 2.30, 2σ = 6.18, 3σ = 11.83 (for -2ΔlnL)
    contour_levels = [2.30, 6.18, 11.83]  # 68%, 95%, 99.73% confidence levels for 2D
    
    # Create a separate histogram for contours to avoid interference
    hist_contour = hist_2d.Clone("hist_contour")
    hist_contour.SetContour(len(contour_levels))
    for i, level in enumerate(contour_levels):
        hist_contour.SetContourLevel(i, level)
    
    # Draw smooth contour lines
    hist_contour.SetLineColor(kBlack)
    hist_contour.SetLineWidth(3)
    hist_contour.Draw("CONT3 SAME")
    
    # Mark the best fit point
    best_fit_marker = ROOT.TMarker(poi1_val, poi2_val, 20)
    best_fit_marker.SetMarkerColor(kRed)
    best_fit_marker.SetMarkerSize(1.5)
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
    
    # Best fit values
    latex.DrawLatex(text_x, text_y - line_height, 
                   f"{x_title}: {poi1_val:.4f} #pm {poi1_err:.4f}")
    latex.DrawLatex(text_x, text_y - 2*line_height, 
                   f"{y_title}: {poi2_val:.4f} #pm {poi2_err:.4f}")
    latex.DrawLatex(text_x, text_y - 3*line_height, 
                   f"Correlation: {fit_results['correlation']:.3f}")
    
    # Add legend for contour lines
    legend = TLegend(0.15, 0.60, 0.45, 0.75)
    legend.SetFillStyle(0)
    legend.SetBorderSize(0)
    legend.SetTextSize(0.035)
    legend.AddEntry(best_fit_marker, "Best fit", "p")
    legend.AddEntry(hist_contour, "68%, 95%, 99.7% CL", "l")
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
    
    print(f">>> Saved 2D parabola plot: {canvasname}.png")
    
    canvas.Close()

def main(args):
    """Main function"""
    
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
    
    # POI names
    poi1_name = args.poi1  # e.g., "tes_DM0"
    poi2_name = args.poi2  # e.g., "tid_SF_DM0"
    
    # Extract region from POI name (assuming format like "tes_DM0")
    if '_' in poi1_name:
        region = poi1_name.split('_', 1)[1]
    else:
        region = args.region if args.region else "DM0"
    
    # Construct fitDiagnostics filename
    # This should match what your makecombinedfitTES_SF_postfit.py produces
    fitdiag_filename = f"{indir}/higgsCombine.mt_m_vis-{region}{tag}{extratag}-{era}-13TeV.MultiDimFit.mH90.root" #f"{indir}/fitDiagnostics.mt_m_vis-{region}{tag}{extratag}-{era}-13TeV.root"
    
    if not os.path.exists(fitdiag_filename):
        print(f"ERROR: FitDiagnostics file not found: {fitdiag_filename}")
        # Try alternative naming
        fitdiag_filename = f"{indir}/fitDiagnostics.{channel}_m_vis-{region}{tag}{extratag}-{era}-13TeV.root"
        if not os.path.exists(fitdiag_filename):
            print(f"ERROR: Alternative FitDiagnostics file not found: {fitdiag_filename}")
            sys.exit(1)
    
    print(f">>> Using FitDiagnostics file: {fitdiag_filename}")
    
    # Extract fit results
    fit_results = get_fit_results(fitdiag_filename, poi1_name, poi2_name)
    if fit_results is None:
        print("ERROR: Could not extract fit results")
        sys.exit(1)
    
    # Create 2D plot
    plot_2d_parabola(setup, region, era, fit_results, 
                     indir=indir, tag=tag, plottag=args.plottag)

if __name__ == '__main__':
    description = '''Plot 2D parabolas from FitDiagnostics output.'''
    parser = ArgumentParser(prog="plot2DParabola_FitDiagnostics", 
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
    
    parser.add_argument('--poi1', dest='poi1', type=str, required=True,
                       help="first parameter of interest (e.g., tes_DM0)")
    
    parser.add_argument('--poi2', dest='poi2', type=str, required=True,
                       help="second parameter of interest (e.g., tid_SF_DM0)")
    
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