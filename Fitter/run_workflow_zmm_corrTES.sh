# Workflow for the CORRELATED-TES fit variant.
# One TES POI per DM (correlated across pT bins) + 3 TauID SF POIs per DM (uncorrelated by pT).
# Sibling of run_workflow_zmm.sh (uncorrelated TES). Uses parallel _corrTES scripts and
# a separate output/plot tree so the two fits can be compared side-by-side.

J_VALUES=("VVLoose" "Medium" "Loose" "Tight" "VTight" "VLoose") 
E_VALUES=("Tight" "VVLoose") 

YEAR="2024"
CONFIG_TT="../Configs/Fitter/tes_id/config_coarse_TT.yml"
CONFIG_MM="../Configs/Fitter/tes_id/FitSetup_mumu.yml"

# Separate I/O tree for the corrTES variant — keep uncorrelated outputs intact
INPUT_ROOT="input_pt_less_region"           # inputs are shared with the uncorrelated workflow
OUTPUT_ROOT="output_pt_less_region_corrTES"
PLOTS_ROOT="plots_pt_less_region_corrTES"

for JET_WP in "${J_VALUES[@]}"; do
  for ELE_WP in "${E_VALUES[@]}"; do
    echo "=========================================="
    echo "=== [corrTES] Jet=$JET_WP, Ele=$ELE_WP ==="
    echo "=========================================="

    BASE_INPUT="${INPUT_ROOT}/againstjet_${JET_WP}/againstelectron_${ELE_WP}"
    BASE_OUTPUT="${OUTPUT_ROOT}/againstjet_${JET_WP}/againstelectron_${ELE_WP}"
    BASE_POSTFIT="${OUTPUT_ROOT/output/postfit}/againstjet_${JET_WP}/againstelectron_${ELE_WP}"
    BASE_PLOTS="${PLOTS_ROOT}/againstjet_${JET_WP}/againstelectron_${ELE_WP}"

    echo "=== Step 1: Zmm CR datacard + per-DM MultiDimFit (corrTES) ==="
    python3 TauES_ID/harvestDatacards_zmm.py -y $YEAR -c $CONFIG_MM -i ${BASE_INPUT}/ -o ${BASE_OUTPUT}/$YEAR/
    python3 TauES_ID/makecombinedfitTES_SF_corrTES.py -y $YEAR -c $CONFIG_TT -i ${BASE_INPUT}/ \
      --input_file ${BASE_INPUT}/ztt_mt_tes_m_vis.inputs-$YEAR-13TeV_mutau.root \
      -o 3 --mumu_datacard_file ${BASE_OUTPUT}/$YEAR/ztt_mm_m_vis-baseline_mumu-$YEAR-13TeV.txt \
      2>&1 | tee step1_multidimfit_corrTES_${JET_WP}_${ELE_WP}.log

    echo "=== Step 2: FitDiagnostics + PostFit (corrTES, per-DM) ==="
    python3 TauES_ID/makecombinedfitTES_SF_postfit_corrTES.py -y $YEAR -c $CONFIG_TT \
      --indir ${BASE_OUTPUT}/ -o 3 \
      --mumu_input_file ${BASE_OUTPUT}/$YEAR/ztt_mm_m_vis-baseline_mumu-$YEAR-13TeV.txt \
      -cmm $CONFIG_MM --jet_wp ${JET_WP} --ele_wp ${ELE_WP} \
      2>&1 | tee step2_postfit_corrTES_${JET_WP}_${ELE_WP}.log

    echo "=== Step 2b: Nuisance pull plots (per DM) ==="
    PULL_TOOL="${CMSSW_BASE}/src/HiggsAnalysis/CombinedLimit/test/diffNuisances.py"
    PULLDIR="${BASE_PLOTS}/${YEAR}/pulls"
    mkdir -p "${PULLDIR}"
    for DM in DM0 DM1 DM10 DM11; do
      FD="${BASE_POSTFIT}/${YEAR}/fitDiagnostics.mt_m_vis-${DM}_mutau_DeepTau-${YEAR}-13TeV.root"
      if [ ! -f "${FD}" ]; then echo "  [pulls] missing ${FD} — skip ${DM}"; continue; fi
      PULLTXT="${PULLDIR}/pulls_${JET_WP}_${ELE_WP}_${DM}.txt"
      python3 "${PULL_TOOL}" --poi tes_${DM} --vtol=0.1 "${FD}" 2>/dev/null | sed 's/[!,]/ /g' | tail -n +4 > "${PULLTXT}"
      python3 scripts/plot_pulls.py -f "${PULLTXT}" -o "${PULLDIR}/pulls_${JET_WP}_${ELE_WP}_${DM}" -t "${JET_WP}/${ELE_WP} ${DM}"
    done

    echo "=== Step 3: Plots ==="
    python3 python/plot/runpostfit.py --variant corr -c $CONFIG_TT -j ${JET_WP} -e ${ELE_WP} -y $YEAR --include-cr \
      2>&1 | tee step3_plots_corrTES_${JET_WP}_${ELE_WP}.log
    python3 pre_post_plot_combiner.py --variant corr --scan_dir ${BASE_PLOTS}/$YEAR/ --jet_wp ${JET_WP} --ele_wp ${ELE_WP}
    python3 plot_measurements.py --variant corr --jet_wp ${JET_WP} --ele_wp ${ELE_WP} --year $YEAR

    echo "=== Step 4: Correction file generation (corrTES) ==="
    python3 createroot_TES.py --variant corr -c $CONFIG_TT -j ${JET_WP} -e ${ELE_WP} -f root -y $YEAR
    python3 createroot_TES.py --variant corr -c $CONFIG_TT -j ${JET_WP} -e ${ELE_WP} -f json -y $YEAR

    echo "=== [corrTES] done: Jet=$JET_WP, Ele=$ELE_WP ==="
    echo
  done
done

echo "=== Scan grids per WP combo ==="
python3 make_scan_grid.py --variant corr --root ${PLOTS_ROOT}
python3 make_measurements_grid.py

echo "=== Merging JSON correction files (corrTES) ==="
python3 merge_tau_jsons.py --variant corr --type both -o tau_sf/TauCorrections_${YEAR}_corrTES.json

echo "=== 1D profile NLLs from per-DM joint fits ==="
python3 plot1D_NLL_profiles.py --variant corr --year $YEAR

echo "=== Building combined TauEnergy_SF + TauID_SF (corrTES variant) ==="
python3 make_tid_2025.py --variant corr -y $YEAR

echo "All corrTES workflows completed!"
