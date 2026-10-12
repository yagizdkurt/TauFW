#!/bin/bash
# Save as run_workflow.sh

echo "=== Step 1: Running MultiDimFit ==="
python3 TauES_ID/makecombinedfitTES_SF.py -y 2024 -c TauES_ID/config/config_coarse_TT.yml -i input_pt_less_region/againstjet_Medium/againstelectron_VVLoose/ --input_file input_pt_less_region/againstjet_Medium/againstelectron_VVLoose/ztt_mt_tes_m_vis.inputs-2024-13TeV_mutau.root -o 3 2>&1 | tee step1_multidimfit.log

echo "=== Step 2: Running FitDiagnostics + PostFit ==="
python3 TauES_ID/makecombinedfitTES_SF_postfit.py -y 2024 -c TauES_ID/config/config_coarse_TT.yml --indir output_pt_less_region/againstjet_Medium/againstelectron_VVLoose/ -o 3 2>&1 | tee step2_postfit.log

echo "=== Step 3: Running Plots ==="
python3 python/plot/runpostfit.py -c TauES_ID/config/config_coarse_TT.yml 2>&1 | tee step3_plots.log
python3 pre_post_plot_combiner.py --scan_dir plots_pt_less_region/againstjet_Medium/againstelectron_VVLoose/2024/
python3 plot_measurements.py
echo "=== Workflow completed ==="


echo "=== Workflow completed ==="


# Note: Add additional steps as needed for 2D scan processing and ROOT/JSON creation
# python3 createroot_TES.py -y 2024 -c TauES_ID/config/config_coarse_TT.yml