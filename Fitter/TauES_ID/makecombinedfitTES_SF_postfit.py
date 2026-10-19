#! /usr/bin/env python
"""
Date : Sept 2024
Author : @oponcet 
Description :
This script is used to run a FITDiagnotic for TES and tid_S. It take as input the values of the parameter of the fit obtained wit h MultiDimFit in makecombinedfit_TES_SF.py. The parameters are read from a text file and used in the fit. The fit is done for each region defined in the config file. The fit is done using the combine tool. The output of the fit is saved in a root file. The script also run the PostFitShapeFromWorkspace to get the postfit shape of the fit. 
"""

from distutils import filelist
from distutils.command.config import config
import sys
import os
import yaml
from argparse import ArgumentParser

# Generating the datacards for mutau channel
def generate_datacards_mutau(era, config, extratag):
    print(' >>>>>> Generating datacards for mutau channel')
    os.system("python3 TauES_ID/harvestDatacards_TES_idSF_MCStat.py -y %s -c %s -e %s "%(era,config,extratag)) 

# Generating the datacards for mumu channel
def generate_datacards_mumu(era, config_mumu, extratag):
    print(' >>>>>> Generating datacards for mumu channel')
    os.system("python3 TauES_ID/harvestDatacards_zmm.py -y %s -c %s -e %s "%(era,config_mumu,extratag)) # Generating the datacards with one statistics uncertianties for all processes

# Merge the datacards between regions for combine fit and return the name of the combined datacard file
def merge_datacards_regions(setup, setup_mumu, config_mumu, era, extratag, mumu_input_file=None):
    # Variable of the fit (usually mvis)
    variable = "m_vis"
    print("Observable : "+variable)
    # LABEL used for datacard file
    LABEL = setup["tag"]+extratag+"-"+era+"-13TeV"
    filelist = "" # List of the datacard files to merge in one file combinecards.txt
    # Name of the combined datacard file
    outcombinedfile = "combinecards%s" %(setup["tag"])
    fit_outdir = os.path.join(args.indir, str(era)) #fit_outdir = f"output_pt_less_region/againstjet_Medium/againstelectron_VVLoose/{era}"
    os.makedirs(fit_outdir, exist_ok=True)
    for region in setup["observables"]["m_vis"]["fitRegions"]:
        filelist += region + f"={fit_outdir}/ztt_mt_m_vis-"+region+LABEL+".txt "
        os.system(f"combineCards.py {filelist} >{fit_outdir}/{outcombinedfile}.txt")
    #print("filelist : %s") %(filelist) 
    # Add the CR datacard file to the lsit of file to merge if there is CR option
    if str(config_mumu) != 'None':
        if mumu_input_file:
            filelist += f"zmm={mumu_input_file} "
        else:
            LABEL_mumu = setup_mumu["tag"]+extratag+"-"+era+"-13TeV"
            filelist +=  f"zmm={fit_outdir}/ztt_mm_m_vis-baseline"+LABEL_mumu+".txt "
        outcombinedfile += "CR"
        os.system(f"combineCards.py {filelist} >{fit_outdir}/{outcombinedfile}.txt")
    print(">>>>>>>>> merging datacards is done ")
    return outcombinedfile



# Merge the datacards between mt regions and Zmm when using Zmm CR and return the name of the CR + region datacard file
def merge_datacards_ZmmCR(setup, setup_mumu, era,extratag,region, mumu_input_file=None):
    # datacard of the region to be merged
    fit_outdir = os.path.join(args.indir, str(era)) #fit_outdir = f"output_pt_less_region/againstjet_Medium/againstelectron_VVLoose/{era}"
    datacardfile_region = f"ztt_mt_m_vis-{region}"+setup["tag"]+extratag+f"-{era}-13TeV.txt"
    filelist = f"{region}={fit_outdir}/{datacardfile_region}"
    if mumu_input_file:
        filelist += f" Zmm={mumu_input_file} "
    else:
        LABEL_mumu = setup_mumu["tag"]+extratag+f"-{era}-13TeV"
        filelist += f" Zmm={fit_outdir}/ztt_mm_m_vis-baseline"+LABEL_mumu+".txt "
    print(filelist)
    # Name of the CR + region datacard file
    outCRfile = f"ztt_mt_m_vis-{region}_zmmCR" #outCRfile = mumu_input_file #"ztt_mt_m_vis-%s_zmmCR" %(region)
    os.system(f"combineCards.py {filelist} >{fit_outdir}/{outCRfile}.txt")
    return outCRfile
    
def run_combined_fit(setup, setup_mumu, option, **kwargs):
    mumu_input_file = kwargs.get('mumu_input_file', None)
    tes_range    = kwargs.get('tes_range',    "%s,%s" %(min(setup["TESvariations"]["values"]), max(setup["TESvariations"]["values"])))
    tid_SF_range = kwargs.get('tid_SF_range', "0.50,1.2")
    extratag     = kwargs.get('extratag',     "_DeepTau")
    algo         = kwargs.get('algo',         "--algo=singles   ") #--alignEdges=1") #--alignEdges=1 grid
    npts_fit     = kwargs.get('npts_fit',     "")
    fit_opts     = kwargs.get('fit_opts',     "--setRobustFitTolerance=0.001 --robustFit=1 --setRobustFitAlgo=Minuit2 --cminDefaultMinimizerStrategy=0 --setRobustFitStrategy=1  --X-rtd MINIMIZER_analytic --cminFallbackAlgo Minuit2,Migrad,0:0.0001 --cminPreScan") # --robustFit=1 --setRobustFitAlgo=Minuit2   --setRobustFitStrategy=1 --cminFallbackAlgo Minuit2,Migrad,0:0.0001 --cminPreScan --X-rtd FITTER_NEW_CROSSING_ALGO 
    xrtd_opts    = kwargs.get('xrtd_opts',    "") #--X-rtd FITTER_NEW_CROSSING_ALGO --X-rtd FITTER_NE
    cmin_opts    = kwargs.get('cmin_opts',    "") #--cminFallbackAlgo Minuit2,Migrad,0:0.0001 --cminPreScan --cminDefaultMinimizerStrategy 0
    save_opts    = kwargs.get('save_opts',    " --saveShapes")
    era          = kwargs.get('era',          "")
    jet_wp       = kwargs.get('jet_wp', args.jet_wp)
    ele_wp       = kwargs.get('ele_wp', args.ele_wp)
    config_mumu  = kwargs.get('config_mumu',  "")
    workspace = ""

    # Set the base output directories
    fit_outdir = os.path.join(args.indir, str(era))
    postfit_outdir = fit_outdir.replace("output", "postfit")
    os.makedirs(fit_outdir, exist_ok=True)
    os.makedirs(postfit_outdir, exist_ok=True)
    print(f"[INFO] fit_outdir: {fit_outdir}")
    print(f"[INFO] postfit_outdir: {postfit_outdir}")
    # Create the workspace for combined fit
    if int(option) > 3:
        datacardfile = merge_datacards_regions(setup,setup_mumu, config_mumu, era, extratag, mumu_input_file=mumu_input_file)
        print(f"datacard file for combined fit = {datacardfile}")
        os.system(f"text2workspace.py {fit_outdir}/{datacardfile}.txt -o {postfit_outdir}/{datacardfile}.root")
        workspace = f"{postfit_outdir}/{datacardfile}.root"

    variable = "m_vis"
    for r in setup["observables"]["m_vis"]["scanRegions"]:
        print("Region : "+r)
        print(f"[INFO] Processing region: {r}")
        BINLABELoutput = f"mt_{variable}-{r}{setup['tag']}{extratag}-{era}-13TeV"

        if int(option) <= 3:
            print(f"config_mumu = {config_mumu}")
            if str(config_mumu) != 'None':
                datacardfile = merge_datacards_ZmmCR(setup, setup_mumu, era, extratag, r, mumu_input_file=mumu_input_file)
                print(f"datacard file for fit by region with additionnal CR = {datacardfile}")
            else:
                datacardfile = f"ztt_mt_m_vis-{r}{setup['tag']}{extratag}-{era}-13TeV"
                print(f"datacard file for fit by region = {datacardfile}")
            # Create workspace 
            # Always read datacard from fit_outdir, write workspace to postfit_outdir
            os.system(f"text2workspace.py {fit_outdir}/{datacardfile}.txt -o {postfit_outdir}/{datacardfile}.root")
            print(f"[DEBUG] text2workspace command: text2workspace.py {fit_outdir}/{datacardfile}.txt -o {postfit_outdir}/{datacardfile}.root")
            workspace = f"{postfit_outdir}/{datacardfile}.root"
            print("Datacard workspace has been created")

        if option == '1':
                POI = f"tes_{r}"
                NP = "rgx{.*tid.*}"
                # Here you can adjsut the range of the TES to constrain it in the FITDAIGNOSTICS 
                if r == "DM0" :
                    tes_range = "0.990,1.010"
                elif r == "DM1" :
                    tes_range = "0.990,1.010"
                elif r == "DM10" :
                    tes_range = "0.990,1.010"
                elif r == "DM11":
                    tes_range = "0.990,1.010"
                elif r == "DM0_pt1" :
                    tes_range = "0.995,1.020"
                elif r == "DM0_pt2" :
                    tes_range = "0.995,1.015"
                elif r == "DM0_pt3" :
                    tes_range = "0.990,1.010"
                elif r == "DM0_pt4" :
                    tes_range = "0.942,0.962"
                elif r == "DM1_pt1" :
                    tes_range = "0.995,1.005"
                elif r == "DM1_pt2" :
                    tes_range = "1.005,1.015"
                elif r == "DM1_pt3" :
                    tes_range = "1.010,1.020"
                elif r == "DM1_pt4" :
                    tes_range = "0.990,1.010"
                elif r == "DM10_pt1" :
                    tes_range = "0.985,1.000"
                elif r == "DM10_pt2" :
                    tes_range = "1.000,1.010"
                elif r == "DM10_pt3" :
                    tes_range = "1.010,1.020"
                elif r == "DM10_pt4" :
                    tes_range = "0.984,1.010"
                elif r == "DM11_pt1":
                    tes_range = "0.990,1.010"
                elif r == "DM11_pt2":
                    tes_range = "1.000,1.020"
                elif r == "DM11_pt3":
                    tes_range = "1.000,1.020"
                elif r == "DM11_pt4":
                    tes_range = "1.020,1.030"
                else:
                    tes_range = "0.900,1.300"

                # Load the parameters from the text file (always from postfit_outdir)
                param_file = kwargs.get('param_file', f"{postfit_outdir}/FitparameterValues_{setup['tag']}_DeepTau_{era}-13TeV_{r}.txt")
                params = {}
                with open(param_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = float(value.strip())
                            if key.startswith('trackedParam_'):
                                key = key[len('trackedParam_'):]
                            params[key] = value
                        else:
                            print(f"Skipping invalid line: {line}")

                param_opts = ",".join([f"{key}={value}" for key, value in params.items()])
                print("param_opts : %s" %(param_opts))
                POI_OPTS_F = f"--saveNLL --setParameters r=1,{param_opts} --setParameterRanges tes_{r}={tes_range}:tid_SF_{r}={tid_SF_range}:sf_W_{r}=0.0,10.0 --freezeParameters r,tes_{r},tid_SF_{r}"
                MutliFitout = f"{fit_outdir}/higgsCombine.{BINLABELoutput}.MultiDimFit.mH90.root"
                FitDiagnostics_opts = f" -m 90  {MutliFitout} {POI_OPTS_F} -n .{BINLABELoutput} {xrtd_opts} {cmin_opts} "
                print(f">>>>>>>>>>>>>>>>>>>>>>[DEBUG] FitDiagnostics command: combine -M FitDiagnostics {FitDiagnostics_opts} --redefineSignalPOIs tes_{r}  --plots")
                
                # os.system(f"combine -M FitDiagnostics {FitDiagnostics_opts} --redefineSignalPOIs tes_{r},tid_SF_{r}  --plots")
                # Use the workspace file produced by text2workspace.py, using postfit_outdir from args.indir
                workspace_file = f"{postfit_outdir}/{datacardfile}.root"
                print(f"[DEBUG] Workspace file: {workspace_file}")
                FitDiagnostics_opts = f" -m 90 -d {workspace_file} {POI_OPTS_F} -n .{BINLABELoutput} {xrtd_opts} {cmin_opts} "
 
                print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>[DEBUG] FitDiagnostics command: combine -M FitDiagnostics {FitDiagnostics_opts} --redefineSignalPOIs tes_{r},tid_SF_{r} --plots")
                os.system(f"combine -M FitDiagnostics {FitDiagnostics_opts} --redefineSignalPOIs tes_{r},tid_SF_{r} --plots")

                print(f"FitDiagnostics {r} : ")

                # Postfit shape:
                outf_postfit = f"output_pt_less_region/againstjet_Medium/againstelectron_Tight/2024/PostFitShape_{era}_{setup['tag']}_{r}.root" # {postfit_outdir}
                outf_fit = f"output_pt_less_region/againstjet_Medium/againstelectron_Tight/2024/fitDiagnostics.mt_m_vis-{r}{setup['tag']}_DeepTau-{era}-13TeV.root" # {postfit_outdir}
                print(f"[DEBUG] PostFitShapesFromWorkspace command: PostFitShapesFromWorkspace --output {outf_postfit} --workspace {workspace} -f {outf_fit}:fit_s --postfit")
                os.system(f"PostFitShapesFromWorkspace --output {outf_postfit} --workspace {workspace} -f {outf_fit}:fit_s --postfit")
                print(f"[DEBUG] Created postfit shape file: {outf_postfit}")
        elif option == '3':
            # Option 3: 2D scan - need to run FitDiagnostics first
            POI = f"tes_{r},tid_SF_{r}"
            tid_SF_range = kwargs.get('tid_SF_range', "0.5,1.2")
            # DM11 (3-prong + π0): widen tid_SF range; the default 0.7 floor was
            # being hit and the seed at boundary crashed FitDiagnostics' Hesse step.
            if r.startswith("DM11"):
                tid_SF_range = "0.5,1.2"
            # Set TES range based on region (same logic as option 1)
            if r == "DM022":
                tes_range = "0.970,1.028"
            # elif r == "DM1":
            #     tes_range = "0.970,1.028"
            # elif r == "DM10":
            #     tes_range = "0.970,1.028"
            # elif r == "DM11":
            #     tes_range = "0.970,1.028"
            # elif r == "DM0_pt1":
            #     tes_range = "0.970,1.028"
            # elif r == "DM0_pt2":
            #     tes_range = "0.970,1.028"
            # elif r == "DM0_pt3":
            #     tes_range = "0.970,1.028"
            # elif r == "DM0_pt4":
            #     tes_range = "0.970,1.028"
            # elif r == "DM1_pt1":
            #     tes_range = "0.970,1.028"
            # elif r == "DM1_pt2":
            #     tes_range = "0.970,1.028"
            # elif r == "DM1_pt3":
            #     tes_range = "0.970,1.028"
            # elif r == "DM1_pt4":
            #     tes_range = "0.970,1.028"
            # elif r == "DM10_pt1":
            #     tes_range = "0.970,1.028"
            # elif r == "DM10_pt2":
            #     tes_range = "0.970,1.028"
            # elif r == "DM10_pt3":
            #     tes_range = "0.970,1.028"
            # elif r == "DM10_pt4":
            #     tes_range = "0.970,1.028"
            # elif r == "DM11_pt1":
            #     tes_range = "0.970,1.028"
            # elif r == "DM11_pt2":
            #     tes_range = "0.970,1.028"
            # elif r == "DM11_pt3":
            #     tes_range = "0.970,1.028"
            # elif r == "DM11_pt4":
            #     tes_range = "0.970,1.028"
            else:
                tes_range = "0.950,1.050"

            # Load parameters from file
            param_file = kwargs.get('param_file', f"{postfit_outdir}/FitparameterValues_{setup['tag']}_DeepTau_{era}-13TeV_{r}.txt")
            param_file = param_file.replace("postfit", "output")
            if os.path.exists(param_file):
                params = {}
                errors = {}
                with open(param_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = float(value.strip())
                            
                            if key.endswith("_1sigma_low"):
                                base = key.replace("_1sigma_low", "")
                                errors.setdefault(base, {})["low"] = value
                            elif key.endswith("_1sigma_high"):
                                base = key.replace("_1sigma_high", "")
                                errors.setdefault(base, {})["high"] = value
                            else:
                                # Central value
                                params[key] = value
                                errors.setdefault(key, {})["central"] = value

                # Debug print safely
                for p in errors:
                    c = errors[p].get('central', 'N/A')
                    l = errors[p].get('low', 'N/A')
                    h = errors[p].get('high', 'N/A')
                    print(f"  {p}: central={c}, low={l}, high={h}")

                # Construct range options
                range_opts_list = []
                for k in errors:
                    if 'low' in errors[k] and 'high' in errors[k]:
                        range_opts_list.append(f"{k}={errors[k]['low']},{errors[k]['high']}")
                range_opts = ":".join(range_opts_list)
                
                print("[DEBUG] --setParameterRanges:", range_opts)  

                # Strip combine's diagnostic branches — they were saved by
                # --saveSpecifiedNuis all / --saveNLL in step 1 but are NOT real
                # workspace parameters. combineTool Impacts chokes on them
                # (ReferenceError: null-pointer in prefit_from_workspace).
                _bad_keys = {"iChannel", "nll", "nll0"}
                param_opts = ",".join([f"{key}={value}" for key, value in params.items() if key not in _bad_keys])
                print(f"Option 3 - param_opts: {param_opts}")
                
                # Set up FitDiagnostics options for 2D scan
                # Seed POIs + saved nuisances from MultiDimFit best-fit (param_opts) so
                # FitDiagnostics doesn't start from defaults and get stuck in a local min.
                POI_OPTS_F = f"--saveNLL --setParameters r=1,{param_opts} --freezeParameters r"

                # Use workspace file
                workspace_file = f"{postfit_outdir}/{datacardfile}.root"
                # robustFit + strategy=2 needed for DM10 stability (was hitting negative
                # eigenvalues in Hesse because Migrad hadn't fully converged).
                # Aligned with MultiDimFit (step 1, option 3) so the two fits land in
                # the same basin: robustFit with Minuit2/strategy=1/tol=0.001, default
                # minimizer strategy=0, analytic derivatives. robustHesse kept for stable errors.
                FitDiagnostics_opts = f" -m 90 -d {workspace_file} {POI_OPTS_F} --setParameterRanges tes_{r}={tes_range}:tid_SF_{r}={tid_SF_range} -n .{BINLABELoutput} --robustFit=1 --setRobustFitAlgo=Minuit2 --setRobustFitStrategy=1 --setRobustFitTolerance=0.001 --cminDefaultMinimizerStrategy=0 --X-rtd MINIMIZER_analytic --robustHesse=1 --redefineSignalPOIs tes_{r},tid_SF_{r} --cminFallbackAlgo Minuit2,Migrad,0:0.0001 --cminPreScan {save_opts} --trackParameters tid_SF_{r}"
                # print(f"[DEBUG] Option 3 - FitDiagnostics command: combine -M FitDiagnostics {FitDiagnostics_opts} --redefineSignalPOIs tes_{r},tid_SF_{r} --plots")
                # os.system(f"combine -M FitDiagnostics {FitDiagnostics_opts} --redefineSignalPOIs tes_{r},tid_SF_{r}") # --plots")
                
                if str(config_mumu) != 'None':
                    # With Z→μμ CR: don't redefine POIs, they should be in the combined workspace
                    print(f"[DEBUG] Using combined workspace with Z→μμ CR - not redefining POIs")
                    os.system(f"combine -M FitDiagnostics {FitDiagnostics_opts}")
                    print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
                    print(f"combine -M FitDiagnostics {FitDiagnostics_opts}")
                    print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
                else:
                    # Without Z→μμ CR: redefine POIs for single region
                    print(f"[DEBUG] Using single region workspace - redefining POIs")
                    os.system(f"combine -M FitDiagnostics {FitDiagnostics_opts}")
                    print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
                    print(f"combine -M FitDiagnostics {FitDiagnostics_opts} --redefineSignalPOIs tes_{r},tid_SF_{r}")
                    print("<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
                print(f"FitDiagnostics for 2D scan {r} completed")
                if args.impacts:  # BUGS F06: impacts ran always; --impacts and --impacts-parallel were ignored
                    os.system(f"mkdir -p impacts/VSjet{jet_wp}_VSele{ele_wp}/")
                    os.system(f"combineTool.py -M Impacts -d {workspace_file} -m 90 --doInitialFit --robustFit 1 --cminFallbackAlgo Minuit2,0:1 -v 0 --redefineSignalPOIs tes_{r},tid_SF_{r} --setParameterRange tes_{r}={tes_range}:tid_SF_{r}={tid_SF_range} --setParameters r=1,{param_opts} --freezeParameters r ")
                    os.system(f"combineTool.py -M Impacts -d {workspace_file} -m 90 --doFits --robustFit 1  --parallel {args.impacts_parallel}  --redefineSignalPOIs tes_{r},tid_SF_{r} --setParameterRange tes_{r}={tes_range}:tid_SF_{r}={tid_SF_range} --setParameters r=1,{param_opts} --freezeParameters r -v 0")
                    os.system(f"combineTool.py -M Impacts -d {workspace_file} -m 90 -o impacts_{r}.json --redefineSignalPOIs tes_{r},tid_SF_{r} --setParameterRange tes_{r}={tes_range}:tid_SF_{r}={tid_SF_range} --setParameters r=1,{param_opts} --freezeParameters r -v 0")
                    os.system(f"plotImpacts.py -i impacts_{r}.json -o impacts/VSjet{jet_wp}_VSele{ele_wp}/impacts_{r}_tid_SF_{r} --POI tid_SF_{r}")
                    os.system(f"plotImpacts.py -i impacts_{r}.json -o impacts/VSjet{jet_wp}_VSele{ele_wp}/impacts_{r}_tes_{r} --POI tes_{r}")
                ##################################################
                try:
                    import ROOT

                    # open ROOT file
                    f = ROOT.TFile.Open(f"fitDiagnostics.{BINLABELoutput}.root")

                    # get the fit_s result
                    fr = f.Get("fit_s")

                    # get nuisance parameters
                    tes = fr.floatParsFinal().find(f"tes_{r}")
                    tid = fr.floatParsFinal().find(f"tid_SF_{r}")

                    # write to txt file
                    os.makedirs(f"FitDiagnosticsValues/VSjet{jet_wp}_VSele{ele_wp}/", exist_ok=True)
                    with open(f"FitDiagnosticsValues/VSjet{jet_wp}_VSele{ele_wp}/{r}_fitdiagnostics_TES_TauID_values.txt", "w") as out:
                        out.write(f"tes_{r} {tes.getVal()} {tes.getError()}\n")
                        out.write(f"tid_SF_{r} {tid.getVal()} {tid.getError()}\n")

                    print(f"Saved to FitDiagnosticsValues/VSjet{jet_wp}_VSele{ele_wp}/{r}_fitdiagnostics_TES_TauID_values.txt")
                except Exception as e:
                    print(f"[ERROR] FitDiagnostics output file fitDiagnostics.{BINLABELoutput}.root does not exist or could not be processed. Exception: {e}")
                ####################################################
                # Now run PostFitShapesFromWorkspace
                outf_postfit = f"{postfit_outdir}/PostFitShape_{era}_{setup['tag']}_{r}.root"
                outf_fit = f"fitDiagnostics.{BINLABELoutput}.root"
                
                # Check if FitDiagnostics output exists
                print(f"[DEBUG] Option 3 - PostFitShapesFromWorkspace command: PostFitShapesFromWorkspace --output {outf_postfit} --workspace {workspace_file} -f {outf_fit}:fit_s --postfit")
                os.system(f"PostFitShapesFromWorkspace --output {outf_postfit} --workspace {workspace_file} -f {outf_fit}:fit_s --postfit")
                
                # Move files to postfit directory
                os.system(f"mv {outf_fit} {postfit_outdir}/")
                print(f"[DEBUG] Created postfit shape file: {outf_postfit}")
            else:
                print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                print(f">>>>>>>>>>>>>>>>>[ERROR] Parameter file {param_file} does not exist. Skipping region {r}.")

                print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
# Plot the scan using output file of combined 
def plotScan(setup, setup_mumu, option, **kwargs):
    tid_SF_range = kwargs.get('tid_SF_range', "0.5,1.2")
    extratag     = kwargs.get('extratag',     "_DeepTau")
    era          = kwargs.get('era',          ""        )
    labelopt     = kwargs.get('labelopt',     ""        ) # --lumi/--cme for the plot scripts (CL §27)
    config       = kwargs.get('config',       ""        )
    indir        = kwargs.get('indir',        None      )
    if indir and not indir.rstrip('/').endswith(str(era)):
        indir = os.path.join(indir, str(era))
    indir_arg    = f"-i {indir}" if indir else ""
    # Plot 

    if option == '2' or option == '4'  :
        print(">>> Plot parabola")
        os.system(f"python3 TauES_ID/plotParabola_POI_region.py -p tid_SF -y {era} -e {extratag}  -s -a -c {config} {indir_arg}{labelopt}") # -y %s -e %s  -s -a -c %s"% (era, extratag, config))
        os.system(f"python3 TauES_ID/plotPostFitScan_POI.py --poi tid_SF -y {era} -e {extratag} -r {min(tid_SF_range)},{max(tid_SF_range)} -c {config} {indir_arg}{labelopt}") # -y %s -e %s -r %s,%s -c %s" %(era,extratag,min(tid_SF_range),max(tid_SF_range), config))

    elif option == '1' or option == '5' :
        print(">>> Plot parabola")
        os.system(f"python3 TauES_ID/plotParabola_POI_region.py -p tes -y {era} -e {extratag} -r {min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])} -s -a -c {config} {indir_arg}{labelopt}") # -y %s -e %s -r %s,%s -s -a -c %s " % (era, extratag, min(setup["TESvariations"]["values"]), max(setup["TESvariations"]["values"]), config)) # -b
        os.system(f"python3 TauES_ID/plotPostFitScan_POI.py --poi tes -y {era} -e {extratag} -r {min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])} -c {config} {indir_arg}{labelopt}") # -y %s -e %s -r %s,%s -c %s" %(era,extratag,min(setup["TESvariations"]["values"]),max(setup["TESvariations"]["values"]), config))
        # EXTRATAG NOT WORKING
    elif option == '3':
        print(">>> Plot 2D scans and uncertainty summaries....")
        
        # # Then create the individual region plots and parabolas
        # for r in setup["observables"]["m_vis"]["scanRegions"]:
        #     os.system(f"python3 TauES_ID/plot2DScan_MultiDimFit.py --poi1 tes_{r} --poi2 tid_SF_{r} -y {era} -c {config} {indir_arg}")
            
        # # Keep the existing parabola plots
        # os.system(f"python3 TauES_ID/plotParabola_POI_region.py -p tid_SF -y {era} -e {extratag}  -s -a -c {config} {indir_arg}") # -y %s -e %s  -s -a -c %s"% (era, extratag, config))
        # os.system(f"python3 TauES_ID/plotPostFitScan_POI.py --poi tid_SF -y {era} -e {extratag} -r {min(tid_SF_range)},{max(tid_SF_range)} -c {config} {indir_arg}") # -y %s -e %s -r %s,%s -c %s" %(era,extratag,min(tid_SF_range),max(tid_SF_range), config))
        # os.system(f"python3 TauES_ID/plotParabola_POI_region.py -p tes -y {era} -e {extratag} -r {min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])} -s -a -c {config} {indir_arg}") # -y %s -e %s -r %s,%s -s -a -c %s " % (era, extratag, min(setup["TESvariations"]["values"]), max(setup["TESvariations"]["values"]), config)) # -b
        # os.system(f"python3 TauES_ID/plotPostFitScan_POI.py --poi tes -y {era} -e {extratag} -r {min(setup['TESvariations']['values'])},{max(setup['TESvariations']['values'])} -c {config} {indir_arg}")
    else:
        print(" No output plot...")






### main function
def main(args):

    era    = args.era
    config = args.config
    config_mumu = args.config_mumu 
    option = args.option
    extratag     = "_DeepTau"


    print("Using configuration file: %s"%(args.config))
    with open(args.config, 'r') as file:
        setup = yaml.safe_load(file)

    if config_mumu != 'None':
        print("Using configuration file for mumu: %s"%(args.config_mumu))
        with open(args.config_mumu, 'r') as file_mumu:
            setup_mumu = yaml.safe_load(file_mumu)
    else: 
        setup_mumu = 0

    # # Generating the datacards for mutau channel
    # generate_datacards_mutau(era=era, config=config,extratag=extratag)

    # Generating the datacards for mumu channel
    # if str(config_mumu) != 'None':
        # generate_datacards_mumu(era=era, config_mumu=config_mumu,extratag=extratag)

    # Run the fit using combine with the different options 
    run_combined_fit(setup,setup_mumu, era=era, config=config, config_mumu=config_mumu, option=option, mumu_input_file=args.mumu_input_file)

    # # Plots 
    labelopt = "".join(" --%s %r" % (key, value) for key, value in (('lumi', args.lumi), ('cme', args.cme)) if value is not None)
    plotScan(setup,setup_mumu, era=era, config=config, config_mumu=config_mumu, option=option, indir=args.indir, labelopt=labelopt)


###
if __name__ == '__main__':

    argv = sys.argv
    parser = ArgumentParser(prog="makeTESfit", description="execute all steps to run TES fit")
    parser.add_argument('-y', '--era', dest='era', choices=['2016', '2017', '2018', 'UL2016_preVFP','UL2016_postVFP', 'UL2017', 'UL2018','UL2018_v10','2022_postEE','2022_preEE', '2024', '2025', '2026', '2526'], default=['UL2018'], action='store', help="set era")
    parser.add_argument('-c', '--config', dest='config', type=str, default='TauES_ID/config/defaultFitSetupTES_mutau.yml', action='store', help="set config file containing sample & fit setup")
    parser.add_argument('-o', '--option', dest='option', choices=['1', '2', '3', '4', '5','6'], default='1', action='store',
                        help="set option : Scan of tes and tid SF is profiled (-o 1) ;  Scan of tid SF and tes is profiled (-o 2) ; 2D scan of tes and tid SF (-o 3) \
                        ; Scan of tid SF, tid SF and tes of other regions are profiled POIs (-o 4); Scan of tes, tid SF and tes of other regions are profiled POIs(-o 5)\
                        ; 2D scan of tes and tid SF and tes of other regions are profiled POIs (-o 6) ")
    parser.add_argument('-cmm', '--config_mumu', dest='config_mumu', type=str, default='None', action='store', help="set config file containing sample & fit setup")
    parser.add_argument('--indir', dest='indir', type=str, required=False, help="Path to the input root file for mutau")
    parser.add_argument('--mumu_input_file', dest='mumu_input_file', type=str, required=False, help="Path to the input root file for mumu")
    parser.add_argument('--jet_wp', dest='jet_wp', type=str, required=True, help="jet working point")
    parser.add_argument('--ele_wp', dest='ele_wp', type=str, required=True, help="electron working point")
    parser.add_argument('--impacts', dest='impacts', action='store_true', default=False, help="also run combineTool -M Impacts per region after FitDiagnostics (slow)")
    parser.add_argument('--impacts-parallel', dest='impacts_parallel', type=int, default=8, help="--parallel value for combineTool Impacts --doFits")
    parser.add_argument('--lumi', dest='lumi', type=float, default=None, help="integrated luminosity [/fb] of the CMS label (default: CMSStyle.lumi_dict of the era; the TauFW Framework gives the one of the shapes' normalisation, CL §27)")
    parser.add_argument('--cme', dest='cme', type=float, default=None, help="centre-of-mass energy [TeV] of the CMS label (default: CMSStyle.cme_dict of the era)")
    args = parser.parse_args()

    main(args)
    print(">>>\n>>> done\n")




#      python3 TauES_ID/harvestDatacards_zmm.py -y 2024 -c TauES/config/defaultFitSetup_mumu.yml  -o output_pt_less_region/againstjet_Medium/againstelectron_VVLoose/2024/ -v -i input_pt_less_region/againstjet_Medium/againstelectron_VVLoose/





#  python3 TauES_ID/makecombinedfitTES_SF.py -y 2024 -c TauES_ID/config/config_tests.yml --mumu_datacard_file input_pt_less_region/againstjet_Medium/againstelectron_VVLoose/ztt_mm_tes_m_vis.inputs-2024-13TeV_mumu.root -i input_pt_less_region/againstjet_Medium/againstelectron_VVLoose --input_file input_pt_less_region/againstjet_Medium/againstelectron_VVLoose/ztt_mt_tes_m_vis.inputs-2024-13TeV_mutau_mt65_DM_pt_Dt2p5_puppimet.root -o 1/2

# python3 TauES_ID/makecombinedfitTES_SF_postfit.py -y 2024 -c TauES_ID/config/config_tests.yml -o 1 -cmm TauES/config/defaultFitSetup_mumu.yml --mumu_input_file output_pt_less_region/againstjet_Medium/againstelectron_VVLoose/2024/ztt_mm_m_vis-baseline_mumu-2024-13TeV.txt 



# python3 TauES_ID/makecombinedfitTES_SF.py -y 2024 -c TauES_ID/config/Default_FitSetupTES_mutau_DM_mt65pt_lessptregion.yml --mumu_datacard_file output_pt_less_region/againstjet_Medium/againstelectron_VVLoose/2024/ztt_mm_m_vis-baseline_mumu-2024-13TeV.txt -i input_pt_less_region/againstjet_VTight/againstelectron_Loose/ --input_file input_pt_less_region/againstjet_VTight/againstelectron_Loose/ztt_mt_tes_m_vis.inputs-2024-13TeV_mutau.root -o 1

# python3 TauES_ID/makecombinedfitTES_SF_postfit.py -y 2024 -c ../Configs/Fitter/tes_id/config_coarse_TT.yml  -cmm ../Configs/Fitter/tes_id/FitSetup_mumu.yml --mumu_input_file output_pt_less_region/againstjet_Medium/againstelectron_Tight/2024/ztt_mm_m_vis-baseline_mumu-2024-13TeV.txt --indir output_pt_less_region/againstjet_Medium/againstelectron_Tight/ -o 1


#### python3 TauES_ID/makecombinedfitTES_SF.py -y 2024 -c ../Configs/Fitter/tes_id/config_coarse_TT.yml -i input_pt_less_region/againstjet_Medium/againstelectron_Tight/ --input_file input_pt_less_region/againstjet_Medium/againstelectron_Tight/ztt_mt_tes_m_vis.inputs-2024-13TeV_mutau.root -o 1 && clear && python3 TauES_ID/makecombinedfitTES_SF_postfit.py -y 2024 -c ../Configs/Fitter/tes_id/config_coarse_TT.yml --indir output_pt_less_region/againstjet_Medium/againstelectron_Tight/ -o 1 && python3 python/plot/runpostfit.py -c ../Configs/Fitter/tes_id/config_coarse_TT.yml
