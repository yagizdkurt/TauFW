# Define working points
J_VALUES=("VVLoose" "Loose" "Tight" "VTight" "VLoose" "Medium")
E_VALUES=("VVLoose" "Tight")

YEAR="2025"
CONFIG_TT="TauES_ID/config/config_coarse_TT.yml"
CONFIG_MM="TauES/config/FitSetup_mumu.yml"

# Loop over each combination
for JET_WP in "${J_VALUES[@]}"; do
  for ELE_WP in "${E_VALUES[@]}"; do
    echo "=========================================="
    echo "=== Running Workflow for Jet=$JET_WP, Ele=$ELE_WP ==="
    echo "=========================================="

    BASE_INPUT="input_pt_less_region/againstjet_${JET_WP}/againstelectron_${ELE_WP}"
    BASE_OUTPUT="output_pt_less_region/againstjet_${JET_WP}/againstelectron_${ELE_WP}"
    BASE_PLOTS="plots_pt_less_region/againstjet_${JET_WP}/againstelectron_${ELE_WP}"

    echo "=== Step 1: Running MultiDimFit ==="
    python3 TauES_ID/harvestDatacards_zmm.py -y $YEAR -c $CONFIG_MM -i ${BASE_INPUT}/ -o ${BASE_OUTPUT}/$YEAR/
    # BUGS F04: --input_file was required but ignored, and is gone
    python3 TauES_ID/makecombinedfitTES_SF.py -y $YEAR -c $CONFIG_TT -i ${BASE_INPUT}/ \
      -o 3 --mumu_datacard_file ${BASE_OUTPUT}/$YEAR/ztt_mm_m_vis-baseline_mumu-$YEAR-13TeV.txt \
      2>&1 | tee step1_multidimfit_${JET_WP}_${ELE_WP}.log

    echo "=== Step 2: Running FitDiagnostics + PostFit ==="
    python3 TauES_ID/makecombinedfitTES_SF_postfit.py -y $YEAR -c $CONFIG_TT --indir ${BASE_OUTPUT}/ -o 3 \
      --mumu_input_file ${BASE_OUTPUT}/$YEAR/ztt_mm_m_vis-baseline_mumu-$YEAR-13TeV.txt \
      -cmm $CONFIG_MM --jet_wp ${JET_WP} --ele_wp ${ELE_WP} --impacts 2>&1 | tee step2_postfit_${JET_WP}_${ELE_WP}.log
    # BUGS F06: impacts now run only with --impacts (they always ran before), so it is passed here

    echo "=== Step 3: Running Plots ==="
    python3 python/plot/runpostfit.py -c $CONFIG_TT -j ${JET_WP} -e ${ELE_WP} -y $YEAR --include-cr \
      2>&1 | tee step3_plots_${JET_WP}_${ELE_WP}.log
    python3 pre_post_plot_combiner.py --scan_dir ${BASE_PLOTS}/$YEAR/ --jet_wp ${JET_WP} --ele_wp ${ELE_WP}
    python3 plot_measurements.py --jet_wp ${JET_WP} --ele_wp ${ELE_WP} --year $YEAR

    echo "=== Step 4: Correction File Generation ==="
    python3 createroot_TES.py -c $CONFIG_TT -j ${JET_WP} -e ${ELE_WP} -f root -y $YEAR
    python3 createroot_TES.py -c $CONFIG_TT -j ${JET_WP} -e ${ELE_WP} -f json -y $YEAR

    echo "=== Workflow completed for Jet=$JET_WP, Ele=$ELE_WP ==="
    echo
  done
done

# Build 4x3 scan grid (rows=DM, cols=pt) per WP combo
echo "=== Building scan grids per WP combo ==="
python3 make_scan_grid.py --root plots_pt_less_region
python3 make_measurements_grid.py 

# Merge all JSON correction files
echo "=== Merging all JSON correction files ==="
python3 merge_tau_jsons.py --type both -o tau_sf/TauCorrections_$YEAR.json -y $YEAR  # BUGS F01: -y (default 2024)

echo "=== Plotting 1D profile NLLs from 2D MultiDimFit outputs ==="
python3 plot1D_NLL_profiles.py --year $YEAR

echo "=== Building combined TauEnergy_SF + TauID_SF with per-(DM, pT-bin) uncorrelated systs ==="
python3 make_tid_2025.py -y $YEAR  # BUGS F02: -y (default 2025)

echo "All workflows completed successfully!"

# #!/bin/bash
# Usage: ./run_workflow_zmm.sh
