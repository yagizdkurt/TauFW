#!/usr/bin/env bash
# Combined 2025+2026 (era "2526") datacard inputs.
# Sibling of run_inputs.sh with YEAR=2526; everything else is identical.
# era "2526" resolves through: samples_v15 (data glob Muon*, puweight_2025_2026_69p2,
# 2025 muon SFs, lumi 135.48 via setera) and the TES_variations/2526->2025 symlink.
# Outputs land next to the 2025 ones, tagged inputs-2526-13TeV (no collision).

J_VALUES=("VTight" "VVLoose" "VLoose" "Loose" "Medium" "Tight")
E_VALUES=("Tight" "VVLoose")

YEAR=2526
CONFIG="TauES_ID/config/config_coarse_TT.yml"
CONFIG_MM="TauES/config/FitSetup_mumu.yml" #CR config

# Create timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M")
LOGFILE="run_TES_${YEAR}_${TIMESTAMP}.log"

echo "Logging to ${LOGFILE}"
echo "Run started at $(date)" | tee -a "$LOGFILE"

for j in "${J_VALUES[@]}"; do
    for e in "${E_VALUES[@]}"; do

        {
            echo "------------------------------------------------------------"
            echo "Running: -j ${j}, -e ${e}"
            echo "------------------------------------------------------------"
        } | tee -a "$LOGFILE"

        python3 ../Histogrammer/shapes/TauES/createinputsTES.py \
            -y ${YEAR} \
            -c ${CONFIG} \
            -j ${j} \
            -e ${e} 2>&1 | tee -a "$LOGFILE"
        STATUS=${PIPESTATUS[0]}   # BUGS F03: status of the mutau command (it was read after the mumu command)
        python3 ../Histogrammer/shapes/TauES/createinputsTES.py \
            -y ${YEAR} \
            -c ${CONFIG_MM} \
            -j ${j} \
            -e ${e}
        STATUS_MM=$?
        [[ $STATUS -eq 0 ]] && STATUS=$STATUS_MM   # BUGS F03: a mumu failure counts too

        if [[ $STATUS -ne 0 ]]; then
            echo "❌ ERROR: iteration failed for j=${j}, e=${e} (exit code $STATUS)" | tee -a "$LOGFILE"
            echo "→ Skipping and continuing..." | tee -a "$LOGFILE"
            continue
        fi

        echo "✔ Completed j=${j}, e=${e}" | tee -a "$LOGFILE"
        echo | tee -a "$LOGFILE"

    done
done

echo "Run finished at $(date)" | tee -a "$LOGFILE"
