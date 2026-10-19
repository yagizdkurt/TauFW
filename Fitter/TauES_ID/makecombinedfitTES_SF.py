#! /usr/bin/env python
"""
Date : July 2023 
Author : @oponcet 
Description :
 - Scan of tes and tid SF is implemented as a rateParamer wich is profiled. Ex usage : Scan by DM (option 1)
 - Scan of tid SF and tes need to be set as POI with redefineSignalPOIs to include it in the fit. Ex usage : Scan by DM (option 2) 
 - 2D scan of tes and tid SF. Ex usage : Scan by DM (option 3)
 - Scan of tid SF, tid SF and tes of other regions are profiled POIs. Ex usage : Fit tes by DM and tid SF by pt (option 4)
 - Scan of tes, tid SF and tes of other regions are profiled POIs. Ex usage : Fit tes by DM and tid SF by pt (option 5)
 - 2D scan of tes and tid SF and tes of other regions are profiled POIs. Ex usage : Fit tes by DM and tid SF by pt (option 6) 
"""

from distutils import filelist
from distutils.command.config import config
import sys
import os
import yaml
from argparse import ArgumentParser


def find_boost_params(fit_result_file, poi1_name, poi2_name, threshold=0):
    """If pass-1's MultiDimFit tree has min(deltaNLL) below `threshold`
    (i.e. a grid scan point sits in a deeper basin than combine's initial
    free-POI fit converged to), return a `--setParameters` string built from
    that entry's POI values (POIs only, nuisances left at defaults).
    Otherwise return None. Used to seed a pass-2 scan that escapes the local minimum."""
    import ROOT
    if not os.path.exists(fit_result_file):
        return None
    f = ROOT.TFile.Open(fit_result_file)
    if not f or f.IsZombie():
        return None
    tree = f.Get("limit")
    if not tree:
        f.Close()
        return None
    nentries = int(tree.GetEntries())
    if nentries == 0:
        f.Close()
        return None

    best_idx, best_nll = -1, float("inf")
    for i in range(nentries):
        tree.GetEntry(i)
        v = float(tree.deltaNLL)
        if v < best_nll:
            best_nll = v
            best_idx = i

    if best_nll >= threshold:
        print(f"[BOOST] Pass-1 min(deltaNLL)={best_nll:.6f} >= {threshold} — no boost needed")
        f.Close()
        return None

    tree.GetEntry(best_idx)
    parts = []
    for b in (poi1_name, poi2_name):
        try:
            parts.append("%s=%.6g" % (b, float(getattr(tree, b))))
        except Exception:
            pass
    # Also seed nuisances from the deepest grid entry — pass-1 saved them via
    # --saveSpecifiedNuis all. Without this, pass-2 starts at the right POI
    # corner but with all nuisances at datacard defaults, and in low-stats
    # bins it drifts straight back into the local basin pass-1 was stuck in.
    skip = {"deltaNLL", "quantileExpected", "iToy", "limit", "limitErr",
            "mh", "syst", "iSeed", "t_cpu", "t_real", "r",
            poi1_name, poi2_name}
    n_nuis = 0
    for b in tree.GetListOfBranches():
        bname = b.GetName()
        if bname in skip: continue
        try:
            v = float(getattr(tree, bname))
        except Exception:
            continue
        if abs(v) > 1e3: continue
        parts.append("%s=%.6g" % (bname, v))
        n_nuis += 1
    f.Close()
    print(f"[BOOST] Pass-1 deepest point: deltaNLL={best_nll:.6f} at entry {best_idx} (POIs + {n_nuis} nuisances seeded)")
    return ",".join(parts) if parts else None

# Generating the datacards for mutau channel
def generate_datacards_mutau(era, config, extratag,input_dir,output_dir=None):
    print(' >>>>>> Generating datacards for mutau channel')
    # BUGS F04: an `input_file` lookup in locals()/globals() was removed here; it never found a value (and
    # harvestDatacards_TES_idSF_MCStat.py has no --input_file option), so the datacards always came from input_dir
    # BUGS F15: the script is found next to this one, not relative to the working directory
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "harvestDatacards_TES_idSF_MCStat.py")
    outopt = " --output_dir %s"%(output_dir) if output_dir else "" # else the cards go next to the input tree
    os.system("python3 %s -y %s -c %s -e %s -i %s%s" % (script, era, config, extratag, input_dir, outopt))

# Generating the datacards for mumu channel
def generate_datacards_mumu(era, config_mumu, extratag, output_dir):
    print(' >>>>>> Generating datacards for mumu channel')
    os.system("python3 TauES_ID/harvestDatacards_zmm.py -y %s -c %s -e %s -o %s"%(era,config_mumu,extratag,output_dir)) # Generating the datacards with one statistics uncertianties for all processes

# Merge the datacards between regions for combine fit and return the name of the combined datacard file
def merge_datacards_regions(setup, setup_mumu, config_mumu, era, extratag, output_dir):
    # Variable of the fit (usually mvis)
    variable = "m_vis"
    print("Observable : "+variable)
    # LABEL used for datacard file
    LABEL = setup["tag"]+extratag+"-"+era+"-13TeV"
    filelist = "" # List of the datacard files to merge in one file combinecards.txt
    # Name of the combined datacard file
    outcombinedfile = "combinecards%s" %(setup["tag"])
    for region in setup["observables"]["m_vis"]["fitRegions"]:
        card_path = os.path.join(output_dir, f"ztt_mt_m_vis-{region}{LABEL}.txt")
        if not os.path.isfile(card_path):
            print(f"ERROR: Missing datacard {card_path}")
        filelist += f"{region}={card_path} "
    # Only merge once, after collecting all regions
    os.system(f"combineCards.py {filelist} >{output_dir}/{outcombinedfile}.txt")
    #print("filelist : %s") %(filelist) 
    # Add the CR datacard file to the lsit of file to merge if there is CR option
    # If mumu_datacard_file is provided, use it directly
    if hasattr(setup, 'mumu_datacard_file') and setup.get('mumu_datacard_file'):
        filelist += f"zmm={setup.get('mumu_datacard_file')} "
        outcombinedfile += "CR"
        print(100*'-')
        print(100*'-')
        print(100*'-')
        print(100*'-')
        
        print(100*'-')
        print(100*'-')
        print(100*'-')
        print(100*'-')
        os.system(f"combineCards.py {filelist} >output_{era}/{outcombinedfile}.txt")
        print(">>>>>>>>> merging datacards is done ")
    # Otherwise, use the old logic (commented out)
    # if str(config_mumu) != 'None':
    #     LABEL_mumu = setup_mumu["tag"]+extratag+"-"+era+"-13TeV"
    #     filelist +=  "zmm=output_"+era+"/ztt_mm_m_vis-baseline"+LABEL_mumu+".txt "
    #     outcombinedfile += "CR"
    #     os.system("combineCards.py %s >output_%s/%s.txt" % (filelist, era,outcombinedfile))
    #     print(">>>>>>>>> merging datacards is done ")
    return outcombinedfile



# Merge the datacards between mt regions and Zmm when using Zmm CR and return the name of the CR + region datacard file
def merge_datacards_ZmmCR(setup, setup_mumu, era,extratag,region, output_dir, mumu_input_file=None):
    # datacard of the region to be merged
    datacardfile_region = "ztt_mt_m_vis-"+region+setup["tag"]+extratag+"-"+era+"-13TeV.txt"
    filelist = f"%s={output_dir}/%s" %(region, datacardfile_region)
    # LABEL_mumu = setup_mumu["tag"]+extratag+"-"+era+"-13TeV"
    # filelist += " Zmm="+output_dir+"/ztt_mm_m_vis-baseline"+LABEL_mumu+".txt "

    if mumu_input_file:
        filelist += f" Zmm={mumu_input_file} "
    else:
        LABEL_mumu = setup_mumu["tag"]+"-"+era+"-13TeV"
        filelist += " Zmm="+output_dir+"/ztt_mm_m_vis-baseline"+LABEL_mumu+".txt "
    
    print(filelist)
    # Name of the CR + region datacard file
    outCRfile = "ztt_mt_m_vis-%s_zmmCR" %(region)
    os.system(f"combineCards.py %s >{output_dir}/%s.txt" % (filelist, outCRfile))
    return outCRfile
    
def run_combined_fit(setup, setup_mumu, option, **kwargs):
    # tes_range    = kwargs.get('tes_range',    "0.950,1.050")
    tes_range    = kwargs.get('tes_range',    "%s,%s" %(min(setup["TESvariations"]["values"]), max(setup["TESvariations"]["values"]))                         )
    tid_SF_range = kwargs.get('tid_SF_range', "0.5,1.2")
    extratag     = kwargs.get('extratag',     "_DeepTau")
    algo         = kwargs.get('algo',         "--algo=grid") #--alignEdges=1 grid --fastScan
    npts_fit     = kwargs.get('npts_fit',     "--points=1600 ") ## 66  --points=10000 --robustFit=1 --setRobustFitAlgo=Minuit2 --setRobustFitStrategy=2 --setRobustFitTolerance=0.001 --robustHesse=1 --robustFit=1 --setRobustFitAlgo=Minuit2 --setRobustFitStrategy=2 --setRobustFitTolerance=0.001
    fit_opts     = kwargs.get('fit_opts',      "--setRobustFitTolerance=0.001 --robustFit=1 --setRobustFitAlgo=Minuit2 --cminDefaultMinimizerStrategy=0 --setRobustFitStrategy=1  --X-rtd MINIMIZER_analytic %s"%(npts_fit) ) #--setRobustFitTolerance=0.001--robustFit=1 --setRobustFitAlgo=Minuit2 --setRobustFitStrategy=1  --X-rtd FITTER_NEW_CROSSING_ALGO
    xrtd_opts    = kwargs.get('xrtd_opts',    "") 
    cmin_opts    = kwargs.get('cmin_opts',     "--cminFallbackAlgo Minuit2,Migrad,0:0.0001 --cminPreScan") # --cminFallbackAlgo Minuit2,Migrad,0:0.0001 --cminPreScan
    save_opts    = kwargs.get('save_opts',    "--saveNLL --saveSpecifiedNuis all --saveFitResult --saveWorkspace") #--saveSpecifiedNuis all --saveFitResult")   
    era          = kwargs.get('era',          "")
    config_mumu  = kwargs.get('config_mumu',  "")
    mumu_input_file = kwargs.get('mumu_input_file', None)  # Add this line
    input_dir   = kwargs.get('input_dir')
    output_dir  = kwargs.get('output_dir', None)
    if output_dir is None:  # derived from input_dir (BUGS F18); --output_dir gives it when the input is elsewhere
        # build output_dir from input_dir but avoid duplicating the era if input_dir already ends with it
        base_out = input_dir.replace('input', 'output')
        if os.path.basename(os.path.normpath(input_dir)) == era:
            output_dir = os.path.normpath(base_out)
        else:
            output_dir = os.path.join(os.path.normpath(base_out), era)
    # convert to absolute path & create it to prevent nested directories when changing cwd
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f"input_dir: {input_dir}")
    print(f"computed output_dir: {output_dir}")
    workspace = ""

    # Create the workspace for combined fit
    if int(option) > 3:
        # merge datacards regions
        datacardfile = merge_datacards_regions(setup,setup_mumu, config_mumu, era, extratag, output_dir, mumu_input_file)
        print("datacard file for combined fit = %s" %(datacardfile)) 
        # Create workspace 
        os.system(f"text2workspace.py {output_dir}/{datacardfile}.txt")
        workspace = f"{output_dir}/{datacardfile}.root"
   
    # Variable of the fit (usually mvis)
    variable = "m_vis"
    ## For each region defined in scanRegions in the config file 
    for r in setup["observables"]["m_vis"]["scanRegions"]:
        print("Region : "+r)

        # Binelabel for output file of the fit
        BINLABELoutput = "mt_"+variable+"-"+r+setup["tag"]+extratag+"-"+era+"-13TeV"

        # For fit by region create the datacards and the workspace here
        if int(option) <= 3 :
            # For CR Zmumu 
            print("config_mumu = %s"  %(config_mumu))
            
            # FIX: Check if config_mumu exists OR if a direct file was provided
            if str(config_mumu) != 'None' or mumu_input_file:
                # merge datacards regions and CR
                # FIX: Pass mumu_input_file to the merge function
                datacardfile = merge_datacards_ZmmCR(setup, setup_mumu, era, extratag, r, output_dir, mumu_input_file)
                print("datacard file for fit by region with additionnal CR = %s" %(datacardfile)) 

            else:
                datacardfile = "ztt_mt_m_vis-"+r+setup["tag"]+extratag+"-"+era+"-13TeV"
                print("datacard file for fit by region = %s" %(datacardfile)) 
            # Create workspace 
            os.system(f"text2workspace.py {output_dir}/{datacardfile}.txt")
            workspace = f"{output_dir}/{datacardfile}.root"
            print("Datacard workspace has been created")

        ## FIT ##

        # Fit of tes_DM by DM with tid_SF as a nuisance parameter 
        if option == '1':
            POI = "tes_%s" % (r)
            NP = "rgx{.*tid.*}"
            print(">>>>>>> "+POI+" fit")
            if POI == "tes_DM10":
                tes_range = "0.950,1.030"
            POI_OPTS = "--saveWorkspace -P %s --setParameterRanges %s=%s:tid_SF_%s=%s:sf_W_%s=0.0,10.0 --setParameters r=1,rgx{.*tes.*}=1,rgx{.*tid.*}=1 --freezeParameters r  --redefineSignalPOIs tid_SF_%s --floatOtherPOIs=1" % (POI, POI, tes_range, r,tid_SF_range,r,r)  # tes_DM
            MultiDimFit_opts = " -m 90  %s %s %s -n .%s %s %s %s %s --trackParameters %s,rgx{.**.},rgx{.*sf_W_*.} --saveInactivePOI=1" %(workspace, algo, POI_OPTS, BINLABELoutput, fit_opts, xrtd_opts, cmin_opts, save_opts,NP)

            # Run combine in output_dir
            cwd = os.getcwd()
            os.makedirs(output_dir, exist_ok=True)
            os.chdir(output_dir)
            # Use only the filename for workspace
            workspace_filename = f"{datacardfile}.root"
            # Replace workspace path in MultiDimFit_opts with just the filename
            MultiDimFit_opts_local = MultiDimFit_opts.replace(workspace, workspace_filename)
            print("MultidimFit %s : " %(r), '\t', MultiDimFit_opts_local)
            os.system("combine -M MultiDimFit  %s" %(MultiDimFit_opts_local))
            os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 --doInitialFit --robustFit 1   --cminFallbackAlgo Minuit2,0:1 -v 0 --redefineSignalPOIs {POI} --setParameterRange r=0.96,1.04:{POI}={tes_range}")  
        
            os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 --doFits --robustFit 1  --parallel 8  --redefineSignalPOIs {POI} --setParameterRange r=0.96,1.04:{POI}={tes_range} -v 0")
            os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 -o tes_impacts_{r}.json --redefineSignalPOIs {POI} --setParameterRange r=0.96,1.04:{POI}={tes_range} -v 0") 
            os.system(f"plotImpacts.py -i tes_impacts_{r}.json -o impacts_tes_SF_{r}")

            os.chdir(cwd)
        # Fit of tid_SF_DM by DM with tes as a nuisance parameter
        elif option == '2':
            POI = "tid_SF_%s" % (r)
            NP = "rgx{.*tid.*}" 
            print(">>>>>>> Scan of "+POI)
            #POI_OPTS = "-P %s  --setParameterRanges %s=%s:tes_%s=%s -m 90 --setParameters r=1,rgx{.*tid.*}=1,rgx{.*tes.*}=1 --freezeParameters r,tes_%s --redefineSignalPOIs tes_%s --floatOtherPOIs 1" % (POI, POI, tid_SF_range,r,tes_range,r,r)  # tes_DM
            POI_OPTS = "-P %s --redefineSignalPOIs tes_%s --setParameterRanges %s=%s:tes_%s=%s -m 90 --setParameters r=1,rgx{.*tid.*}=1,rgx{.*tes.*}=1 --setParameterRange r=0.96,1.04 --floatOtherPOIs=1" % (POI,r, POI, tid_SF_range, r,tes_range)  # tes_DM
            MultiDimFit_opts = " %s %s %s -n .%s %s %s %s %s --trackParameters rgx{.*tid.*},rgx{.*W.*},rgx{.*dy.*} --saveInactivePOI=1 " %(workspace, algo, POI_OPTS, BINLABELoutput,fit_opts, xrtd_opts, cmin_opts, save_opts)
            print("MultidimFit %s : " %(r), '\t', MultiDimFit_opts)
            os.system("combine -M MultiDimFit %s " %(MultiDimFit_opts))

            os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 --doInitialFit --robustFit 1   --cminFallbackAlgo Minuit2,0:1 -v 0 --redefineSignalPOIs {POI} --setParameterRange r=0.96,1.04:{POI}=0.5,1.2")  
        
            os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 --doFits --robustFit 1  --parallel 8  --redefineSignalPOIs {POI} --setParameterRange r=0.96,1.04:{POI}=0.5,1.2 -v 0")
            os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 -o tid_impacts_{r}.json --redefineSignalPOIs {POI} --setParameterRange r=0.96,1.04:{POI}=0.5,1.2 -v 0") 
            os.system(f"plotImpacts.py -i tid_impacts_{r}.json -o impacts_tid_SF_{r}")

        # 2D Fit of tes_DM and tid_SF_DM by DM, both are pois
        elif option == '3':
            print(">>>>>>> Fit of tid_SF_"+r+" and tes_"+r)
            POI1 = "tid_SF_%s" % (r)
            POI2 = "tes_%s" % (r)
            # DM11 (3-prong + π0): tid_SF wants to go below the default 0.7 floor —
            # widen the range so the grid scan finds a real interior minimum instead
            # of pegging at the boundary.
            if r.startswith("DM11"):
                tid_SF_range = "0.5,1.2"
            POI_OPTS = "-P %s -P %s --setParameterRanges %s=%s:%s=%s --setParameters r=1 --redefineSignalPOIs %s,%s --freezeParameters r" % (POI2, POI1, POI2, tes_range, POI1,tid_SF_range, POI2, POI1) # :r=0.96,1.04 %s=1,%s=1, ,POI2, POI1  --freezeParameters r
            # POI_OPTS = "-P %s -P %s --setParameterRanges %s=%s:%s=%s  --setParameters r=1,%s=0.8,%s=1.025 --redefineSignalPOIs %s,%s  --freezeParameters r" % (POI2, POI1, POI2, tes_range, POI1,tid_SF_range, POI2, POI1, POI2,POI1) # %s=1,%s=1, ,POI2, POI1  --freezeParameters r  --freezeParameters r
            MultiDimFit_opts = " -m 90 %s %s %s -n .%s %s %s %s %s " %(workspace, algo, POI_OPTS, BINLABELoutput, fit_opts, xrtd_opts, cmin_opts, save_opts) #--trackParameters rgx{.*tid.*},rgx{.*W.*},rgx{.*dy.*} --cminFallbackAlgo Minuit2,Migrad,0:0.001
            
            # Run combine in output_dir
            cwd = os.getcwd()
            os.makedirs(output_dir, exist_ok=True)
            try:
                os.chdir(output_dir)
                workspace_filename = f"{datacardfile}.root"
                MultiDimFit_opts_local = MultiDimFit_opts.replace(workspace, workspace_filename)
                print("2D MultidimFit %s : " %(r), '\t', MultiDimFit_opts_local)
                os.system("combine -M MultiDimFit  %s" %(MultiDimFit_opts_local))
                print("COMMAND: combine -M MultiDimFit  %s" %(MultiDimFit_opts_local))

                # --- Iterative boost: each pass, if the grid found a deeper basin
                # than the converged free-POI fit (entry 0), reseed from the deepest
                # grid point's POIs + profiled nuisances and re-run. Stops when entry
                # 0 is the deepest point or after MAX_BOOST_ITER iterations. Each
                # pass reuses the same -n tag, overwriting the previous file. ---
                fit_result_file = f"higgsCombine.{BINLABELoutput}.MultiDimFit.mH90.root"
                MAX_BOOST_ITER = 3
                for boost_iter in range(1, MAX_BOOST_ITER + 1):
                    boost = find_boost_params(fit_result_file, f"tes_{r}", f"tid_SF_{r}")
                    if not boost:
                        if boost_iter > 1:
                            print(f"[BOOST] Converged after {boost_iter - 1} extra pass(es)")
                        break
                    boosted_opts = MultiDimFit_opts_local.replace(
                        "--setParameters r=1",
                        "--setParameters r=1,%s" % boost
                    )
                    print(f"[BOOST] Re-running scan with seeded parameters (pass {boost_iter + 1})")
                    print("2D MultidimFit (pass-%d boosted) %s : " % (boost_iter + 1, r), '\t', boosted_opts)
                    os.system("combine -M MultiDimFit  %s" %(boosted_opts))
                    print(f"[BOOST] Pass-{boost_iter + 1} complete — overwrote {fit_result_file}")
                else:
                    print(f"[BOOST] Reached MAX_BOOST_ITER={MAX_BOOST_ITER} without entry 0 becoming global min — accepting current result")

                # Extract actual parameter values from the fit result
                param_file = f"FitparameterValues_{setup['tag']}_DeepTau_{era}-13TeV_{r}.txt"
                print(f"[DEBUG] Looking for 2D fit result file: {fit_result_file}")
                print(f"[DEBUG] Creating parameter file: {param_file}")
                # if os.path.exists(fit_result_file):
                import ROOT
                f = ROOT.TFile.Open(fit_result_file)
                tree = f.Get("limit") if f and not f.IsZombie() else None
                if tree and hasattr(tree, "GetListOfBranches"):
                    branches = [b.GetName() for b in tree.GetListOfBranches()]
                    nll_branch = "deltaNLL"

                    best_idx = 0
                    best_val = float("inf")
                    nentries = int(tree.GetEntries())

                    tes_vals_in_1sigma = []
                    tid_vals_in_1sigma = []

                    # Parse ranges
                    tes_min, tes_max = [float(x) for x in tes_range.split(',')]
                    tid_min, tid_max = [float(x) for x in tid_SF_range.split(',')]

                    # First pass: properly loop and fill 1σ arrays
                    for i in range(nentries):
                        tree.GetEntry(i)

                        if 0 <= tree.deltaNLL <= 0.5:     
                            val_tes = getattr(tree, f"tes_{r}")
                            val_tid = getattr(tree, f"tid_SF_{r}")

                            if (tes_min <= val_tes <= tes_max) and (tid_min <= val_tid <= tid_max):
                                tes_vals_in_1sigma.append(val_tes)
                                tid_vals_in_1sigma.append(val_tid)

                    # Protect against empty lists
                    if tes_vals_in_1sigma:
                        tes_low  = min(tes_vals_in_1sigma)
                        tes_high = max(tes_vals_in_1sigma)
                    else:
                        tes_low = tes_high = None

                    if tid_vals_in_1sigma:
                        tid_low  = min(tid_vals_in_1sigma)
                        tid_high = max(tid_vals_in_1sigma)
                    else:
                        tid_low = tid_high = None

                    print(f"[DEBUG] TES 1-sigma range: {tes_low} - {tes_high}")
                    print(f"[DEBUG] TauID SF 1-sigma range: {tid_low} - {tid_high}")

                    # Second pass: find best-fit index
                    for i in range(nentries):
                        tree.GetEntry(i)
                        val = float(getattr(tree, nll_branch))
                        if val < best_val and val >= 0:
                            best_val = val
                            best_idx = i

                    # Load best-fit entry
                    tree.GetEntry(best_idx)
                    tes_val = float(getattr(tree, f"tes_{r}"))
                    tid_val = float(getattr(tree, f"tid_SF_{r}"))

                    print(f"[DEBUG] Best fit entry index: {best_idx} with deltaNLL = {best_val}")
                    print(f"tes_vals_in_1sigma: {tes_vals_in_1sigma}")
                    print(f"tid_vals_in_1sigma: {tid_vals_in_1sigma}")
                    print(f"[DEBUG] Best fit TES: tes_{r} = {tes_val}")
                    print(f"[DEBUG] Best fit TauID SF: tid_SF_{r} = {tid_val}")

                    print(f"[INFO] Extracted TES:   tes_{r} = {tes_val:.6f}")
                    print(f"[INFO] Extracted TauID: tid_SF_{r} = {tid_val:.6f}")

                    # except Exception:
                    #     tes_val, tid_val = 1.0, 1.0
                    # Extract nuisance values from entry 0 (the free-POI converged fit).
                    # These seed FitDiagnostics in step 2 so Migrad starts at MultiDimFit's
                    # minimum, not at datacard defaults — needed for low-stats high-pt regions
                    # where defaults put FitDiag in a different basin and Hesse fails silently.
                    tree.GetEntry(0)
                    skip_branches = {"deltaNLL", "quantileExpected", "iToy", "limit", "limitErr",
                                     "mh", "syst", "iSeed", "t_cpu", "t_real", "r",
                                     f"tes_{r}", f"tid_SF_{r}"}
                    nuis_seeds = []
                    for b in tree.GetListOfBranches():
                        bname = b.GetName()
                        if bname in skip_branches: continue
                        try:
                            v = float(getattr(tree, bname))
                        except Exception:
                            continue
                        if abs(v) > 1e3: continue  # guard against junk
                        nuis_seeds.append((bname, v))

                    with open(param_file, "w") as pf:
                        # BUGS F05: a missing 1-sigma interval (None) is left out instead of raising TypeError
                        pf.write(f"tes_{r}: {tes_val:.6f}\n")
                        if tes_low is not None:
                            pf.write(f"tes_{r}_1sigma_low: {tes_low:.6f}\n")
                            pf.write(f"tes_{r}_1sigma_high: {tes_high:.6f}\n")
                        pf.write(f"tid_SF_{r}: {tid_val:.6f}\n")
                        if tid_low is not None:
                            pf.write(f"tid_SF_{r}_1sigma_low: {tid_low:.6f}\n")
                            pf.write(f"tid_SF_{r}_1sigma_high: {tid_high:.6f}\n")
                        for bname, v in nuis_seeds:
                            pf.write(f"{bname}: {v:.6f}\n")
                    print(f"[INFO] Parameter values written to {param_file} ({len(nuis_seeds)} nuisances seeded)")
                    f.Close()

                ###################
                # from math import isnan
                # import ROOT
                # fit_result_file = f"multidimfit.{BINLABELoutput}.root" 
                # f = ROOT.TFile.Open(fit_result_file)
                # if not f or f.IsZombie():
                #     print("[ERROR] Could not open fit result file.")
                # else:
                #     fit = f.Get("fit_mdf")
                #     if not fit:
                #         print("[ERROR] Could not find RooFitResult 'fit_mdf'.")
                #     else:
                #         # Build parameter names: tes_DM0, tid_SF_DM0 → using {r}
                #         tes_name = f"tes_{r}"
                #         tid_name = f"tid_SF_{r}"

                #         pars = fit.floatParsFinal()

                #         tes_var = pars.find(tes_name)
                #         tid_var = pars.find(tid_name)

                #         if not tes_var or not tid_var:
                #             print(f"[ERROR] TES or TauID not found: {tes_name}, {tid_name}")
                #         else:
                #             tes_val, tes_err = tes_var.getVal(), tes_var.getError()
                #             tid_val, tid_err = tid_var.getVal(), tid_var.getError()

                #             # Write results to file
                #             with open(param_file, "w") as pf:
                #                 pf.write(f"{tes_name}: {tes_val:.6f}\n") #  +/- {tes_err:.6f}\n")
                #                 pf.write(f"{tid_name}: {tid_val:.6f}\n") #  +/- {tid_err:.6f}\n")

                #             print(f"[INFO] Extracted TES:   {tes_name} = {tes_val:.6f} ± {tes_err:.6f}")
                #             print(f"[INFO] Extracted TauID: {tid_name} = {tid_val:.6f} ± {tid_err:.6f}")

                #     f.Close()

                ###################
                else:
                    continue

                # os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 --doInitialFit --robustFit 1 --cminFallbackAlgo Minuit2,0:1 -v 0 --redefineSignalPOIs {POI2},{POI1} --setParameterRange {POI2}={tes_range}:{POI1}={tid_SF_range} --setParameters r=1 --freezeParameters r ")  
                # os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 --doFits --robustFit 1  --parallel 8  --redefineSignalPOIs {POI2},{POI1} --setParameterRange {POI2}={tes_range}:{POI1}={tid_SF_range} --setParameters r=1 --freezeParameters r -v 0")
                # os.system(f"combineTool.py -M Impacts -d {workspace} -m 90 -o impacts_{r}.json --redefineSignalPOIs {POI2},{POI1} --setParameterRange {POI2}={tes_range}:{POI1}={tid_SF_range} --setParameters r=1 --freezeParameters r -v 0") 
                # os.system(f"plotImpacts.py -i impacts_{r}.json -o impacts_{r}_{POI1} --POI {POI1}")
                # os.system(f"plotImpacts.py -i impacts_{r}.json -o impacts_{r}_{POI2} --POI {POI2}")

            finally:
                os.chdir(cwd)

        ### Fit with combined datacards  tes_DM0,tes_DM1,tes_DM10,tes_DM11 
        ## Fit of tid_SF in its regions with tes_region and other tid_SF_regions as nuisance parameters    tes_DM0,tes_DM1,tes_DM10,tes_DM11
        elif option == '4': 
            print(">>>>>>> Fit of tid_SF_"+r)
            POI_OPTS = "-P tid_SF_%s --redefineSignalPOIs tes_DM0_pt1,tes_DM0_pt2,tes_DM1_pt1,tes_DM1_pt2,tes_DM10_pt1,tes_DM10_pt2,tes_DM11_pt1,tes_DM11_pt2  --setParameterRanges rgx{.*tid.*}=%s:rgx{.*tes.*}=%s -m 90 --setParameters r=1,rgx{.*tes.*}=1 --freezeParameters r --floatOtherPOIs=1 " %(r, tid_SF_range,tes_range)
            MultiDimFit_opts = "%s %s %s -n .%s %s %s %s %s  --trackParameters rgx{.*tid.*},rgx{.*W.*},rgx{.*dy.*} --saveInactivePOI=1" %(workspace, algo, POI_OPTS, BINLABELoutput, fit_opts, xrtd_opts, cmin_opts, save_opts)
            os.system("combine -M MultiDimFit %s" %(MultiDimFit_opts))

        ## Fit of tes in DM regions with tid_SF and other tes_DM as nuisance parameters  
        elif option == '5':
            print(">>>>>>> simultaneous fit of tid_SF in pt bins and tes_"+r + " in DM")
            POI_OPTS = "-P tes_%s --redefineSignalPOIs tes_DM0,tes_DM1,tes_DM10,tes_DM11,tid_SF_DM0,tid_SF_DM1,tid_SF_DM10,tid_SF_DM11 --setParameterRanges rgx{.*tid.*}=%s:rgx{.*tes.*}=%s -m 90 --setParameters r=1,rgx{.*tes.*}=1,rgx{.*tid.*}=1 --freezeParameters r --floatOtherPOIs=1" %(r, tid_SF_range, tes_range)
            MultiDimFit_opts = "%s %s %s -n .%s %s %s %s %s --trackParameters rgx{.**.} --saveInactivePOI=1"  %(workspace, algo, POI_OPTS, BINLABELoutput, fit_opts, xrtd_opts, cmin_opts, save_opts)
            os.system("combine -M MultiDimFit %s " %(MultiDimFit_opts))

        ### 2D Fit of tes_DM and tid_SF in DM and pt regions with others tid_SF and tes_DM as nuisance parameter
        elif option == '6':
            #for each decay mode
            for r in setup['tidRegions']: #["DM0","DM1","DM10","DM11"]
                for dm in setup['tesRegions']:
                    print("Region : "+r)
                    print(">>>>>>> simultaneous fit of tes_" +r + " in pt bins and tes_"+r + "in DM")
                    POI_OPTS = "-P tid_SF_%s -P tes_%s --setParameterRanges rgx{.*tid.*}=%s:rgx{.*tes.*}=%s -m 90 --setParameters r=1 --freezeParameters r" %(r,dm, tid_SF_range, tes_range)
                    MultiDimFit_opts = "-m 90 %s %s %s -n .%s %s %s %s %s  " %(workspace, algo, POI_OPTS, BINLABELoutput, fit_opts, xrtd_opts, cmin_opts, save_opts)
                    os.system("combine -M MultiDimFit %s" %(MultiDimFit_opts))

        else:
            continue

    # only move files if we are not already in the output dir
    if os.path.abspath(os.getcwd()) != output_dir:
        os.system("mv higgsCombine*root %s" %output_dir)
        os.system("mv *.root %s" %output_dir)
        os.system("mv *.png %s"%output_dir)

    

# Plot the scan using output file of combined 
def plotScan(setup, setup_mumu, option, **kwargs):
    tid_SF_range = kwargs.get('tid_SF_range', "0.8,1.2")
    extratag     = kwargs.get('extratag',     "_DeepTau")
    era          = kwargs.get('era',          ""        )
    labelopt     = kwargs.get('labelopt',     ""        ) # --lumi/--cme for the plot scripts (CL §27)
    config       = kwargs.get('config',       ""        )
    indir        = kwargs.get('indir', "")
    plot_dir     = kwargs.get('plot_dir', None) # None: plot2DScan_MultiDimFit.py derives it from indir
    # Plot 

    if option == '2' or option == '4'  :
        print(">>> Plot parabola")
        os.system((" python3 TauES_ID/plotParabola_POI_region.py -p tid_SF -y %s -e %s  -s -a -c %s -i %s"% (era, extratag, config, indir))+labelopt)
        os.system((" python3 TauES_ID/plotPostFitScan_POI.py --poi tid_SF -y %s -e %s -r %s,%s -c %s -i %s" %(era,extratag,min(tid_SF_range),max(tid_SF_range), config, indir))+labelopt)

    elif option == '1' or option == '5' :
        print('indir: ', indir)
        print(">>> Plot parabola")
        os.system((" python3 TauES_ID/plotParabola_POI_region.py -p tes -y %s -e %s -r %s,%s -s -a -c %s -i %s" % (era, extratag, min(setup["TESvariations"]["values"]), max(setup["TESvariations"]["values"]), config, indir))+labelopt)
        os.system((" python3 TauES_ID/plotPostFitScan_POI.py --poi tes -y %s -e %s -r %s,%s -c %s -i %s" %(era,extratag,min(setup["TESvariations"]["values"]),max(setup["TESvariations"]["values"]), config, indir))+labelopt)

    elif option == '3':
        print(">>> Plot 1D scans for each POI in each region (from 2D fit output)")
        # Then create individual 2D plots for each region (optional, for detailed view)
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plot2DScan_MultiDimFit.py") # BUGS F15
        outopt = f" --outdir {plot_dir}" if plot_dir else ""
        for r in setup["observables"]["m_vis"]["scanRegions"]:
            print(f"python3 {script} --poi1 tes_{r} --poi2 tid_SF_{r} -y {era} -c {config} -i {indir} -t multidimfit{outopt}")
            os.system(f"python3 {script} --poi1 tes_{r} --poi2 tid_SF_{r} -y {era} -c {config} -i {indir} -t multidimfit{outopt}{labelopt}")
        # for r in setup["observables"]["m_vis"]["scanRegions"]:
        #     # Plot TES
        #     os.system(f"python3 TauES_ID/plotParabola_POI_region.py -p tes -y {era} -e {extratag} -r {min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])} -s -a -c {config} -i {indir}")
        #     os.system(f"python3 TauES_ID/plotPostFitScan_POI.py --poi tes -y {era} -e {extratag} -r {min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])} -c {config} -i {indir}")
        #     # Plot TID SF
        #     os.system(f"python3 TauES_ID/plotParabola_POI_region.py -p tid_SF -y {era} -e {extratag} -s -a -c {config} -i {indir}")
        #     os.system(f"python3 TauES_ID/plotPostFitScan_POI.py --poi tid_SF -y {era} -e {extratag} -r {min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])} -c {config} -i {indir}")

    
    else:
        print(" No output plot...")






### main function
def main(args):


    era    = args.era
    config = args.config
    config_mumu = args.config_mumu 
    option = args.option
    # Always set extratag to a non-empty default value
    extratag = "_DeepTau"
    input_dir = args.input_dir
    output_dir = args.output_dir
    if output_dir is None:  # derived from input_dir (BUGS F18); --output_dir gives it when the input is elsewhere
        # build output_dir from input_dir but avoid duplicating the era if input_dir already ends with it
        base_out = input_dir.replace('input', 'output')
        if os.path.basename(os.path.normpath(input_dir)) == era:
            output_dir = os.path.normpath(base_out)
        else:
            output_dir = os.path.join(os.path.normpath(base_out), era)
    # convert to absolute path & create it to prevent nested directories when changing cwd
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f"input_dir: {input_dir}")
    print(f"computed output_dir: {output_dir}")
    print("Using configuration file: %s"%(args.config))
    with open(args.config, 'r') as file:
        setup = yaml.safe_load(file)


    if config_mumu != 'None':
        print("Using configuration file for mumu: %s"%(args.config_mumu))
        with open(args.config_mumu, 'r') as file_mumu:
            setup_mumu = yaml.safe_load(file_mumu)
    else: 
        setup_mumu = 0

    # Generating the datacards for mutau channel
    generate_datacards_mutau(era=era, config=config, extratag=extratag, input_dir=input_dir,
                             output_dir=output_dir if args.output_dir else None)

    # Generating the datacards for mumu channel (commented out, use provided file instead)
    # if str(config_mumu) != 'None':
    #     output_dir = input_dir.replace('input', 'output')
    #     output_dir = os.path.join(output_dir, era)
    #     generate_datacards_mumu(era=era, config_mumu=config_mumu, extratag=extratag, output_dir=output_dir)

    # Attach mumu_datacard_file to setup for use in merge_datacards_regions
    setup['mumu_datacard_file'] = getattr(args, 'mumu_datacard_file', None)

    # Run the fit using combine with the different options 
    # FIX: Pass mumu_input_file explicitly in the kwargs
    run_combined_fit(setup, setup_mumu, era=era, input_dir=input_dir, output_dir=output_dir, config=config, config_mumu=config_mumu, option=option, extratag=extratag, mumu_input_file=args.mumu_datacard_file)

    # Plots
    plot_dir = os.path.abspath(args.plot_dir) if args.plot_dir else None
    labelopt = "".join(" --%s %r" % (key, value) for key, value in (('lumi', args.lumi), ('cme', args.cme)) if value is not None)
    plotScan(setup, setup_mumu, era=era, config=config, config_mumu=config_mumu, option=option, indir=output_dir, extratag=extratag, plot_dir=plot_dir, labelopt=labelopt)


###
if __name__ == '__main__':

    argv = sys.argv
    extratag = ""
    parser = ArgumentParser(prog="makeTESfit", description="execute all steps to run TES fit")
    parser.add_argument('-y', '--era', dest='era', default=['2025'], action='store', help="set era")
    parser.add_argument('-c', '--config', dest='config', type=str, default='TauES_ID/config/defaultFitSetupTES_mutau.yml', action='store', help="set config file containing sample & fit setup")
    parser.add_argument('-o', '--option', dest='option', choices=['1', '2', '3', '4', '5','6'], default='1', action='store',
                        help="set option : Scan of tes and tid SF is profiled (-o 1) ;  Scan of tid SF and tes is profiled (-o 2) ; 2D scan of tes and tid SF (-o 3) \
                        ; Scan of tid SF, tid SF and tes of other regions are profiled POIs (-o 4); Scan of tes, tid SF and tes of other regions are profiled POIs(-o 5)\
                        ; 2D scan of tes and tid SF and tes of other regions are profiled POIs (-o 6) ")
    parser.add_argument('-cmm', '--config_mumu', dest='config_mumu', type=str, default='None', action='store', help="set config file containing sample & fit setup")
    parser.add_argument('--mumu_datacard_file', dest='mumu_datacard_file', type=str, default=None, help="Path to the mumu datacard file to use (if not generating)")
    parser.add_argument('-i', '--input_dir', dest='input_dir', type=str, help="inputdir containing root files for datacard")
    parser.add_argument('--output_dir', dest='output_dir', type=str, default=None, help="directory of the cards and fit results (default: input_dir with 'input' -> 'output', plus the era)")
    parser.add_argument('--plot_dir', dest='plot_dir', type=str, default=None, help="directory of the 2D scan plots (default: output_dir with 'output' -> 'plots')")
    # BUGS F04: --input_file (required, but never used) was removed
    parser.add_argument('--lumi', dest='lumi', type=float, default=None, help="integrated luminosity [/fb] of the CMS label (default: CMSStyle.lumi_dict of the era; the TauFW Framework gives the one of the shapes' normalisation, CL §27)")
    parser.add_argument('--cme', dest='cme', type=float, default=None, help="centre-of-mass energy [TeV] of the CMS label (default: CMSStyle.cme_dict of the era)")
    args = parser.parse_args()

    main(args)
    print(">>>\n>>> done\n")
